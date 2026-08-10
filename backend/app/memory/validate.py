"""Deterministic quality checks before persisting memories."""

from __future__ import annotations

import re

_MIN_CONTENT_LEN = 4

# Ends like a question / soft interrogative particle.
_QUESTION_END = re.compile(r"[？?吗呢]\s*$")

# Clear interrogative / undecided structures in Chinese memory text.
_INTERROGATIVE = re.compile(
    r"(什么|哪个|哪些|哪位|谁|怎么|如何|是否|有没有|是不是|要不要|好不好)"
)

# Content that is only punctuation / placeholders.
_ONLY_NOISE = re.compile(r"^[\s\-_.…·,，。！!？?~～、；;：:]+$")


def memory_reject_reason(key: str, content: str) -> str | None:
    """Return a short reject reason, or None if the memory is acceptable."""
    _ = key  # reserved for future key-based rules
    text = (content or "").strip()
    if not text:
        return "empty"
    if len(text) < _MIN_CONTENT_LEN:
        return "too_short"
    if _ONLY_NOISE.match(text):
        return "noise_only"
    if _QUESTION_END.search(text):
        return "question_like"
    if _INTERROGATIVE.search(text):
        return "interrogative"
    return None


def is_valid_memory(key: str, content: str) -> bool:
    return memory_reject_reason(key, content) is None
