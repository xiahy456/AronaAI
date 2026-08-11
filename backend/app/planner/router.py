"""Route simple turns to local AronaLM; complex turns to dual planner path."""

from __future__ import annotations

import re

# Exact / near-exact greetings and identity probes → local only.
_SIMPLE_EXACT = frozenset(
    {
        "你好",
        "您好",
        "嗨",
        "哈喽",
        "hello",
        "hi",
        "早上好",
        "早安",
        "中午好",
        "下午好",
        "晚上好",
        "晚安",
        "再见",
        "拜拜",
        "阿洛娜",
        "阿罗娜",
        "在吗",
        "在不在",
        "你是谁",
        "你叫什么",
        "你叫什么名字",
        "介绍一下你自己",
        "介绍下你自己",
    }
)

_SIMPLE_RE = re.compile(
    r"^(你好呀?|您好呀?|哈喽|嗨嗨?|早呀?|晚安呀?|"
    r"阿洛娜在吗|阿罗娜在吗|"
    r"你是谁呀?|你叫什么(名字)?呀?)$"
)


def route_mode(user_text: str) -> str:
    """Return 'local' or 'dual'."""
    text = (user_text or "").strip()
    if not text:
        return "local"
    lowered = text.lower()
    if text in _SIMPLE_EXACT or lowered in _SIMPLE_EXACT:
        return "local"
    # Very short chit-chat without punctuation-heavy content
    compact = re.sub(r"[\s!~！。？?~～]+", "", text)
    if compact in _SIMPLE_EXACT or _SIMPLE_RE.match(compact):
        return "local"
    if len(compact) <= 6 and compact in {"早", "诶", "嗯", "哦", "呀"}:
        return "local"
    return "dual"
