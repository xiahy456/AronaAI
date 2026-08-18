#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Merge accepted/edited queue_v24 rows into renderer_finetune_v24.jsonl.

Does not touch renderer_finetune.jsonl (V2.3).

  python data-process/merge_renderer_v24.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from renderer_format import make_rewrite_sample  # noqa: E402

FINETUNE_ROOT = Path(__file__).resolve().parent.parent
REVIEW_DIR = FINETUNE_ROOT / "data" / "raw" / "normal" / "review"
OUT_DIR = FINETUNE_ROOT / "data" / "finetune_training"
QUEUE_PATH = REVIEW_DIR / "queue_v24.jsonl"
OUT_PATH = OUT_DIR / "renderer_finetune_v24.jsonl"


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
    draft = str(rec.get("draft") or "").strip()
    gold = str(rec.get("gold") or "").strip()
    if not draft or not gold:
        return None
    sample_id = str(rec.get("id") or "") or None
    return make_rewrite_sample(draft, gold, sample_id=sample_id)


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


def merge(*, queue: Path = QUEUE_PATH, out: Path = OUT_PATH) -> int:
    rows = _read_jsonl(queue)
    items: list[dict[str, Any]] = []
    pending = 0
    rejected = 0
    for rec in rows:
        sample = _from_review(rec)
        if sample:
            items.append(sample)
        else:
            st = str(rec.get("status") or "").strip()
            if st == "rejected":
                rejected += 1
            else:
                pending += 1
    items = _dedup(items)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"  queue_v24: {len(items)}/{len(rows)} accepted|edited")
    if pending:
        print(f"  NOTE: {pending} pending/empty status; skipped until accepted/edited")
    if rejected:
        print(f"  rejected: {rejected}")
    print(f"Wrote {len(items)} -> {out}")
    return len(items)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, default=QUEUE_PATH)
    parser.add_argument("--out", type=Path, default=OUT_PATH)
    args = parser.parse_args()
    merge(queue=args.queue, out=args.out)


if __name__ == "__main__":
    main()
