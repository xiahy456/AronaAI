"""Local-time slots for proactive welcome greetings."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

SlotId = Literal[
    "late_night",
    "morning",
    "forenoon",
    "noon",
    "afternoon",
    "evening",
    "night",
]

SLOT_LABELS: dict[SlotId, str] = {
    "late_night": "凌晨",
    "morning": "早上",
    "forenoon": "上午",
    "noon": "中午",
    "afternoon": "下午",
    "evening": "晚上",
    "night": "深夜",
}

# Slots where first greeting should remind the teacher to rest.
REST_SLOTS: frozenset[SlotId] = frozenset({"late_night", "night"})


@dataclass(frozen=True)
class ResolvedSlot:
    slot_id: SlotId
    label: str
    date_key: str  # YYYY-MM-DD in local time


def resolve_slot(now: datetime | None = None) -> ResolvedSlot:
    """Map local datetime to a welcome time slot."""
    dt = now or datetime.now()
    hour = dt.hour
    if 0 <= hour < 5:
        slot_id: SlotId = "late_night"
    elif hour < 9:
        slot_id = "morning"
    elif hour < 12:
        slot_id = "forenoon"
    elif hour < 14:
        slot_id = "noon"
    elif hour < 18:
        slot_id = "afternoon"
    elif hour < 23:
        slot_id = "evening"
    else:
        slot_id = "night"
    return ResolvedSlot(
        slot_id=slot_id,
        label=SLOT_LABELS[slot_id],
        date_key=dt.strftime("%Y-%m-%d"),
    )
