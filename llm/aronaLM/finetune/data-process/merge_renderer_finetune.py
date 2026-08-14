#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Merge human-accepted renderer samples into training JSONL.

Default: review/queue.jsonl (accepted|edited) + review/contrast.jsonl.
Does not mix uncarded persona. Old curated/synth files are opt-in only.

  python data-process/merge_renderer_finetune.py
  python data-process/merge_renderer_finetune.py --include-legacy
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from renderer_format import make_sample  # noqa: E402

FINETUNE_ROOT = Path(__file__).resolve().parent.parent
REVIEW_DIR = FINETUNE_ROOT / "data" / "raw" / "normal" / "review"
CHOSEN_DIR = FINETUNE_ROOT / "data" / "raw" / "normal" / "chosen"
OUT_DIR = FINETUNE_ROOT / "data" / "finetune_training"

LEGACY_FILES = (
    "renderer_curated.json",
    "renderer_synth_v2.json",
    "renderer_intent.json",
)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        if isinstance(rec, dict):
            rows.append(rec)
    return rows


def _from_review(rec: dict[str, Any]) -> dict[str, Any] | None:
    status = str(rec.get("status") or "").strip()
    if status not in {"accepted", "edited"}:
        return None
    user = str(rec.get("user_text") or "").strip()
    gold = str(rec.get("gold") or "").strip()
    card = rec.get("card")
    if not user or not gold or not isinstance(card, dict) or not card:
        return None
    if rec.get("conversations"):
        return {
            "conversations": rec["conversations"],
            "id": rec.get("id"),
        }
    sample = make_sample(user, card, gold)
    if rec.get("id"):
        sample["id"] = rec["id"]
    return sample


def _dedup(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in items:
        key = json.dumps(item.get("conversations"), ensure_ascii=False, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def merge(
    *,
    include_legacy: bool = False,
    persona_max: int = 0,
) -> int:
    items: list[dict[str, Any]] = []
    pending = 0
    for name in ("queue.jsonl", "contrast.jsonl"):
        path = REVIEW_DIR / name
        rows = _read_jsonl(path)
        kept = 0
        for rec in rows:
            sample = _from_review(rec)
            if sample:
                items.append(sample)
                kept += 1
            elif str(rec.get("status") or "pending") == "pending":
                pending += 1
        print(f"  {name}: {kept}/{len(rows)} accepted")
    if pending:
        print(f"  NOTE: {pending} pending left in review; merge skips them until accepted/edited")

    if include_legacy:
        for name in LEGACY_FILES:
            path = CHOSEN_DIR / name
            if not path.is_file():
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            n = 0
            for rec in data if isinstance(data, list) else []:
                if isinstance(rec, dict) and rec.get("conversations"):
                    items.append(rec)
                    n += 1
            print(f"  legacy {name}: {n}")

    if persona_max > 0:
        print(f"WARNING: persona_max={persona_max} ignored; renderer mix is card-only")

    items = _dedup(items)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "renderer_finetune.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"Wrote {len(items)} -> {out_path}")
    return len(items)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include-legacy", action="store_true")
    parser.add_argument("--persona-max", type=int, default=0)
    args = parser.parse_args()
    merge(include_legacy=args.include_legacy, persona_max=args.persona_max)


if __name__ == "__main__":
    main()
