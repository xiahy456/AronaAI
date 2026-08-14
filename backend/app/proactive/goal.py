"""Sparse follow-up of unfinished memory goals."""

from __future__ import annotations

import re
from datetime import datetime

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


def can_attempt_goal(
    now: datetime,
    *,
    last_user_at: datetime | None,
    last_user_act: str,
    goal_count: int,
    min_after_user_sec: float,
    max_per_day: int,
) -> bool:
    if last_user_act == "depart":
        return False
    if goal_count >= max(0, int(max_per_day)):
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
) -> dict[str, object] | None:
    """Oldest unvisited / longest-since-visit goal that is not muted or cooling."""
    eligible: list[tuple[float, float, dict[str, object]]] = []
    for item in goals:
        key = str(item.get("key") or "").strip()
        content = str(item.get("content") or "").strip()
        if not key or not content:
            continue
        mute_until = _parse_iso(str(goal_mute.get(key) or ""))
        if mute_until is not None and now < mute_until:
            continue
        last = _parse_iso(str(goal_last.get(key) or ""))
        if last is not None and (now - last).total_seconds() < cooldown_sec:
            continue
        last_ts = last.timestamp() if last else 0.0
        updated = float(item.get("updated_at") or 0.0)
        eligible.append((last_ts, updated, item))
    if not eligible:
        return None
    eligible.sort(key=lambda row: (row[0], row[1]))
    return eligible[0][2]


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
