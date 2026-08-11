"""Regex fallback memory extraction when DeepSeek is unavailable."""

from __future__ import annotations

import re
from typing import Any

from .normalize import COLOR_TOKEN, normalize_memory_item
from .validate import is_valid_memory

_INTERROGATIVE_VALUE = re.compile(r"(什么|哪个|哪些|哪位|谁|怎么|如何|是否|有没有|是不是)")

# (pattern, key, template) — order matters; more specific first.
_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"我叫\s*([^\s，。！？,?吗呢.!?\n～~]{1,12})"), "user_name", "老师的名字是{0}"),
    (re.compile(r"我的名字是\s*([^\s，。！？,?吗呢.!?\n～~]{1,12})"), "user_name", "老师的名字是{0}"),
    (
        re.compile(r"(?:我的)?生日(?:是|在)\s*([^\s，。！？,?吗呢.!?\n]{2,20})"),
        "user_birthday",
        "老师的生日是{0}",
    ),
    (
        re.compile(rf"(?:我)?(?:比较|更|最|改成|换成)?喜欢\s*({COLOR_TOKEN})"),
        "preference_color",
        "老师喜欢{0}",
    ),
    (
        re.compile(rf"我不喜欢\s*({COLOR_TOKEN})"),
        "preference_color",
        "老师不喜欢{0}",
    ),
    (
        re.compile(r"(?:我)?(?:比较|更|最|改成|换成)?喜欢\s*([^，。！？,?吗呢.!?\n]{1,20})"),
        "preference_like",
        "老师喜欢{0}",
    ),
    (re.compile(r"我不喜欢\s*([^，。！？,?吗呢.!?\n]{1,20})"), "preference_dislike", "老师不喜欢{0}"),
    (re.compile(r"请记住[：:，,\s]*(.+)"), "explicit_note", "老师希望记住：{0}"),
]


def regex_extract_memories(user_text: str) -> list[dict[str, Any]]:
    text = (user_text or "").strip()
    if not text:
        return []

    results: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for pattern, key, template in _PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        value = match.group(1).strip().rstrip("。！？!?!~～吗呢")
        if not value or _INTERROGATIVE_VALUE.search(value):
            continue
        content = template.format(value)
        item = normalize_memory_item(
            {
                "op": "upsert",
                "key": key,
                "content": content,
                "category": "preference" if "preference" in key else "profile",
            }
        )
        nkey = str(item.get("key") or "")
        ncontent = str(item.get("content") or "")
        if not is_valid_memory(nkey, ncontent):
            continue
        if nkey in seen_keys:
            continue
        seen_keys.add(nkey)
        results.append(item)
    return results
