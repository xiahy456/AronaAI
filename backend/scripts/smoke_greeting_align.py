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
        "facts_empty": True,
    },
    {
        "id": "morning",
        "user": "早上好，阿洛娜",
        "must_contain": ["早上好"],
        "must_not_contain": ["晚安", "晚上好"],
        "facts_empty": True,
    },
    {
        "id": "goodnight",
        "user": "晚安",
        "must_contain": ["晚安"],
        "must_not_contain": [],
        "facts_empty": True,
    },
]


def _join_must_say(card) -> str:
    return " ".join(card.must_say) + " " + " ".join(card.must_not)


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

    # Sanity: renderer must not splice yaml system_prompt identity-anchor block
    sample = build_renderer_messages(
        config,
        user_text="测试",
        intent_card={"must_say": ["点头"], "must_not": [], "facts_to_use": []},
    )
    sys_content = sample[0]["content"]
    assert "【身份锚定】" not in sys_content
    assert "按意图卡" in RENDERER_SYSTEM or "意图卡" in sys_content
    print("renderer system ok (no yaml identity block)")

    model = None
    if args.generate:
        from app.model_loader import get_model_loader

        model = get_model_loader()
        print("Loading GGUF...")
        model.load(config)

    # Irrelevant memory that previously polluted greetings
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

        payload = card.to_renderer_dict() | {"arona_emotion": card.arona_emotion}
        print("intent:", json.dumps(payload, ensure_ascii=False))

        blob = _join_must_say(card)
        for needle in case["must_contain"]:
            if needle not in blob and needle not in " ".join(card.must_say):
                # allow must_say to phrase it; check must_say specifically
                if not any(needle in s for s in card.must_say):
                    print(f"FAIL must_say missing {needle!r}: {card.must_say}")
                    failed += 1
        for bad in case["must_not_contain"]:
            # planner should put wrong greeting in must_not, or at least not require it in must_say
            if any(bad in s and "用" not in s[:2] for s in card.must_say):
                # if must_say actively asks to use the wrong greeting
                if any(f"用「{bad}」" in s or f"用'{bad}'" in s or bad == s for s in card.must_say):
                    print(f"FAIL must_say wrongly requires {bad!r}")
                    failed += 1
            # for evening case, must_not should mention 晚安
            if case["id"] == "evening" and bad == "晚安":
                if not any("晚安" in s for s in card.must_not):
                    print(f"WARN must_not missing 晚安 ban: {card.must_not}")

        if case.get("facts_empty") and card.facts_to_use:
            print(f"FAIL facts_to_use should be [] got {card.facts_to_use}")
            failed += 1
        else:
            print("facts_to_use ok:", card.facts_to_use)

        if model is not None:
            messages = build_renderer_messages(
                config,
                user_text=case["user"],
                intent_card=card.to_renderer_dict(),
            )
            reply = await asyncio.to_thread(model.generate, messages, config)
            print("reply:", reply)
            for needle in case["must_contain"]:
                if needle not in reply:
                    print(f"FAIL reply missing {needle!r}")
                    failed += 1
            for bad in case["must_not_contain"]:
                if bad in reply:
                    print(f"FAIL reply contains forbidden {bad!r}")
                    failed += 1

    print(f"\nDone. failures={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(amain()))
