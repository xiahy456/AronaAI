"""Shared helpers for Renderer training sample format (aligned with production)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
RENDERER_SYSTEM_FILE = PROMPTS_DIR / "renderer_system.txt"

USER_TAIL = (
    "请严格按意图卡回复老师（1–3句）。若需开聊，请选定话题直接说，"
    "不要用「还是」把选择抛回老师。"
)

BASE_MUST_NOT = [
    "说教",
    "自称其他AI",
    "长篇列表",
    "复述意图卡",
]


def load_renderer_system() -> str:
    return RENDERER_SYSTEM_FILE.read_text(encoding="utf-8").strip()


def strip_emotion(card: dict[str, Any]) -> dict[str, Any]:
    out = dict(card)
    out.pop("arona_emotion", None)
    return out


def format_human(user_text: str, card: dict[str, Any]) -> str:
    card_text = json.dumps(strip_emotion(card), ensure_ascii=False)
    return (
        f"【回复意图卡】\n{card_text}\n\n"
        f"【老师原话】\n{user_text.strip()}\n\n"
        f"{USER_TAIL}"
    )


def make_sample(user_text: str, card: dict[str, Any], reply: str) -> dict[str, Any]:
    """ShareGPT sample with system + human + gpt."""
    return {
        "conversations": [
            {"from": "system", "value": load_renderer_system()},
            {"from": "human", "value": format_human(user_text, card)},
            {"from": "gpt", "value": reply.strip()},
        ]
    }


def make_card(
    *,
    user_emotion: str,
    topic: str,
    stance: str,
    must_say: list[str],
    must_not: list[str] | None = None,
    facts_to_use: list[str] | None = None,
    tone: str = "温柔活泼短句",
    length: str = "1-3句",
) -> dict[str, Any]:
    mn = list(BASE_MUST_NOT)
    for item in must_not or []:
        if item not in mn:
            mn.append(item)
    return {
        "user_emotion": user_emotion,
        "topic": topic,
        "stance": stance,
        "must_say": must_say,
        "must_not": mn,
        "facts_to_use": list(facts_to_use or []),
        "tone": tone,
        "length": length,
    }
