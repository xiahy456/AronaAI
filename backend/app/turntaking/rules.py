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

"""Fast, explainable addressee / end-of-turn rules."""

from __future__ import annotations

import re
from dataclasses import dataclass

ACTION_IGNORE = "ignore"
ACTION_WAIT = "wait"
ACTION_REPLY = "reply"

_NAME_RE = re.compile(r"阿洛娜|Arona|ARONA|arona|助手")
_INCOMPLETE_RE = re.compile(
    r"(然后|就是|那个|嗯+|额+|呃+|因为|所以|还有|以及)[。.…·、，,]*$"
)
_QUESTION_RE = re.compile(r"[吗呢吧么？?]$|能不能|可不可以|要不要|是不是")
_IMPERATIVE_RE = re.compile(r"(帮我|给我|告诉我|提醒我|记一下|查一下|你觉得|你会|你能)")
_OTHER_ADDRESSEE_RE = re.compile(
    r"(跟他|跟她|跟他们|你去|电话|接通|喂[,，]?\s*你好|稍等我跟)"
)
_TRAILING_PAUSE_RE = re.compile(r"[…·]{2,}$|…$")


@dataclass(frozen=True)
class RuleDecision:
    action: str
    reason: str
    confidence: str  # high | low
    addressed: bool
    incomplete: bool


def looks_incomplete(text: str) -> bool:
    cleaned = (text or "").strip()
    if not cleaned:
        return False
    if _INCOMPLETE_RE.search(cleaned):
        return True
    if _TRAILING_PAUSE_RE.search(cleaned):
        return True
    return cleaned.endswith(("，", ",", "、"))


def is_addressed_to_arona(text: str) -> bool:
    return bool(_NAME_RE.search(text or ""))


def has_other_addressee(text: str) -> bool:
    return bool(_OTHER_ADDRESSEE_RE.search(text or ""))


def decide_rules(
    *,
    text: str,
    seconds_since_arona: float | None,
    continuation_window_sec: float,
    already_waited: bool = False,
) -> RuleDecision:
    cleaned = (text or "").strip()
    if not cleaned:
        return RuleDecision(ACTION_IGNORE, "empty", "high", False, False)

    addressed = is_addressed_to_arona(cleaned)
    incomplete = looks_incomplete(cleaned)
    continuation = (
        seconds_since_arona is not None
        and seconds_since_arona <= float(continuation_window_sec)
    )
    other_person = has_other_addressee(cleaned) and not addressed
    question = bool(_QUESTION_RE.search(cleaned))
    imperative = bool(_IMPERATIVE_RE.search(cleaned))

    if other_person:
        return RuleDecision(ACTION_IGNORE, "other_addressee", "high", False, incomplete)

    if incomplete and not already_waited:
        return RuleDecision(
            ACTION_WAIT,
            "incomplete",
            "high",
            addressed or continuation or imperative,
            True,
        )

    if addressed:
        return RuleDecision(ACTION_REPLY, "name", "high", True, incomplete)

    if continuation:
        return RuleDecision(ACTION_REPLY, "continuation", "high", True, incomplete)

    if imperative:
        return RuleDecision(ACTION_REPLY, "imperative", "low", True, incomplete)

    if question:
        return RuleDecision(ACTION_IGNORE, "undirected_question", "low", False, incomplete)

    return RuleDecision(ACTION_IGNORE, "not_addressed", "low", False, incomplete)
