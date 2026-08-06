"""Heuristic triggers for memory extraction (W2/W5)."""

from __future__ import annotations

import re

# Explicit remember
_EXPLICIT = re.compile(r"(请记住|记住这个|帮我记住|不要忘记)")

# First-person fact-ish patterns
_FACTISH = re.compile(
    r"(我叫|我的名字|我是|我姓|"
    r"我喜欢|我不喜欢|我讨厌|我爱|"
    r"我住|我家|我在|"
    r"我的爱好|我的生日|我今年|"
    r"记得我|以后叫我|称呼我)"
)


def should_extract(user_text: str, *, turn_count: int, every_n_turns: int) -> bool:
    text = (user_text or "").strip()
    if not text:
        return False
    if _EXPLICIT.search(text):
        return True
    if _FACTISH.search(text):
        return True
    if every_n_turns > 0 and turn_count > 0 and turn_count % every_n_turns == 0:
        return True
    return False
