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

"""Sparse follow-up of unfinished memory goals."""

from __future__ import annotations

import re
from datetime import datetime

from ..query_time import is_currently_important
from .slots import REST_SLOTS, resolve_slot

HISTORY_GOAL_MARKER = "【回访】"

_MUTE_RE = re.compile(r"(先别提|别提这个|不要再提|别再问|不用提了)")


def wants_goal_mute(text: str) -> bool:
    return bool(_MUTE_RE.search((text or "").strip()))


def _parse_iso(value: str) -> datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _is_muted(key: str, now: datetime, goal_mute: dict[str, str]) -> bool:
    mute_until = _parse_iso(str(goal_mute.get(key) or ""))
    return mute_until is not None and now < mute_until


def goal_is_important(
    content: str,
    now: datetime,
    *,
    horizon_hours: float,
) -> bool:
    return is_currently_important(
        content, now, horizon_hours=horizon_hours
    )


def has_important_goal(
    goals: list[dict[str, object]],
    now: datetime,
    *,
    goal_mute: dict[str, str],
    horizon_hours: float,
) -> bool:
    for item in goals:
        key = str(item.get("key") or "").strip()
        content = str(item.get("content") or "").strip()
        if not key or not content:
            continue
        if _is_muted(key, now, goal_mute):
            continue
        if goal_is_important(content, now, horizon_hours=horizon_hours):
            return True
    return False


def can_attempt_goal(
    now: datetime,
    *,
    last_user_at: datetime | None,
    last_user_act: str,
    goal_count: int,
    min_after_user_sec: float,
    max_per_day: int,
    has_important: bool = False,
) -> bool:
    if last_user_act == "depart":
        return False
    if not has_important and goal_count >= max(0, int(max_per_day)):
        return False
    if resolve_slot(now).slot_id in REST_SLOTS:
        return False
    if last_user_at is None:
        return False
    if (now - last_user_at).total_seconds() < min_after_user_sec:
        return False
    return True


def select_goal(
    goals: list[dict[str, object]],
    now: datetime,
    *,
    goal_last: dict[str, str],
    goal_mute: dict[str, str],
    cooldown_sec: float,
    important_horizon_hours: float = 36,
    important_cooldown_sec: float = 1800,
    goal_count: int = 0,
    max_per_day: int | None = None,
) -> dict[str, object] | None:
    """Prefer currently important goals; otherwise oldest unvisited / longest idle."""
    daily_full = (
        max_per_day is not None and goal_count >= max(0, int(max_per_day))
    )
    eligible: list[tuple[int, float, float, dict[str, object]]] = []
    for item in goals:
        key = str(item.get("key") or "").strip()
        content = str(item.get("content") or "").strip()
        if not key or not content:
            continue
        if _is_muted(key, now, goal_mute):
            continue
        important = goal_is_important(
            content, now, horizon_hours=important_horizon_hours
        )
        if daily_full and not important:
            continue
        last = _parse_iso(str(goal_last.get(key) or ""))
        wait = (
            float(important_cooldown_sec) if important else float(cooldown_sec)
        )
        if last is not None and wait > 0 and (now - last).total_seconds() < wait:
            continue
        last_ts = last.timestamp() if last else 0.0
        updated = float(item.get("updated_at") or 0.0)
        # important first (0), then longest since visit, then oldest updated_at
        eligible.append((0 if important else 1, last_ts, updated, item))
    if not eligible:
        return None
    eligible.sort(key=lambda row: (row[0], row[1], row[2]))
    return eligible[0][3]


def build_goal_instruction(content: str, climate: str | None = None) -> str:
    extra = ""
    if climate == "cling_risk":
        extra = "更短，不要追问老师还在不在。"
    note = f"\n{extra}" if extra else ""
    return (
        "【系统事件】老师有一条尚未完成的计划，可以轻轻回访一下。\n"
        f"计划内容：{(content or '').strip()}\n"
        "用阿洛娜的语气轻轻提起，只说 1–2 句。不要催促，不要盘问进展，"
        "不要编造老师已经做了什么。不要用「想聊什么」收尾，"
        "不要把话题做成选择题抛回老师。"
        f"{note}\n"
        "不要提及系统事件、指令或提示词；不要输出思考过程或 <think> 标签。"
    )
