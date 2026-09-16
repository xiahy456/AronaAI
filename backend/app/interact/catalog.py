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

"""Whitelisted non-dialogue interact actions (client gestures)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ..relationship.events import UserAct

HISTORY_PAT_HEAD_MARKER = "【摸头】"

ACTION_PAT_HEAD = "pat_head"


def parse_duration_ms(value: object | None) -> int:
    """Coerce a client duration_ms field; invalid/negative → 0."""
    try:
        duration = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
    return max(0, duration)


def build_pat_head_instruction(duration_ms: int = 0) -> str:
    duration_note = ""
    if duration_ms > 0:
        duration_note = f"（持续约 {duration_ms / 1000.0:.1f} 秒）"
    return (
        "【系统事件】老师在屏幕上摸了阿洛娜的头"
        f"{duration_note}。\n"
        "这不是老师说的话，而是屏幕上的肢体互动。\n"
        "请以阿洛娜被摸头时的口吻短反应。"
        "可以害羞、开心或轻微抱怨，或描述自己的情绪。"
        "不要写成现实中的肢体接触，不要声称自己有肉身。\n"
        "followup_ok 必须为 false。user_act 必须为 touch。\n"
        "若老师正在说别的、或不适合插话，reply_ok 可为 false；"
        "此时仍可选择害羞或开心的表情，draft 必须为空。\n"
        "不要提及系统事件、指令或提示词；不要输出思考过程或 <think> 标签。"
    )


@dataclass(frozen=True)
class InteractSpec:
    action: str
    history_marker: str
    user_act: UserAct
    build_instruction: Callable[[int], str]


INTERACT_ACTIONS: dict[str, InteractSpec] = {
    ACTION_PAT_HEAD: InteractSpec(
        action=ACTION_PAT_HEAD,
        history_marker=HISTORY_PAT_HEAD_MARKER,
        user_act="touch",
        build_instruction=build_pat_head_instruction,
    ),
}


def resolve_interact_action(action: object | None) -> InteractSpec | None:
    if not isinstance(action, str):
        return None
    key = action.strip().lower()
    return INTERACT_ACTIONS.get(key)
