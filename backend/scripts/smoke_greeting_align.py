"""Smoke: greeting time-of-day alignment for Planner (+ optional GGUF render).

Usage:
  python backend/scripts/smoke_greeting_align.py
  python backend/scripts/smoke_greeting_align.py --generate
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.config import load_config  # noqa: E402
from app.planner import PlannerClient  # noqa: E402
from app.prompt import RENDERER_SYSTEM, build_renderer_messages  # noqa: E402

CASES = [
    {
        "id": "evening",
        "user": "晚上好啊，罗娜。",
        "must_contain": ["晚上好"],
        "must_not_contain": ["晚安"],
    },
    {
        "id": "morning",
        "user": "早上好，阿洛娜",
        "must_contain": ["早上好"],
        "must_not_contain": ["晚安", "晚上好"],
    },
    {
        "id": "goodnight",
        "user": "晚安",
        "must_contain": ["晚安"],
        "must_not_contain": [],
    },
]


async def amain() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Also run AronaLM renderer (loads GGUF)",
    )
    args = parser.parse_args()

    config = load_config()
    planner = PlannerClient(config.planner)
    if not planner.enabled:
        print("planner disabled / no API key")
        return 1

    sample = build_renderer_messages(config, draft="测试草稿")
    sys_content = sample[0]["content"]
    assert "【身份锚定】" not in sys_content
    assert "意图草稿" in RENDERER_SYSTEM or "【意图草稿】" in sample[1]["content"]
    print("renderer system ok (draft v24)")

    model = None
    if args.generate:
        from app.model_loader import get_model_loader

        model = get_model_loader()
        print("Loading GGUF...")
        model.load(config)

    fake_memories = ["老师邀请阿洛娜一起外出"]
    failed = 0

    for case in CASES:
        print(f"\n=== {case['id']}: {case['user']!r} ===")
        card = await planner.plan(
            user_text=case["user"],
            history=[],
            memories=fake_memories,
            knowledge=[],
        )
        if card is None:
            print("FAIL planner returned None")
            failed += 1
            continue

        payload = {
            "draft": card.to_renderer_draft(),
            "arona_emotion": card.arona_emotion,
            "followup_ok": card.followup_ok,
        }
        print("intent:", json.dumps(payload, ensure_ascii=False))
        draft = card.to_renderer_draft()

        for needle in case["must_contain"]:
            if needle not in draft:
                print(f"FAIL draft missing {needle!r}: {draft!r}")
                failed += 1
        for bad in case["must_not_contain"]:
            if bad in draft:
                print(f"FAIL draft contains banned {bad!r}: {draft!r}")
                failed += 1

        if model is not None:
            messages = build_renderer_messages(config, draft=draft)
            reply = await asyncio.to_thread(model.generate, messages, config)
            print("reply:", reply)
            for needle in case["must_contain"]:
                if needle not in reply:
                    print(f"FAIL reply missing {needle!r}")
                    failed += 1
            for bad in case["must_not_contain"]:
                if bad in reply:
                    print(f"FAIL reply contains {bad!r}")
                    failed += 1

    print(f"\nDone. failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(amain()))
