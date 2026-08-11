"""Smoke: multi-turn greeting stickiness + Arona picks one topic to open.

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
CHOICE_RE = re.compile(r"老师想聊.+还是")


def _must_blob(card) -> str:
    return " | ".join(card.must_say)


def _requires_greeting(card) -> bool:
    blob = _must_blob(card)
    return any(
        re.search(rf"用[「『]?{w}[」』]?回应", blob) or blob.strip() == w
        for w in GREETING_WORDS
    )


def _has_concrete_topic(joined: str) -> bool:
    keys = ("草莓", "基沃托斯", "牛奶", "开心", "趣事", "见闻", "工作", "待办", "休息")
    return any(k in joined for k in keys) or ("先聊" in joined) or ("开聊" in joined)


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
            "expect_open_topic": False,
        },
        {
            "user": "今天没什么计划。",
            "expect_greeting": False,
            "expect_open_topic": False,
            "forbid_reply_greeting": True,
        },
        {
            "user": "那聊些什么呢？",
            "expect_greeting": False,
            "expect_open_topic": True,
        },
        {
            "user": "阿罗那想要聊什么？",
            "expect_greeting": False,
            "expect_open_topic": True,
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

        if turn["expect_open_topic"]:
            joined = _must_blob(card)
            if not _has_concrete_topic(joined):
                print("FAIL must_say lacks concrete open topic:", card.must_say)
                failed += 1
            if any("供老师选择" in s or "几个话题选项" in s for s in card.must_say):
                print("FAIL must_say still plans a menu for teacher:", card.must_say)
                failed += 1
            not_blob = " | ".join(card.must_not)
            if "还是" not in not_blob and "选择题" not in not_blob and "抛回" not in not_blob:
                print("WARN must_not may lack choice-ban:", card.must_not)
            if any("老师想聊什么" in s for s in card.must_say):
                print("FAIL must_say bounces to teacher")
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
            if turn["expect_open_topic"]:
                if CHOICE_RE.search(reply) or ("还是" in reply and "老师想聊" in reply):
                    print("FAIL reply is choice bounce:", reply)
                    failed += 1
                if "话题单" in reply or "列个话题" in reply or "列几个" in reply:
                    print("FAIL reply claims topic list without opening:", reply)
                    failed += 1
                if reply.strip() in {"老师想聊什么呀？", "老师想聊什么呢？"}:
                    print("FAIL empty bounce:", reply)
                    failed += 1

        history.append({"role": "user", "content": user})
        history.append(
            {
                "role": "assistant",
                "content": reply
                or (
                    "（占位回复）"
                    if not turn["expect_open_topic"]
                    else "阿洛娜想先跟老师聊聊草莓牛奶呀~"
                ),
            }
        )

    print(f"\nDone. failures={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(amain()))
