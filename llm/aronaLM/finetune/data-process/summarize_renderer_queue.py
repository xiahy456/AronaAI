#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Summarize review/queue.jsonl for human review.

  python data-process/summarize_renderer_queue.py
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

QUEUE = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "raw"
    / "normal"
    / "review"
    / "queue.jsonl"
)


def main() -> None:
    rows = []
    for line in QUEUE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        if isinstance(rec, dict):
            rows.append(rec)

    print(f"queue {QUEUE} n={len(rows)}")
    print("status", dict(Counter(str(r.get("status") or "unset") for r in rows)))
    print("verdict", dict(Counter(str(r.get("verdict") or "unset") for r in rows)))
    flags = Counter()
    for r in rows:
        for f in r.get("flags") or []:
            flags[str(f)] += 1
    if flags:
        print("flags", dict(flags))

    bounce = []
    empty_ms = []
    toolish = []
    tool_needles = ("找到了", "已经帮您", "备份了", "归档到", "删除了", "搜索一下")
    for r in rows:
        gold = str(r.get("gold") or "")
        card = r.get("card") if isinstance(r.get("card"), dict) else {}
        ms = card.get("must_say") if isinstance(card.get("must_say"), list) else []
        if not ms:
            empty_ms.append(r.get("id"))
        if "还是" in gold and ("？" in gold or "?" in gold):
            bounce.append(r.get("id"))
        if any(n in gold for n in tool_needles):
            toolish.append(r.get("id"))
    print(f"empty must_say: {len(empty_ms)}")
    for i in empty_ms[:12]:
        print(f"  {i}")
    print(f"gold looks like A-or-B bounce: {len(bounce)}")
    for i in bounce[:20]:
        print(f"  {i}")
    print(f"gold may claim a finished tool action: {len(toolish)}")
    for i in toolish[:20]:
        print(f"  {i}")
    print("Review pending: set status accepted|edited|rejected, then merge.")


if __name__ == "__main__":
    main()
