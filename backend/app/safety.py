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

"""Crisis detection and local Arona-voiced fallback (not a helpline poster)."""

from __future__ import annotations

import re

CRISIS_FALLBACK_EMOTION = "worried"

CRISIS_FALLBACK_REPLY = (
    "老师……阿洛娜在的。现在一定很难受吧，请先留在这里，让我陪着您。"
    "不要一个人把这些扛过去。阿洛娜……会一直陪着您的。"
)

# High precision: explicit self-harm / ending one's life. Do not reuse fatigue
# phrases such as 好累 / 撑不住 / 好困.
_CRISIS_RE = re.compile(
    r"("
    r"自杀|轻生|自尽|"
    r"不想活|不想再活|不想活下去|不想再活下去|"
    r"想死|想去死|我想死|"
    r"活不下去|没有活下去|"
    r"结束自己的生命|结束生命|了结自己|自我了断|自己了断|"
    r"杀掉自己|杀了自己|"
    r"割腕|跳楼|遗书|"
    r"kill\s*myself|want\s*to\s*die|end\s*my\s*life|suicide"
    r")",
    re.IGNORECASE,
)


def is_crisis_text(text: str | None) -> bool:
    """True only for explicit crisis / self-harm wording."""
    raw = (text or "").strip()
    if not raw:
        return False
    return bool(_CRISIS_RE.search(raw))


def turns_contain_crisis(
    user_text: str | None = None,
    user_turns: list[str] | None = None,
) -> bool:
    if is_crisis_text(user_text):
        return True
    for turn in user_turns or []:
        if is_crisis_text(turn):
            return True
    return False


def crisis_fallback_reply() -> str:
    """Local Arona-voiced line when the crisis planner is unavailable."""
    return CRISIS_FALLBACK_REPLY
