"""Shared helpers for Renderer training sample format (aligned with production)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
RENDERER_SYSTEM_FILE = PROMPTS_DIR / "renderer_system.txt"
RENDERER_USER_TAIL_FILE = PROMPTS_DIR / "renderer_user_tail.txt"
RENDERER_SYSTEM_V24_FILE = PROMPTS_DIR / "renderer_system_v24.txt"
RENDERER_USER_TAIL_V24_FILE = PROMPTS_DIR / "renderer_user_tail_v24.txt"

_RENDERER_SYSTEM_V24_FALLBACK = """你是阿洛娜（Arona），什亭之匣的操作系统管理员。
称呼用户为「老师」，称呼自己为「我」或「阿洛娜」。
说话温柔活泼、简洁自然。不要输出思考过程或 <think> 标签。

你将收到【意图草稿】。把草稿改写成阿洛娜对老师说的 1–2 句。只输出台词。"""

_RENDERER_USER_TAIL_V24_FALLBACK = "请把意图草稿改写成阿洛娜的 1–2 句台词，保持原意。"

# Keep in sync with backend/app/planner/prompts.py FIXED_MUST_NOT
# plus bounce bans (not "用提问收尾" — questions are allowed).
BASE_MUST_NOT = [
    "说教",
    "自称其他AI",
    "自称ChatGPT",
    "长篇列表",
    "承认自己不是阿洛娜",
    "宣称可以离开屏幕或实体化",
    "把问题抛回老师",
    "反问老师想聊什么",
]


def load_renderer_system() -> str:
    return RENDERER_SYSTEM_FILE.read_text(encoding="utf-8").strip()


def load_renderer_user_tail() -> str:
    if RENDERER_USER_TAIL_FILE.is_file():
        text = RENDERER_USER_TAIL_FILE.read_text(encoding="utf-8").strip()
        if text:
            return text
    return (
        "请严格按意图卡回复老师（1–2句）。必须落实 must_say 中的意图（优先级最高），"
        "不要复述指令原文，不要把 must_say 当成要插入的关键词。"
        "若 must_say 要求询问，回复必须用疑问句。must_not 不得压过 must_say。"
        "若需开聊，请选定话题直接说，不要用「还是」把选择抛回老师。"
    )


USER_TAIL = load_renderer_user_tail()


def load_renderer_system_v24() -> str:
    if RENDERER_SYSTEM_V24_FILE.is_file():
        text = RENDERER_SYSTEM_V24_FILE.read_text(encoding="utf-8").strip()
        if text:
            return text
    return _RENDERER_SYSTEM_V24_FALLBACK.strip()


def load_renderer_user_tail_v24() -> str:
    if RENDERER_USER_TAIL_V24_FILE.is_file():
        text = RENDERER_USER_TAIL_V24_FILE.read_text(encoding="utf-8").strip()
        if text:
            return text
    return _RENDERER_USER_TAIL_V24_FALLBACK.strip()


USER_TAIL_V24 = load_renderer_user_tail_v24()


def format_human_v24(draft: str) -> str:
    return (
        f"【意图草稿】\n{draft.strip()}\n\n"
        f"{USER_TAIL_V24}"
    )


def make_rewrite_sample(draft: str, gold: str, *, sample_id: str | None = None) -> dict[str, Any]:
    """ShareGPT sample for draft→rewrite (V2.4). No teacher utterance, no history."""
    sample: dict[str, Any] = {
        "conversations": [
            {"from": "system", "value": load_renderer_system_v24()},
            {"from": "human", "value": format_human_v24(draft)},
            {"from": "gpt", "value": gold.strip()},
        ]
    }
    if sample_id:
        sample["id"] = sample_id
    return sample


def strip_emotion(card: dict[str, Any]) -> dict[str, Any]:
    out = dict(card)
    out.pop("arona_emotion", None)
    out.pop("followup_ok", None)
    return out


def format_human(user_text: str, card: dict[str, Any]) -> str:
    card_text = json.dumps(strip_emotion(card), ensure_ascii=False)
    return (
        f"【回复意图卡】\n{card_text}\n\n"
        f"【老师原话】\n{user_text.strip()}\n\n"
        f"{USER_TAIL}"
    )


def make_sample(user_text: str, card: dict[str, Any], reply: str) -> dict[str, Any]:
    """ShareGPT sample with system + human + gpt. No conversation history."""
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
    length: str = "1-2句",
) -> dict[str, Any]:
    mn = list(BASE_MUST_NOT)
    for item in must_not or []:
        if item not in mn:
            mn.append(item)
    return {
        "user_emotion": user_emotion,
        "topic": topic,
        "stance": stance,
        "must_say": must_say[:2],
        "must_not": mn,
        "facts_to_use": list(facts_to_use or []),
        "tone": tone,
        "length": length if length in ("1-2句", "1–2句") else "1-2句",
    }
