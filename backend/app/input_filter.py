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

"""Reject unusable user inputs (empty / ASR SDK error strings) before chat."""

from __future__ import annotations

import re

# Soft reply when dirty ASR text is dropped at WS (does not enter history).
ASR_FALLBACK_REPLY = "刚才没听清，请再说一次～"
ASR_FALLBACK_EMOTION = "curious"

_DIRTY_SUBSTRINGS = (
    "[Tencent Speech Recognizer]",
    "Didnt recognize",
    "Didn't recognize",
    "Didnt recognize vailable content",
    "Audio data is null",
    "Request failed",
    "TencentCloud authentication",
    "TencentClout API error",
    "JSON analysis error",
)

# Whole-message English SDK / ASR error blobs
_DIRTY_FULL_RE = re.compile(
    r"^\s*\[Tencent Speech Recognizer\].+\s*$",
    re.IGNORECASE,
)


def is_unusable_user_text(content: str | None) -> bool:
    """Return True if content should not enter Planner / history."""
    if content is None:
        return True
    text = str(content).strip()
    if not text:
        return True
    lower = text.lower()
    for needle in _DIRTY_SUBSTRINGS:
        if needle.lower() in lower:
            return True
    if _DIRTY_FULL_RE.match(text):
        return True
    return False
