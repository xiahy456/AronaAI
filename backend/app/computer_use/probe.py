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

"""Hardcoded phase-0 computer-use probe (move center, wait, Escape)."""

from __future__ import annotations

from .schema import ComputerUseAction

PROBE_TOKEN = "__cu_probe__"
PROBE_ALIAS = "键鼠探针"
PROBE_ALIASES = frozenset({PROBE_TOKEN, PROBE_ALIAS})

PROBE_DONE_REPLY = "键鼠探针跑完了。"
PROBE_DISABLED_REPLY = "键鼠探针未开启。"
PROBE_CANCELLED_REPLY = "键鼠探针已取消。"
PROBE_FAILED_REPLY = "键鼠探针没有跑完。"


def is_probe_text(text: str | None, token: str | None = None) -> bool:
    stripped = (text or "").strip()
    if not stripped:
        return False
    aliases = set(PROBE_ALIASES)
    extra = (token or "").strip()
    if extra:
        aliases.add(extra)
    return stripped in aliases


def probe_actions() -> list[ComputerUseAction]:
    return [
        ComputerUseAction(
            action="move",
            x=0.5,
            y=0.5,
            coord_space="normalized",
        ),
        ComputerUseAction(action="wait", ms=400),
        ComputerUseAction(action="key", combo="escape"),
    ]
