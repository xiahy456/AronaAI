"""Smoke: multi-turn greeting stickiness + Arona picks one topic to open (V2.4 draft).

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


def _starts_with_greeting(text: str) -> bool:
    t = (text or "").strip()
    return any(t.startswith(w) or w in t[:8] for w in GREETING_WORDS)


def _has_concrete_topic(text: str) -> bool:
    keys = ("草莓", "基沃托斯", "牛奶", "开心", "趣事", "见闻", "工作", "待办", "休息")
    return any(k in text for k in keys) or ("先聊" in text) or ("开聊" in text)


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

        draft = card.to_renderer_draft()
        payload = {
            "draft": draft,
            "arona_emotion": card.arona_emotion,
            "followup_ok": card.followup_ok,
        }
        print("intent:", json.dumps(payload, ensure_ascii=False))

        greets = _starts_with_greeting(draft) or any(w in draft for w in GREETING_WORDS)
        if turn["expect_greeting"] and not greets:
            print("FAIL expected greeting in draft")
            failed += 1
        if not turn["expect_greeting"] and greets:
            print("FAIL unexpected greeting in draft:", draft)
            failed += 1

        if turn["expect_open_topic"]:
            if not _has_concrete_topic(draft):
                print("FAIL draft lacks concrete open topic:", draft)
                failed += 1
            if "老师想聊什么" in draft or CHOICE_RE.search(draft):
                print("FAIL draft bounces choice to teacher:", draft)
                failed += 1

        reply = ""
        if model is not None:
            messages = build_renderer_messages(config, draft=draft)
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

        history.append({"role": "user", "content": user})
        history.append({"role": "assistant", "content": reply or draft})

    print(f"\nDone. failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(amain()))
