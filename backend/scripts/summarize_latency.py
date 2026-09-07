"""Summarize per-module latency stats from backend/logs/arona-backend.log.

A record is one completed orchestrator turn (`chat done` or `initiate done`).
Module times come from the `latency=` fields logged between the matching
`start` and `done`. Memory extract is attached when the extractor queue
runs after that turn.

Usage (from repo root or backend/):
  python backend/scripts/summarize_latency.py
  python scripts/summarize_latency.py --last 50
  python scripts/summarize_latency.py --last 20 --offset 20
  python scripts/summarize_latency.py --from "2026-09-07 12:00" --to "2026-09-07 13:00"
  python scripts/summarize_latency.py --slice -40:-20 --kind chat
"""

from __future__ import annotations

import argparse
import ast
import math
import re
import statistics
import sys
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = BACKEND_DIR / "logs" / "arona-backend.log"
DEFAULT_OUTPUT = BACKEND_DIR / "logs" / "latency_summary.txt"

RECORD_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) "
    r"\[(?P<level>\w+)\] (?P<logger>[\w.]+): (?P<msg>.*)$"
)
SESSION_RE = re.compile(r"session=(?P<session>\S+)")
LATENCY_S_RE = re.compile(r"latency=(?P<lat>\d+(?:\.\d+)?)s")
KIND_RE = re.compile(r"\bkind=(?P<kind>\S+)")
CONTEXT_RE = re.compile(r"\bcontext=(?P<ctx>\S+)")
REQUEST_RE = re.compile(r"\brequest=")

MODULE_SPECS: tuple[tuple[str, str, str], ...] = (
    ("query_embedding", "query embedding session=", "查询向量"),
    ("memory_retrieve", "initiate memory retrieve session=", "记忆检索"),
    ("memory_retrieve", "memory retrieve session=", "记忆检索"),
    ("rag_retrieve", "rag retrieve session=", "知识检索"),
    ("planner", "initiate planner session=", "Planner"),
    ("planner", "planner session=", "Planner"),
    ("llm_generate", "initiate llm done session=", "本地LLM"),
    ("llm_generate", "llm generate done session=", "本地LLM"),
)

MODULE_ORDER = (
    "query_embedding",
    "memory_retrieve",
    "rag_retrieve",
    "planner",
    "llm_generate",
    "memory_extract",
    "total",
    "total_ex_llm",
    "total_ex_planner",
    "total_ex_llm_planner",
)

MODULE_LABELS = {
    "query_embedding": "query_embedding       查询向量",
    "memory_retrieve": "memory_retrieve       记忆检索",
    "rag_retrieve": "rag_retrieve           知识检索",
    "planner": "planner                Planner",
    "llm_generate": "llm_generate           本地LLM",
    "memory_extract": "memory_extract         记忆抽取",
    "total": "total                  整轮总耗时",
    "total_ex_llm": "total_ex_llm           除去本地模型",
    "total_ex_planner": "total_ex_planner       除去Planner",
    "total_ex_llm_planner": "total_ex_llm_planner   除去本地模型+Planner",
}

DERIVED_MODULES = (
    "total_ex_llm",
    "total_ex_planner",
    "total_ex_llm_planner",
)
SHARE_SKIP = {"total", "memory_extract", *DERIVED_MODULES}
LABEL_WIDTH = 42

TS_FORMATS = (
    "%Y-%m-%d %H:%M:%S,%f",
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
)


@dataclass
class Turn:
    kind: str
    session: str
    start_ts: str
    done_ts: str = ""
    initiate_kind: str = ""
    context: str = ""
    request: str = ""
    latencies: dict[str, float] = field(default_factory=dict)

    @property
    def stamp(self) -> str:
        return self.done_ts or self.start_ts


@dataclass
class Stats:
    count: int
    mean: float
    median: float
    stdev: float | None
    min: float
    max: float
    p25: float
    p75: float
    p90: float
    p95: float
    total: float


def _reconfigure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass


def parse_timestamp(text: str) -> datetime:
    raw = (text or "").strip()
    if not raw:
        raise ValueError("empty timestamp")
    last_error: Exception | None = None
    for fmt in TS_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError as exc:
            last_error = exc
    raise ValueError(f"unrecognized timestamp: {raw!r}") from last_error


def parse_slice(text: str) -> slice:
    parts = text.split(":")
    if not 1 <= len(parts) <= 3:
        raise argparse.ArgumentTypeError(
            "slice must look like START:END, :N, N:, or -N:"
        )

    def maybe_int(value: str) -> int | None:
        if value == "":
            return None
        try:
            return int(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(
                f"invalid slice bound {value!r}"
            ) from exc

    return slice(*(maybe_int(part) for part in parts))


def percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        raise ValueError("empty sample")
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    rank = (len(sorted_vals) - 1) * (p / 100.0)
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return sorted_vals[low]
    weight = rank - low
    return sorted_vals[low] * (1.0 - weight) + sorted_vals[high] * weight


def compute_stats(values: list[float]) -> Stats | None:
    if not values:
        return None
    ordered = sorted(values)
    stdev = statistics.stdev(values) if len(values) >= 2 else None
    return Stats(
        count=len(values),
        mean=statistics.mean(values),
        median=statistics.median(values),
        stdev=stdev,
        min=ordered[0],
        max=ordered[-1],
        p25=percentile(ordered, 25),
        p75=percentile(ordered, 75),
        p90=percentile(ordered, 90),
        p95=percentile(ordered, 95),
        total=sum(values),
    )


def iter_log_records(text: str):
    current_ts = ""
    current_logger = ""
    current_msg_lines: list[str] = []

    def flush():
        if current_ts:
            yield current_ts, current_logger, "\n".join(current_msg_lines)

    for raw_line in text.splitlines():
        match = RECORD_RE.match(raw_line)
        if match:
            yield from flush()
            current_ts = match.group("ts")
            current_logger = match.group("logger")
            current_msg_lines = [match.group("msg")]
        elif current_ts:
            current_msg_lines.append(raw_line)
    yield from flush()


def _session_of(message: str) -> str:
    match = SESSION_RE.search(message)
    return match.group("session") if match else ""


def _latency_s(message: str) -> float | None:
    match = LATENCY_S_RE.search(message)
    if not match:
        return None
    return float(match.group("lat"))


def _read_python_string(text: str) -> str:
    if not text:
        return ""
    if text[0] not in "'\"":
        return text.split(" ", 1)[0]
    quote = text[0]
    i = 1
    chars: list[str] = [quote]
    while i < len(text):
        ch = text[i]
        chars.append(ch)
        if ch == "\\" and i + 1 < len(text):
            chars.append(text[i + 1])
            i += 2
            continue
        if ch == quote:
            literal = "".join(chars)
            try:
                value = ast.literal_eval(literal)
            except (SyntaxError, ValueError):
                value = literal[1:-1]
            return value if isinstance(value, str) else str(value)
        i += 1
    return text[1:]


def _preview_request(message: str, limit: int = 80) -> str:
    match = REQUEST_RE.search(message)
    if not match:
        return ""
    raw = _read_python_string(message[match.end() :]).replace("\n", " ").strip()
    if len(raw) > limit:
        return raw[: limit - 1] + "…"
    return raw


def _module_from_message(message: str) -> str | None:
    for module, prefix, _label in MODULE_SPECS:
        if message.startswith(prefix):
            return module
    return None


def _apply_derived_latencies(turn: Turn) -> None:
    total = turn.latencies.get("total")
    if total is None:
        return
    llm = float(turn.latencies.get("llm_generate") or 0.0)
    planner = float(turn.latencies.get("planner") or 0.0)
    turn.latencies["total_ex_llm"] = max(0.0, total - llm)
    turn.latencies["total_ex_planner"] = max(0.0, total - planner)
    turn.latencies["total_ex_llm_planner"] = max(0.0, total - llm - planner)


def parse_turns(text: str) -> list[Turn]:
    open_turns: dict[str, list[Turn]] = {}
    completed: list[Turn] = []
    extract_queue: deque[Turn] = deque()
    extract_start_ts: datetime | None = None

    def stack_for(session: str) -> list[Turn]:
        return open_turns.setdefault(session, [])

    def open_turn(kind: str, session: str, ts: str, message: str) -> Turn:
        turn = Turn(kind=kind, session=session, start_ts=ts)
        if kind == "initiate":
            kind_match = KIND_RE.search(message)
            if kind_match:
                turn.initiate_kind = kind_match.group("kind")
        turn.request = _preview_request(message)
        stack_for(session).append(turn)
        return turn

    def current_turn(session: str) -> Turn | None:
        stack = open_turns.get(session)
        if stack:
            return stack[-1]
        return None

    def close_turn(kind: str, session: str, ts: str, message: str) -> Turn:
        stack = stack_for(session)
        found: Turn | None = None
        for index in range(len(stack) - 1, -1, -1):
            if stack[index].kind == kind:
                found = stack.pop(index)
                break
        if found is None:
            found = Turn(kind=kind, session=session, start_ts=ts)
        found.done_ts = ts
        latency = _latency_s(message)
        if latency is not None:
            found.latencies["total"] = latency
        ctx = CONTEXT_RE.search(message)
        if ctx:
            found.context = ctx.group("ctx")
        kind_match = KIND_RE.search(message)
        if kind_match:
            found.initiate_kind = kind_match.group("kind")
        request = _preview_request(message)
        if request:
            found.request = request
        _apply_derived_latencies(found)
        completed.append(found)
        return found

    for ts, logger_name, message in iter_log_records(text):
        first_line = message.split("\n", 1)[0]
        session = _session_of(first_line)

        if logger_name == "app.orchestrator":
            if first_line.startswith("chat start session="):
                open_turn("chat", session, ts, first_line)
                continue
            if first_line.startswith("initiate start session="):
                open_turn("initiate", session, ts, first_line)
                continue
            if first_line.startswith("chat done session="):
                close_turn("chat", session, ts, first_line)
                continue
            if first_line.startswith("initiate done session="):
                close_turn("initiate", session, ts, first_line)
                continue
            if first_line.startswith("memory extract enqueue session="):
                target = current_turn(session)
                if target is None and completed:
                    for prior in reversed(completed):
                        if prior.session == session:
                            target = prior
                            break
                if target is not None:
                    extract_queue.append(target)
                continue
            module = _module_from_message(first_line)
            if module is None:
                continue
            latency = _latency_s(first_line)
            if latency is None or not session:
                continue
            target = current_turn(session)
            if target is None:
                continue
            target.latencies[module] = latency
            continue

        if logger_name != "app.memory.extractor":
            continue
        if first_line.startswith("memory extract start "):
            extract_start_ts = parse_timestamp(ts)
            continue
        if first_line.startswith("memory extract done "):
            if extract_queue and extract_start_ts is not None:
                target = extract_queue.popleft()
                delta = (parse_timestamp(ts) - extract_start_ts).total_seconds()
                if delta >= 0:
                    target.latencies["memory_extract"] = delta
            extract_start_ts = None

    return completed


def select_turns(turns: list[Turn], args: argparse.Namespace) -> list[Turn]:
    selected = list(turns)
    if args.kind != "all":
        selected = [turn for turn in selected if turn.kind == args.kind]

    if args.from_ts:
        start = parse_timestamp(args.from_ts)
        selected = [
            turn
            for turn in selected
            if parse_timestamp(turn.stamp) >= start
        ]
    if args.to_ts:
        end = parse_timestamp(args.to_ts)
        selected = [
            turn
            for turn in selected
            if parse_timestamp(turn.stamp) <= end
        ]

    if args.slice is not None:
        return selected[args.slice]
    if args.all:
        return selected

    count = args.last if args.last is not None else 20
    if count <= 0:
        return selected
    offset = max(0, args.offset)
    if offset == 0:
        return selected[-count:]
    end = len(selected) - offset
    start_index = max(0, end - count)
    if end <= 0:
        return []
    return selected[start_index:end]


def _fmt_sec(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.3f}s"


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:5.1f}%"


def _values(turns: list[Turn], module: str) -> list[float]:
    return [
        turn.latencies[module]
        for turn in turns
        if module in turn.latencies
    ]


def _share_stats(turns: list[Turn], module: str) -> tuple[float | None, float | None, int]:
    pairs = [
        (turn.latencies[module], turn.latencies["total"])
        for turn in turns
        if module in turn.latencies and "total" in turn.latencies and turn.latencies["total"] > 0
    ]
    if not pairs:
        return None, None, 0
    mean_share = statistics.mean(module_v / total_v for module_v, total_v in pairs)
    sum_share = sum(module_v for module_v, _total in pairs) / sum(
        total_v for _module, total_v in pairs
    )
    return mean_share, sum_share, len(pairs)


def _render_table(turns: list[Turn]) -> list[str]:
    header = (
        f"{'模块':<{LABEL_WIDTH}} {'样本':>6} {'平均':>10} {'中位数':>10} {'标准差':>10} "
        f"{'最小':>10} {'最大':>10} {'P25':>10} {'P75':>10} {'P90':>10} {'P95':>10}"
    )
    lines = [
        header,
        "-" * len(header),
    ]
    for module in MODULE_ORDER:
        stats = compute_stats(_values(turns, module))
        label = MODULE_LABELS[module]
        if stats is None:
            lines.append(
                f"{label:<{LABEL_WIDTH}} {0:6d} "
                + " ".join(f"{'—':>10}" for _ in range(9))
            )
            continue
        lines.append(
            f"{label:<{LABEL_WIDTH}} {stats.count:6d} "
            f"{_fmt_sec(stats.mean):>10} {_fmt_sec(stats.median):>10} "
            f"{_fmt_sec(stats.stdev):>10} {_fmt_sec(stats.min):>10} "
            f"{_fmt_sec(stats.max):>10} {_fmt_sec(stats.p25):>10} "
            f"{_fmt_sec(stats.p75):>10} {_fmt_sec(stats.p90):>10} "
            f"{_fmt_sec(stats.p95):>10}"
        )
    lines.append(
        "说明：total_ex_* = total 减去对应模块（该轮未出现则按 0），下限为 0。"
        " memory_extract 异步，不参与相减。"
    )
    return lines


def _render_share(turns: list[Turn]) -> list[str]:
    lines = [
        "占整轮总耗时比例（仅统计同时有该模块与 total 的记录）",
        "说明：memory_extract 在回包之后异步执行，不计入 total，故不列入本表。",
        f"{'模块':<{LABEL_WIDTH}} {'样本':>6} {'均值占比':>10} {'合计占比':>10}",
        "-" * (LABEL_WIDTH + 30),
    ]
    for module in MODULE_ORDER:
        if module in SHARE_SKIP:
            continue
        mean_share, sum_share, count = _share_stats(turns, module)
        label = MODULE_LABELS[module]
        if count == 0:
            lines.append(
                f"{label:<{LABEL_WIDTH}} {0:6d} {'—':>10} {'—':>10}"
            )
            continue
        lines.append(
            f"{label:<{LABEL_WIDTH}} {count:6d} "
            f"{_fmt_pct((mean_share or 0) * 100):>10} "
            f"{_fmt_pct((sum_share or 0) * 100):>10}"
        )
    return lines


def _render_records(turns: list[Turn]) -> list[str]:
    lines = ["采样记录明细"]
    for index, turn in enumerate(turns, start=1):
        kind = turn.kind
        if turn.initiate_kind:
            kind = f"{turn.kind}/{turn.initiate_kind}"
        parts = [
            f"[{index}] {turn.stamp}  {kind:<16} session={turn.session}",
            f"      total={_fmt_sec(turn.latencies.get('total'))}  "
            f"ex_llm={_fmt_sec(turn.latencies.get('total_ex_llm'))}  "
            f"ex_planner={_fmt_sec(turn.latencies.get('total_ex_planner'))}  "
            f"ex_both={_fmt_sec(turn.latencies.get('total_ex_llm_planner'))}  "
            f"context={turn.context or '—'}",
        ]
        module_bits = []
        for module in MODULE_ORDER:
            if module in {"total", *DERIVED_MODULES} or module not in turn.latencies:
                continue
            module_bits.append(f"{module}={turn.latencies[module]:.3f}s")
        if module_bits:
            parts.append("      " + "  ".join(module_bits))
        if turn.request:
            parts.append(f"      request={turn.request}")
        lines.extend(parts)
        lines.append("")
    return lines


def describe_selection(args: argparse.Namespace, n_all: int, n_selected: int) -> str:
    bits = [f"完成记录 {n_all} 条", f"采样 {n_selected} 条"]
    if args.kind != "all":
        bits.append(f"kind={args.kind}")
    if args.from_ts:
        bits.append(f"from={args.from_ts}")
    if args.to_ts:
        bits.append(f"to={args.to_ts}")
    if args.slice is not None:
        bits.append(f"slice={args.slice}")
    elif args.all:
        bits.append("range=all")
    else:
        count = args.last if args.last is not None else 20
        if args.offset:
            bits.append(f"last={count} offset={args.offset}")
        else:
            bits.append(f"last={count}")
    return "；".join(bits)


def render_report(
    *,
    source: Path,
    args: argparse.Namespace,
    all_turns: list[Turn],
    selected: list[Turn],
) -> str:
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "后端模块耗时汇总",
        f"source: {source}",
        f"generated: {generated}",
        describe_selection(args, len(all_turns), len(selected)),
    ]
    if selected:
        lines.append(f"时间范围: {selected[0].stamp}  ~  {selected[-1].stamp}")
    else:
        lines.append("时间范围: （无采样记录）")
    lines.append("")

    chat_n = sum(1 for turn in selected if turn.kind == "chat")
    initiate_n = sum(1 for turn in selected if turn.kind == "initiate")
    lines.append(f"其中 chat={chat_n}  initiate={initiate_n}")
    lines.append("")
    lines.append("== 全部采样 ==")
    lines.extend(_render_table(selected))
    lines.append("")
    lines.extend(_render_share(selected))
    lines.append("")

    if chat_n and initiate_n:
        for kind, label in (("chat", "用户对话"), ("initiate", "主动开口")):
            subset = [turn for turn in selected if turn.kind == kind]
            lines.append(f"== {label} ({kind}, {len(subset)} 条) ==")
            lines.extend(_render_table(subset))
            lines.append("")
            lines.extend(_render_share(subset))
            lines.append("")

    lines.extend(_render_records(selected))
    return "\n".join(lines).rstrip() + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize backend module latency stats from arona-backend.log."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"backend log file (default: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"summary output file (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--last",
        type=int,
        default=None,
        metavar="N",
        help="take the last N records after filters (default: 20)",
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        metavar="N",
        help="with --last, skip N newest records first (default: 0)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="use every record after kind/time filters (ignore --last)",
    )
    parser.add_argument(
        "--slice",
        type=parse_slice,
        default=None,
        metavar="START:END",
        help="Python slice on filtered records, e.g. 0:20, -40:-20, 10:",
    )
    parser.add_argument(
        "--from",
        dest="from_ts",
        default=None,
        metavar="TIME",
        help='keep records at/after this time, e.g. "2026-09-07 12:00"',
    )
    parser.add_argument(
        "--to",
        dest="to_ts",
        default=None,
        metavar="TIME",
        help='keep records at/before this time, e.g. "2026-09-07 13:00"',
    )
    parser.add_argument(
        "--kind",
        choices=("all", "chat", "initiate"),
        default="all",
        help="record kind to include (default: all)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    _reconfigure_stdio()
    args = parse_args(argv)
    if args.last is not None and args.last < 0:
        print("--last must be >= 0", file=sys.stderr)
        return 2
    if args.offset < 0:
        print("--offset must be >= 0", file=sys.stderr)
        return 2
    if args.from_ts:
        parse_timestamp(args.from_ts)
    if args.to_ts:
        parse_timestamp(args.to_ts)

    log_path = args.input if args.input.is_absolute() else (Path.cwd() / args.input)
    out_path = args.output if args.output.is_absolute() else (Path.cwd() / args.output)
    if not log_path.is_file():
        print(f"log file not found: {log_path}", file=sys.stderr)
        return 1

    text = log_path.read_text(encoding="utf-8", errors="replace")
    all_turns = parse_turns(text)
    selected = select_turns(all_turns, args)
    report = render_report(
        source=log_path,
        args=args,
        all_turns=all_turns,
        selected=selected,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    summary_end = report.find("采样记录明细")
    print(report[:summary_end] if summary_end > 0 else report, end="")
    print(f"wrote {len(selected)} records to {out_path} (from {log_path})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
