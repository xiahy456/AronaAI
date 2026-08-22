"""30-case knowledge RAG eval: precision, misses, and false recall.

Three buckets (10 cases each):
  1. direct  — ask about one existing lore chunk
  2. unrelated — chit-chat / off-corpus; any hit is false recall
  3. multi — one utterance that targets two lore chunks

Usage (from backend/):
  python scripts/eval_knowledge_rag.py
  python scripts/eval_knowledge_rag.py --json-out logs/rag_eval.json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

from app.config import load_config  # noqa: E402
from app.knowledge import KnowledgeRetriever, ingest_corpus, load_corpus  # noqa: E402

# Titles must match corpus `##` headings exactly.
DIRECT = "direct"
UNRELATED = "unrelated"
MULTI = "multi"

CASES: list[dict[str, object]] = [
    # --- 1. Direct questions about existing chunks ---
    {
        "id": "d01",
        "bucket": DIRECT,
        "query": "阿洛娜是谁？",
        "expect": ["身份"],
    },
    {
        "id": "d02",
        "bucket": DIRECT,
        "query": "阿洛娜平时负责什么工作？",
        "expect": ["职责"],
    },
    {
        "id": "d03",
        "bucket": DIRECT,
        "query": "阿洛娜穿什么衣服？发带和裙子是什么样的？",
        "expect": ["服装"],
    },
    {
        "id": "d04",
        "bucket": DIRECT,
        "query": "阿洛娜身高多少？头发和眼睛是什么颜色？",
        "expect": ["外貌"],
    },
    {
        "id": "d05",
        "bucket": DIRECT,
        "query": "阿洛娜的光环一般是什么颜色和形状？",
        "expect": ["光环"],
    },
    {
        "id": "d06",
        "bucket": DIRECT,
        "query": "基沃托斯是什么地方？",
        "expect": ["基沃托斯概况"],
    },
    {
        "id": "d07",
        "bucket": DIRECT,
        "query": "沙勒全称是什么？和联邦学生会是什么关系？",
        "expect": ["联邦学生会与沙勒"],
    },
    {
        "id": "d08",
        "bucket": DIRECT,
        "query": "什亭之匣是什么？也叫什亭之箱吗？",
        "expect": ["什亭之匣是什么"],
    },
    {
        "id": "d09",
        "bucket": DIRECT,
        "query": "老师和什亭之匣、阿洛娜是什么关系？",
        "expect": ["与老师的关系"],
    },
    {
        "id": "d10",
        "bucket": DIRECT,
        "query": "阿洛娜生气、慌张或者特别开心的时候，光环会怎么变？",
        "expect": ["光环"],
    },
    # --- 2. Unrelated to the lore corpus ---
    {
        "id": "u01",
        "bucket": UNRELATED,
        "query": "啊，抱歉，突然有任务要做了",
        "expect": [],
    },
    {
        "id": "u02",
        "bucket": UNRELATED,
        "query": "今天有一点点忙",
        "expect": [],
    },
    {
        "id": "u03",
        "bucket": UNRELATED,
        "query": "晚饭吃什么好呢",
        "expect": [],
    },
    {
        "id": "u04",
        "bucket": UNRELATED,
        "query": "我去洗个澡先",
        "expect": [],
    },
    {
        "id": "u05",
        "bucket": UNRELATED,
        "query": "今天天气真好啊",
        "expect": [],
    },
    {
        "id": "u06",
        "bucket": UNRELATED,
        "query": "有点困了，想睡觉",
        "expect": [],
    },
    {
        "id": "u07",
        "bucket": UNRELATED,
        "query": "谢谢你，阿洛娜",
        "expect": [],
    },
    {
        "id": "u08",
        "bucket": UNRELATED,
        "query": "先这样吧，没什么事",
        "expect": [],
    },
    {
        "id": "u09",
        "bucket": UNRELATED,
        "query": "明天上午要开会",
        "expect": [],
    },
    {
        "id": "u10",
        "bucket": UNRELATED,
        "query": "刚才那部动画好看吗",
        "expect": [],
    },
    # --- 3. One utterance covering multiple chunks ---
    {
        "id": "m01",
        "bucket": MULTI,
        "query": "阿洛娜是谁，平时又负责什么？",
        "expect": ["身份", "职责"],
    },
    {
        "id": "m02",
        "bucket": MULTI,
        "query": "阿洛娜穿什么衣服，光环一般是什么颜色？",
        "expect": ["服装", "光环"],
    },
    {
        "id": "m03",
        "bucket": MULTI,
        "query": "阿洛娜多高，上衣和裙子是什么颜色？",
        "expect": ["外貌", "服装"],
    },
    {
        "id": "m04",
        "bucket": MULTI,
        "query": "什亭之匣是什么，基沃托斯又是什么地方？",
        "expect": ["什亭之匣是什么", "基沃托斯概况"],
    },
    {
        "id": "m05",
        "bucket": MULTI,
        "query": "联邦学生会和沙勒是做什么的，基沃托斯是学园都市吗？",
        "expect": ["联邦学生会与沙勒", "基沃托斯概况"],
    },
    {
        "id": "m06",
        "bucket": MULTI,
        "query": "阿洛娜左右瞳孔分别是什么颜色，光环平时又是什么样？",
        "expect": ["外貌", "光环"],
    },
    {
        "id": "m07",
        "bucket": MULTI,
        "query": "老师和什亭之匣是什么关系，阿洛娜的身份又是什么？",
        "expect": ["与老师的关系", "身份"],
    },
    {
        "id": "m08",
        "bucket": MULTI,
        "query": "阿洛娜的伞和发带是什么样的，生气的时候光环会变成什么样？",
        "expect": ["服装", "光环"],
    },
    {
        "id": "m09",
        "bucket": MULTI,
        "query": "阿洛娜平时帮老师做什么，和老师之间是什么关系？",
        "expect": ["职责", "与老师的关系"],
    },
    {
        "id": "m10",
        "bucket": MULTI,
        "query": "沙勒是联邦搜查社吗，什亭之匣又是老师随身带的什么设备？",
        "expect": ["联邦学生会与沙勒", "什亭之匣是什么"],
    },
]


@dataclass
class CaseResult:
    id: str
    bucket: str
    query: str
    expect: list[str]
    hits: list[str]
    hit_titles: list[str]
    tp: list[str]
    fp: list[str]
    fn: list[str]
    precision: float
    recall: float
    ok: bool
    note: str


def _known_titles(corpus_dir: Path) -> list[str]:
    return [c.title for c in load_corpus(corpus_dir)]


def _hit_title(text: str, known: list[str]) -> str:
    blob = (text or "").strip()
    for title in sorted(known, key=len, reverse=True):
        if blob.startswith(f"{title}：") or blob.startswith(f"{title}:"):
            return title
    if "：" in blob:
        return blob.split("：", 1)[0].strip()
    if ":" in blob:
        return blob.split(":", 1)[0].strip()
    return blob[:24]


def _safe_div(num: float, den: float) -> float:
    if den <= 0:
        return 1.0
    return num / den


def _evaluate_case(
    *,
    case: dict[str, object],
    hit_texts: list[str],
    known: list[str],
    top_k: int,
) -> CaseResult:
    expect = [str(t) for t in (case.get("expect") or [])]
    expect_set = set(expect)
    titles = [_hit_title(h, known) for h in hit_texts]
    hit_set = set(titles)
    tp = sorted(hit_set & expect_set)
    fp = sorted(hit_set - expect_set)
    fn = sorted(expect_set - hit_set)
    precision = _safe_div(len(tp), len(hit_set))
    recall_den = min(len(expect_set), top_k) if expect_set else 0
    if not expect_set:
        recall = 1.0 if not hit_set else 0.0
        ok = not hit_set
        note = "empty_ok" if ok else "false_recall"
    else:
        recall = _safe_div(len(tp), recall_den)
        # Direct: gold title must appear, no extras.
        # Multi: at least two gold titles (or all if expect < 2), no extras.
        need = 1 if case["bucket"] == DIRECT else min(2, len(expect_set), top_k)
        ok = (len(tp) >= need) and not fp
        if ok:
            note = "ok"
        elif fp and len(tp) >= need:
            note = "false_recall"
        elif fp:
            note = "miss+false_recall"
        else:
            note = "miss"
    return CaseResult(
        id=str(case["id"]),
        bucket=str(case["bucket"]),
        query=str(case["query"]),
        expect=expect,
        hits=list(hit_texts),
        hit_titles=titles,
        tp=tp,
        fp=fp,
        fn=fn,
        precision=round(precision, 4),
        recall=round(recall, 4),
        ok=ok,
        note=note,
    )


def _print_case(result: CaseResult) -> None:
    mark = "PASS" if result.ok else "FAIL"
    print(f"[{mark}] {result.id} ({result.bucket}) {result.note}")
    print(f"  Q: {result.query}")
    print(f"  expect: {result.expect or '（无）'}")
    if result.hit_titles:
        print(f"  hits:   {result.hit_titles}")
    else:
        print("  hits:   （无）")
    if result.fp:
        print(f"  false:  {result.fp}")
    if result.fn:
        print(f"  miss:   {result.fn}")
    for i, hit in enumerate(result.hits, 1):
        preview = hit if len(hit) <= 100 else hit[:100] + "…"
        print(f"    {i}. {preview}")


def _bucket_stats(rows: list[CaseResult]) -> dict[str, object]:
    n = len(rows)
    ok_n = sum(1 for r in rows if r.ok)
    false_n = sum(1 for r in rows if r.fp)
    miss_n = sum(1 for r in rows if r.fn)
    tp = sum(len(r.tp) for r in rows)
    fp = sum(len(r.fp) for r in rows)
    fn = sum(len(r.fn) for r in rows)
    return {
        "cases": n,
        "pass": ok_n,
        "pass_rate": round(_safe_div(ok_n, n), 4),
        "false_recall_cases": false_n,
        "false_recall_rate": round(_safe_div(false_n, n), 4),
        "miss_cases": miss_n,
        "miss_rate": round(_safe_div(miss_n, n), 4),
        "micro_precision": round(_safe_div(tp, tp + fp), 4),
        "micro_recall": round(_safe_div(tp, tp + fn), 4),
        "tp": tp,
        "fp": fp,
        "fn": fn,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Write full results JSON to this path",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=None,
        help="Override knowledge.retrieve_top_k for this run",
    )
    parser.add_argument(
        "--no-ingest",
        action="store_true",
        help="Skip ingest_corpus; use the existing Chroma collection",
    )
    args = parser.parse_args()

    if len(CASES) != 30:
        print(f"FAIL: expected 30 cases, found {len(CASES)}", file=sys.stderr)
        return 1
    buckets = {DIRECT: 0, UNRELATED: 0, MULTI: 0}
    for case in CASES:
        buckets[str(case["bucket"])] += 1
    if buckets != {DIRECT: 10, UNRELATED: 10, MULTI: 10}:
        print(f"FAIL: expected 10/10/10 buckets, got {buckets}", file=sys.stderr)
        return 1

    config = load_config()
    if not args.no_ingest:
        try:
            n = ingest_corpus(config, rebuild=False)
            print(f"ingest ensured: {n} chunks")
        except Exception as exc:
            print(f"FAIL: ingest: {exc}", file=sys.stderr)
            return 1

    known = _known_titles(config.knowledge_corpus_abs_path)
    missing_expect = sorted(
        {
            title
            for case in CASES
            for title in (case.get("expect") or [])
            if str(title) not in known
        }
    )
    if missing_expect:
        print(
            f"FAIL: case expect titles not in corpus: {missing_expect}",
            file=sys.stderr,
        )
        return 1

    config.knowledge.enabled = True
    config.knowledge.query_cache_enabled = False
    top_k = args.top_k if args.top_k is not None else int(config.knowledge.retrieve_top_k)
    retriever = KnowledgeRetriever(config)

    print(
        f"collection={config.knowledge.collection} top_k={top_k} "
        f"min_score={config.knowledge.min_score} "
        f"score_margin={config.knowledge.score_margin} chunks={len(known)}"
    )
    print("titles:", ", ".join(known))
    print()

    results: list[CaseResult] = []
    for case in CASES:
        hits = retriever.retrieve(str(case["query"]), top_k=top_k)
        result = _evaluate_case(
            case=case, hit_texts=hits, known=known, top_k=top_k
        )
        results.append(result)
        _print_case(result)
        print()

    overall = _bucket_stats(results)
    print("=== summary ===")
    print(
        f"all  pass={overall['pass']}/{overall['cases']} "
        f"({overall['pass_rate']:.0%})  "
        f"false_recall_cases={overall['false_recall_cases']} "
        f"({overall['false_recall_rate']:.0%})  "
        f"miss_cases={overall['miss_cases']} ({overall['miss_rate']:.0%})"
    )
    print(
        f"     micro P={overall['micro_precision']:.3f} "
        f"R={overall['micro_recall']:.3f}  tp={overall['tp']} fp={overall['fp']} fn={overall['fn']}"
    )
    by_bucket: dict[str, dict[str, object]] = {}
    for name in (DIRECT, UNRELATED, MULTI):
        subset = [r for r in results if r.bucket == name]
        stats = _bucket_stats(subset)
        by_bucket[name] = stats
        print(
            f"{name:10} pass={stats['pass']}/{stats['cases']} "
            f"false_recall={stats['false_recall_cases']} "
            f"miss={stats['miss_cases']}  "
            f"P={stats['micro_precision']:.3f} R={stats['micro_recall']:.3f}"
        )

    fails = [r for r in results if not r.ok]
    if fails:
        print("\nfailed ids:", ", ".join(r.id for r in fails))

    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "top_k": top_k,
            "min_score": config.knowledge.min_score,
            "score_margin": config.knowledge.score_margin,
            "titles": known,
            "overall": overall,
            "by_bucket": by_bucket,
            "cases": [asdict(r) for r in results],
        }
        args.json_out.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\njson: {args.json_out}")

    # Report-only: always exit 0 after a successful run so residual false
    # recall remains visible instead of aborting the eval.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
