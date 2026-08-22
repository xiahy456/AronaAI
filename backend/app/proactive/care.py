"""Time-of-day care motives: lunch and sleep reminders."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

CareKind = Literal["lunch", "sleep"]

HISTORY_CARE_MARKER = "【提醒】"
CARE_MEMORY_QUERY = "老师 午饭 睡觉 作息"

_CARE_INTENTS: dict[CareKind, str] = {
    "lunch": "现在是午饭时段。请简短提醒老师记得吃饭，不要催促，不要说教。",
    "sleep": (
        "现在偏晚了。请温柔提醒老师注意休息、别熬太晚；"
        "不要说「早上好」这类白天问候，不要催促。"
    ),
}


def parse_hhmm(value: str) -> tuple[int, int]:
    parts = (value or "").strip().split(":")
    if len(parts) < 2:
        raise ValueError(f"invalid hh:mm {value!r}")
    return int(parts[0]), int(parts[1])


def minutes_of_day(dt: datetime) -> int:
    return dt.hour * 60 + dt.minute


def in_window(now: datetime, start: str, end: str) -> bool:
    """True if local now is in [start, end). End < start wraps midnight."""
    cur = minutes_of_day(now)
    start_h, start_m = parse_hhmm(start)
    end_h, end_m = parse_hhmm(end)
    start_min = start_h * 60 + start_m
    end_min = end_h * 60 + end_m
    if start_min <= end_min:
        return start_min <= cur < end_min
    return cur >= start_min or cur < end_min


def _elapsed(now: datetime, then: datetime | None) -> float | None:
    if then is None:
        return None
    return (now - then).total_seconds()


def care_skip_reason(
    kind: CareKind,
    now: datetime,
    *,
    done_today: list[str] | set[str],
    start: str,
    end: str,
    last_proactive_at: datetime | None = None,
    after_sec: float = 0,
) -> str | None:
    """Why care cannot fire. None means it may fire."""
    if kind in done_today:
        return "done_today"
    if not in_window(now, start, end):
        return "out_of_window"
    elapsed_proactive = _elapsed(now, last_proactive_at)
    if elapsed_proactive is not None and elapsed_proactive < after_sec:
        return f"after_welcome wait={after_sec - elapsed_proactive:.0f}s"
    return None


def should_fire_care(
    kind: CareKind,
    now: datetime,
    *,
    done_today: list[str] | set[str],
    start: str,
    end: str,
    last_proactive_at: datetime | None = None,
    after_sec: float = 0,
) -> bool:
    return (
        care_skip_reason(
            kind,
            now,
            done_today=done_today,
            start=start,
            end=end,
            last_proactive_at=last_proactive_at,
            after_sec=after_sec,
        )
        is None
    )


def build_care_instruction(kind: CareKind, climate: str | None = None) -> str:
    intent = _CARE_INTENTS[kind]
    extra = ""
    if climate == "cling_risk":
        extra = "提醒要更短，不要索取确认，也不要问老师还需要你吗。"
    elif climate in {"fragile", "rupture"}:
        extra = "语气放轻、简短，不要活泼催促或开玩笑。"
    note = f"\n{extra}" if extra else ""
    return (
        "【系统事件】到了该轻轻照料老师的时刻。\n"
        f"{intent}{note}\n"
        "用阿洛娜的语气主动开口，只说 1–2 句。"
        "不要用「想聊什么」收尾，不要把话题做成选择题抛回老师。"
        "不要提及系统事件、指令或提示词；不要输出思考过程或 <think> 标签。"
    )
