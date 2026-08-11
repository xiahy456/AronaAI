"""Smoke: multi-turn greeting stickiness + topic proposal.

Usage:
  python backend/scripts/smoke_multiturn_chat.py
  python backend/scripts/smoke_multiturn_chat.py --generate
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.config import load_config  # noqa: E402
from app.planner import PlannerClient  # noqa: E402
from app.prompt import build_renderer_messages  # noqa: E402

GREETING_WORDS = ("早上好", "下午好", "晚上好", "晚安", "早安")


def _must_blob(card) -> str:
    return " | ".join(card.must_say)


def _not_blob(card) -> str:
    return " | ".join(card.must_not)


def _requires_greeting(card) -> bool:
    blob = _must_blob(card)
    return any(
        re.search(rf"用[「『]?{w}[」』]?回应", blob) or blob.strip() == w
        for w in GREETING_WORDS
    )


async def amain() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generate", action="store_true")
    args = parser.parse_args()

    config = load_config()
    planner = PlannerClient(config.planner)
    if not planner.enabled:
        print("planner disabled / no API key")
        return 1

    model = None
    if args.generate:
        from app.model_loader import get_model_loader

        model = get_model_loader()
        print("Loading GGUF...")
        model.load(config)

    history: list[dict[str, str]] = []
    failed = 0

    turns = [
        {
            "user": "晚上好呀。",
            "expect_greeting": True,
            "expect_topics": False,
        },
        {
            "user": "今天没什么计划。",
            "expect_greeting": False,
            "expect_topics": False,
            "forbid_reply_greeting": True,
        },
        {
            "user": "那聊些什么呢？",
            "expect_greeting": False,
            "expect_topics": True,
        },
        {
            "user": "你有什么想聊的吗？",
            "expect_greeting": False,
            "expect_topics": True,
        },
    ]

    for i, turn in enumerate(turns, start=1):
        user = turn["user"]
        print(f"\n=== turn {i}: {user!r} ===")
        card = await planner.plan(
            user_text=user,
            history=history,
            memories=[],
            knowledge=[],
        )
        if card is None:
            print("FAIL planner None")
            failed += 1
            continue

        payload = card.to_renderer_dict() | {"arona_emotion": card.arona_emotion}
        print("intent:", json.dumps(payload, ensure_ascii=False))

        greets = _requires_greeting(card)
        if turn["expect_greeting"] and not greets:
            print("FAIL expected greeting must_say")
            failed += 1
        if not turn["expect_greeting"] and greets:
            print("FAIL unexpected greeting must_say:", card.must_say)
            failed += 1
        if not turn["expect_greeting"]:
            if not any("问候" in s or "晚上好" in s or "再次" in s for s in card.must_not):
                print("WARN must_not may lack anti-greeting:", card.must_not)

        if turn["expect_topics"]:
            # Concrete topic names should appear in must_say (not just 提出话题)
            joined = _must_blob(card)
            vague_only = (
                "提出" in joined
                and "草莓" not in joined
                and "基沃托斯" not in joined
                and "开心" not in joined
                and "趣事" not in joined
                and "见闻" not in joined
                and "牛奶" not in joined
            )
            # At least one must_say item should look concrete (len>8 or contains named topic)
            concrete = any(
                len(s) >= 8
                and not s.startswith("提出几个")
                and "话题选项" not in s
                for s in card.must_say
            ) or any(
                k in joined
                for k in ("草莓", "基沃托斯", "牛奶", "开心", "趣事", "见闻", "今天")
            )
            if vague_only or not concrete:
                # Soft fail if no concrete token — still count as fail per plan
                print("FAIL must_say lacks concrete topics:", card.must_say)
                failed += 1
            bounce = any("老师想聊什么" in s for s in card.must_say)
            if bounce:
                print("FAIL must_say asks teacher to choose without topics")
                failed += 1

        reply = ""
        if model is not None:
            messages = build_renderer_messages(
                config,
                user_text=user,
                intent_card=card.to_renderer_dict(),
                history=history,
            )
            reply = await asyncio.to_thread(model.generate, messages, config)
            print("reply:", reply)
            if turn.get("forbid_reply_greeting"):
                if any(w in reply[:12] for w in ("早上好", "下午好", "晚上好", "晚安")):
                    print("FAIL reply starts with greeting:", reply)
                    failed += 1
            if turn["expect_topics"]:
                # Should list something concrete; not only bounce
                if "老师想聊什么" in reply and not any(
                    k in reply for k in ("草莓", "基沃托斯", "牛奶", "开心", "趣事", "见闻", "还是")
                ):
                    print("FAIL reply only bounces question:", reply)
                    failed += 1
                if "列几个" in reply and "、" not in reply and "或者" not in reply:
                    print("FAIL reply claims to list but does not:", reply)
                    failed += 1

        history.append({"role": "user", "content": user})
        history.append(
            {
                "role": "assistant",
                "content": reply
                or ("（占位回复）" if not turn["expect_topics"] else "要不要聊聊草莓牛奶呀~"),
            }
        )

    print(f"\nDone. failures={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(amain()))
