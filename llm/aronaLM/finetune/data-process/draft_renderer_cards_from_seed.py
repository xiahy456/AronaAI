#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Draft Planner-style intent cards from handwritten seed dialogues.

Does not rewrite gold replies. History is input to the card LLM only.
Writes data/raw/normal/review/queue.jsonl for human review.

  python data-process/draft_renderer_cards_from_seed.py
  python data-process/draft_renderer_cards_from_seed.py --limit 8
  python data-process/draft_renderer_cards_from_seed.py --resume
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from llm_client import chat_json  # noqa: E402
from renderer_format import BASE_MUST_NOT  # noqa: E402

FINETUNE_ROOT = Path(__file__).resolve().parent.parent
SEED_DIR = FINETUNE_ROOT / "data" / "raw" / "normal" / "seed"
REVIEW_DIR = FINETUNE_ROOT / "data" / "raw" / "normal" / "review"
QUEUE_PATH = REVIEW_DIR / "queue.jsonl"

DRAFT_SYSTEM = """你是阿洛娜桌面陪伴的「回复规划参谋」。根据老师原话和阿洛娜已经写好的金标回复，反推一张意图卡。
禁止改写金标对白。禁止输出台词草稿。

must_say 是给小模型 Renderer 的思路指令，不是回复里必须出现的词。
形态必须像线上 Planner，例如：
- 「回应老师的感谢，表示随时愿意陪伴」
- 「可自然询问老师接下来想做什么或想聊什么」
- 「表明自己是什亭之匣的操作系统管理员，并点明是老师的助手」
禁止：金标词碎片（只写「助手」）；并列三条「聊一聊A/B/C」；空泛「保持口吻」。
最多 2 条，至少 1 条；禁止空列表。必须能被金标回复落实（落实=完成意图，不是原文出现）。

must_not 写金标实际避开的行为，并合并固定禁令。
金标若含问号：不要写「用提问收尾」「不要以疑问结尾」「不要反问」。
提问可以出现；禁止的是把选择抛回老师（「还是…呢？」选题）。
轻松陪伴 ≠ 禁止提问。若金标在提问，must_say 应写出询问类指令。

只输出一个 JSON 对象，字段：
user_emotion, topic, stance, must_say, must_not, facts_to_use, tone
length 固定为 "1-2句" 由调用方写入。
"""


def _history_text(pairs: list[tuple[str, str]]) -> str:
    if not pairs:
        return "（无）"
    lines: list[str] = []
    for human, gpt in pairs:
        lines.append(f"老师：{human}")
        lines.append(f"阿洛娜：{gpt}")
    return "\n".join(lines)


def slice_seed(seed_dir: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted(seed_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            continue
        for src_i, rec in enumerate(data):
            conv = rec.get("conversations") if isinstance(rec, dict) else None
            if not isinstance(conv, list):
                continue
            pending_human = ""
            hist: list[tuple[str, str]] = []
            turn_i = 0
            for turn in conv:
                if not isinstance(turn, dict):
                    continue
                role = turn.get("from")
                val = str(turn.get("value") or "").strip()
                if role == "human":
                    pending_human = val
                elif role == "gpt" and pending_human:
                    items.append(
                        {
                            "id": f"{path.name}#{src_i}#t{turn_i}",
                            "source_file": path.name,
                            "source_index": src_i,
                            "turn_index": turn_i,
                            "user_text": pending_human,
                            "gold": val,
                            "history_for_card": [
                                {"user": h, "gpt": g} for h, g in hist[-2:]
                            ],
                        }
                    )
                    hist.append((pending_human, val))
                    pending_human = ""
                    turn_i += 1
    return items


def _normalize_card(parsed: dict[str, Any], gold: str) -> dict[str, Any]:
    must_say = parsed.get("must_say")
    if not isinstance(must_say, list):
        must_say = []
    must_say = [str(x).strip() for x in must_say if str(x).strip()][:2]
    must_not = parsed.get("must_not")
    if not isinstance(must_not, list):
        must_not = []
    must_not = [str(x).strip() for x in must_not if str(x).strip()]
    seen = set(must_not)
    for ban in BASE_MUST_NOT:
        if ban not in seen:
            must_not.append(ban)
            seen.add(ban)
    if ("？" in gold or "?" in gold) and any(
        k in "".join(must_not) for k in ("用提问收尾", "不要以疑问结尾", "不要反问")
    ):
        must_not = [
            x
            for x in must_not
            if not any(k in x for k in ("用提问收尾", "不要以疑问结尾", "不要反问"))
        ]
    facts = parsed.get("facts_to_use")
    if not isinstance(facts, list):
        facts = []
    facts = [str(x).strip() for x in facts if str(x).strip()]
    return {
        "user_emotion": str(parsed.get("user_emotion") or "").strip() or "平常",
        "topic": str(parsed.get("topic") or "").strip() or "日常",
        "stance": str(parsed.get("stance") or "").strip() or "接住本轮短回复",
        "must_say": must_say,
        "must_not": must_not,
        "facts_to_use": facts,
        "tone": str(parsed.get("tone") or "").strip() or "温柔短句",
        "length": "1-2句",
    }


def draft_card(item: dict[str, Any]) -> dict[str, Any]:
    hist_pairs = [
        (str(h.get("user") or ""), str(h.get("gpt") or ""))
        for h in (item.get("history_for_card") or [])
        if isinstance(h, dict)
    ]
    payload = {
        "source_file": item.get("source_file"),
        "history": _history_text(hist_pairs),
        "user_text": item["user_text"],
        "gold_reply": item["gold"],
        "fixed_must_not": BASE_MUST_NOT,
    }
    last_error = "empty_must_say"
    for attempt in range(2):
        user = json.dumps(payload, ensure_ascii=False)
        if attempt == 1:
            user += "\n\n上一轮 must_say 为空。必须给出 1–2 条思路指令，禁止空列表。"
        parsed = chat_json(
            system=DRAFT_SYSTEM,
            user=user,
            temperature=0.2,
            max_tokens=700,
        )
        if not isinstance(parsed, dict):
            last_error = "draft did not return an object"
            continue
        card = _normalize_card(parsed, item["gold"])
        if card["must_say"]:
            return card
        last_error = "empty_must_say"
    raise ValueError(last_error)


def _load_queue(path: Path) -> dict[str, dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    if not path.is_file():
        return by_id
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        if isinstance(rec, dict) and rec.get("id"):
            by_id[str(rec["id"])] = rec
    return by_id


def _write_queue(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for rec in rows:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-dir", type=Path, default=SEED_DIR)
    parser.add_argument("--out", type=Path, default=QUEUE_PATH)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--resume", action="store_true", help="Skip ids already in queue")
    parser.add_argument("--sleep", type=float, default=0.15)
    args = parser.parse_args()

    sliced = slice_seed(args.seed_dir)
    if args.limit > 0:
        sliced = sliced[: args.limit]
    existing = _load_queue(args.out) if args.resume or args.out.is_file() else {}
    print(f"sliced {len(sliced)} turns from {args.seed_dir}", flush=True)

    rows: list[dict[str, Any]] = []
    seen_order: list[str] = []
    for item in sliced:
        rid = item["id"]
        prev = existing.get(rid)
        prev_card = prev.get("card") if prev else None
        has_card = (
            isinstance(prev_card, dict)
            and isinstance(prev_card.get("must_say"), list)
            and bool(prev_card.get("must_say"))
        )
        if args.resume and prev and has_card:
            rows.append(prev)
            seen_order.append(rid)
            continue
        print(f"draft {rid} ...", flush=True)
        try:
            card = draft_card(item)
            rec = {
                **item,
                "card": card,
                "verdict": "",
                "reasons": [],
                "status": "pending",
                "flags": [],
            }
        except Exception as exc:
            rec = {
                **item,
                "card": {},
                "verdict": "fail",
                "reasons": [f"draft_error:{exc}"],
                "status": "pending",
                "flags": ["draft_error"],
            }
            print(f"  FAIL {rid}: {exc}", flush=True)
        rows.append(rec)
        seen_order.append(rid)
        _write_queue(args.out, rows + [existing[k] for k in existing if k not in seen_order])
        if args.sleep > 0:
            time.sleep(args.sleep)

    leftover = [existing[k] for k in existing if k not in seen_order]
    _write_queue(args.out, rows + leftover)
    print(f"Wrote {len(rows) + len(leftover)} -> {args.out}", flush=True)


if __name__ == "__main__":
    main()
