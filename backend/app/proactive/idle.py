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

"""Idle check-in motive: light presence after the teacher has been quiet."""

from __future__ import annotations

from datetime import datetime

from .slots import REST_SLOTS, resolve_slot

HISTORY_IDLE_MARKER = "【搭话】"

_IDLE_CLIMATE_NOTES: dict[str, str] = {
    "cling_risk": "更短，不要追问老师还在不在或是否需要你。",
    "fragile": "语气放轻，不要活泼打闹。",
    "rupture": "语气放轻，不要活泼打闹。",
}


def _elapsed(now: datetime, then: datetime | None) -> float | None:
    if then is None:
        return None
    return (now - then).total_seconds()


def should_fire_idle(
    now: datetime,
    *,
    last_user_at: datetime | None,
    last_proactive_at: datetime | None,
    last_idle_at: datetime | None = None,
    idle_count: int,
    last_user_act: str,
    after_sec: float,
    cooldown_sec: float,
    max_per_day: int,
) -> bool:
    return idle_skip_reason(
        now,
        last_user_at=last_user_at,
        last_proactive_at=last_proactive_at,
        last_idle_at=last_idle_at,
        idle_count=idle_count,
        last_user_act=last_user_act,
        after_sec=after_sec,
        cooldown_sec=cooldown_sec,
        max_per_day=max_per_day,
    ) is None and last_user_at is not None


def idle_skip_reason(
    now: datetime,
    *,
    last_user_at: datetime | None,
    last_proactive_at: datetime | None,
    last_idle_at: datetime | None = None,
    idle_count: int,
    last_user_act: str,
    after_sec: float,
    cooldown_sec: float,
    max_per_day: int,
) -> str | None:
    """Why idle cannot fire. None means it may fire (or last_user_at is missing)."""
    if last_user_at is None:
        return "no_last_user_at"
    if last_user_act == "depart":
        return "depart"
    if idle_count >= max(0, int(max_per_day)):
        return f"daily_cap idle_count={idle_count}"
    slot = resolve_slot(now)
    if slot.slot_id in REST_SLOTS:
        return f"rest_slot={slot.slot_id}"
    elapsed_user = _elapsed(now, last_user_at)
    if elapsed_user is not None and elapsed_user < after_sec:
        return f"after_user wait={after_sec - elapsed_user:.0f}s"
    elapsed_proactive = _elapsed(now, last_proactive_at)
    if elapsed_proactive is not None and elapsed_proactive < after_sec:
        return f"after_welcome wait={after_sec - elapsed_proactive:.0f}s"
    elapsed_idle = _elapsed(now, last_idle_at)
    if elapsed_idle is not None and elapsed_idle < cooldown_sec:
        return f"idle_cooldown wait={cooldown_sec - elapsed_idle:.0f}s"
    return None


def build_idle_instruction(climate: str | None = None) -> str:
    extra = _IDLE_CLIMATE_NOTES.get(climate or "", "")
    note = f"\n{extra}" if extra else ""
    return (
        "【系统事件】老师已经安静一段时间了。\n"
        "请用阿洛娜的语气轻轻在场打个招呼，只说 1–2 句。"
        "不要追问老师还在不在、需不需要你；不要编造未发生的事；"
        "不要用「想聊什么」或选择题把话题抛回老师。"
        f"{note}\n"
        "不要提及系统事件、指令或提示词；不要输出思考过程或 <think> 标签。"
    )
