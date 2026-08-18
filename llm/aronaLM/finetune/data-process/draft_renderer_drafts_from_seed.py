#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reverse-draft V2.4 training queue from handwritten seed gold lines.

Parses seed dialog (human+gpt) and monologue (gpt-only). Calls DeepSeek with
the locked §2.2 prompts. Writes data/raw/normal/review/queue_v24.jsonl.

  python data-process/draft_renderer_drafts_from_seed.py
  python data-process/draft_renderer_drafts_from_seed.py --limit 8
  python data-process/draft_renderer_drafts_from_seed.py --resume
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from llm_client import chat_json  # noqa: E402

FINETUNE_ROOT = Path(__file__).resolve().parent.parent
SEED_DIR = FINETUNE_ROOT / "data" / "raw" / "normal" / "seed"
REVIEW_DIR = FINETUNE_ROOT / "data" / "raw" / "normal" / "review"
QUEUE_PATH = REVIEW_DIR / "queue_v24.jsonl"

# Locked §2.2 — must stay byte-aligned with the V2.4 plan.
DRAFT_SYSTEM = """你在为「草稿→改写」训练造数据：金标是阿洛娜对老师说的话，根据阿洛娜已有的金标台词，反写出一句中性的意图草稿。
草稿会交给小模型改写成阿洛娜口吻；因此草稿必须保留全部意思，但去掉撒娇、结巴和标志性口吻。

要求：
1. 只输出一个 JSON：{"draft": "..."}
2. draft 必须是 1–2 句完整中文，已经能当普通人说的话发表；禁止提纲（如「表示陪伴并提议喝茶」）。
3. 意思与金标一致：该问的仍问，该拒的仍拒，事实不增不减；不要比金标多编情节。
4. 口吻：略平、略书面；去掉「呀」「呢」「哦~」等撒娇；去掉「那、那…」结巴；可保留「老师」称呼。
5. 不要复述金标原文到几乎一字不差；也不要改成完全另一套意思。
6. 不要输出阿洛娜腔表演说明、系统事件、关系数值、思考过程或 Markdown。
"""

_OUTLINE_RE = re.compile(
    r"^(表示|表明|说明|回应|表达|提出|询问|强调|承认|拒绝|安慰|邀请)"
)
_PUNCT_RE = re.compile(r"[\s。！？!?~～、，,.\-…「」『』\"'“”‘’（）()【】\[\]·•]")


def _norm(text: str) -> str:
    return _PUNCT_RE.sub("", (text or "").strip()).lower()


def _sentence_count(text: str) -> int:
    t = (text or "").strip()
    if not t:
        return 0
    parts = [p for p in re.split(r"(?<=[。！？!?~～])\s*", t) if p.strip()]
    return len(parts) if parts else 1


def _mechanical_notes(draft: str, gold: str) -> list[str]:
    notes: list[str] = []
    d = (draft or "").strip()
    g = (gold or "").strip()
    if not d:
        notes.append("empty_draft")
        return notes
    if _OUTLINE_RE.match(d) and "。" not in d and "？" not in d and "?" not in d:
        notes.append("outline_like")
    if _sentence_count(d) > 2:
        notes.append("too_many_sentences")
    nd, ng = _norm(d), _norm(g)
    if nd and ng and (nd == ng or nd in ng or ng in nd):
        # Near-identity / containment after stripping punct.
        if abs(len(nd) - len(ng)) <= max(2, int(0.08 * max(len(nd), len(ng)))):
            notes.append("near_identity")
        elif nd == ng:
            notes.append("near_identity")
    return notes


def slice_seed(seed_dir: Path) -> list[dict[str, Any]]:
    """Extract one gold (last gpt) per seed record; optional last human as user_text."""
    items: list[dict[str, Any]] = []
    for path in sorted(seed_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            continue
        for src_i, rec in enumerate(data):
            conv = rec.get("conversations") if isinstance(rec, dict) else None
            if not isinstance(conv, list):
                continue
            last_human = ""
            last_gpt = ""
            for turn in conv:
                if not isinstance(turn, dict):
                    continue
                role = turn.get("from")
                val = str(turn.get("value") or "").strip()
                if not val:
                    continue
                if role == "human":
                    last_human = val
                elif role == "gpt":
                    last_gpt = val
            if not last_gpt:
                continue
            fmt = "dialog" if last_human else "monologue"
            items.append(
                {
                    "id": f"{path.name}#{src_i}",
                    "source": path.name,
                    "source_index": src_i,
                    "user_text": last_human,
                    "gold": last_gpt,
                    "format": fmt,
                }
            )
    return items


def build_user_prompt(user_text: str, gold: str) -> str:
    if (user_text or "").strip():
        return (
            f"【老师原话】（仅供理解语境，不要写进 draft）\n{user_text.strip()}\n\n"
            f"【阿洛娜金标台词】\n{gold.strip()}\n\n"
            '请输出 JSON：{"draft": "1–2句中性意图草稿"}'
        )
    return (
        f"【阿洛娜金标台词】\n{gold.strip()}\n\n"
        "（无老师原话。只根据金标反写草稿。）\n"
        '请输出 JSON：{"draft": "1–2句中性意图草稿"}'
    )


def reverse_draft(user_text: str, gold: str) -> str:
    parsed = chat_json(
        system=DRAFT_SYSTEM,
        user=build_user_prompt(user_text, gold),
        temperature=0.3,
        max_tokens=400,
    )
    if not isinstance(parsed, dict):
        raise ValueError("draft response not an object")
    draft = str(parsed.get("draft") or "").strip()
    if not draft:
        raise ValueError("empty_draft")
    return draft


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
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--sleep", type=float, default=0.15)
    args = parser.parse_args()

    items = slice_seed(args.seed_dir)
    if args.limit > 0:
        items = items[: args.limit]
    existing = _load_queue(args.out) if args.resume else {}
    rows: list[dict[str, Any]] = []
    done_ids = set(existing.keys()) if args.resume else set()

    print(f"seed items={len(items)} resume={args.resume} existing={len(existing)}")
    for i, item in enumerate(items):
        rid = str(item["id"])
        if rid in done_ids and rid in existing:
            rows.append(existing[rid])
            continue
        try:
            draft = reverse_draft(item["user_text"], item["gold"])
            notes = _mechanical_notes(draft, item["gold"])
            rec = {
                "id": rid,
                "gold": item["gold"],
                "draft": draft,
                "user_text": item["user_text"],
                "source": item["source"],
                "format": item["format"],
                "status": "",
                "notes": ";".join(notes),
            }
            rows.append(rec)
            print(
                f"[{i + 1}/{len(items)}] {rid} fmt={item['format']} "
                f"notes={rec['notes'] or '-'} draft={draft[:40]}…"
            )
        except Exception as exc:
            rec = {
                "id": rid,
                "gold": item["gold"],
                "draft": "",
                "user_text": item["user_text"],
                "source": item["source"],
                "format": item["format"],
                "status": "",
                "notes": f"error:{exc}",
            }
            rows.append(rec)
            print(f"[{i + 1}/{len(items)}] FAIL {rid}: {exc}")
        if args.sleep > 0:
            time.sleep(args.sleep)
        if (i + 1) % 10 == 0:
            _write_queue(args.out, rows)

    if args.resume:
        seen = {str(r["id"]) for r in rows}
        for rid, rec in existing.items():
            if rid not in seen:
                rows.append(rec)

    _write_queue(args.out, rows)
    flagged = sum(1 for r in rows if r.get("notes"))
    print(f"Wrote {len(rows)} -> {args.out} (notes flagged={flagged})")


if __name__ == "__main__":
    main()
