"""Regex fallback memory extraction when DeepSeek is unavailable."""

from __future__ import annotations

import re
from typing import Any

from .validate import is_valid_memory

_INTERROGATIVE_VALUE = re.compile(r"(什么|哪个|哪些|哪位|谁|怎么|如何|是否|有没有|是不是)")

_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"我叫\s*([^\s，。！？,?吗呢.!?\n～~]{1,12})"), "user_name", "老师的名字是{0}"),
    (re.compile(r"我的名字是\s*([^\s，。！？,?吗呢.!?\n～~]{1,12})"), "user_name", "老师的名字是{0}"),
    (re.compile(r"我喜欢\s*([^，。！？,?吗呢.!?\n]{1,20})"), "preference_like", "老师喜欢{0}"),
    (re.compile(r"我不喜欢\s*([^，。！？,?吗呢.!?\n]{1,20})"), "preference_dislike", "老师不喜欢{0}"),
    (re.compile(r"请记住[：:，,\s]*(.+)"), "explicit_note", "老师希望记住：{0}"),
]


def regex_extract_memories(user_text: str) -> list[dict[str, Any]]:
    text = (user_text or "").strip()
    if not text:
        return []

    results: list[dict[str, Any]] = []
    for pattern, key, template in _PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        value = match.group(1).strip().rstrip("。！？!?!~～吗呢")
        if not value or _INTERROGATIVE_VALUE.search(value):
            continue
        content = template.format(value)
        if not is_valid_memory(key, content):
            continue
        results.append(
            {
                "op": "upsert",
                "key": key,
                "content": content,
                "category": "preference" if "preference" in key else "profile",
            }
        )
    return results
