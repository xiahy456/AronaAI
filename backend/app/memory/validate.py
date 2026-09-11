# Copyright 2026 xia_hy456. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
