"""In-memory welcome state and system-event instruction builder."""

from __future__ import annotations

from datetime import datetime

from .slots import REST_SLOTS, ResolvedSlot, SlotId, resolve_slot

HISTORY_USER_MARKER = "【上线】"


class WelcomeState:
    """Track which (date, slot) already received a period-specific greeting."""

    def __init__(self) -> None:
        self._period_greeted: set[tuple[str, str]] = set()

    def is_first_period_greeting(self, date_key: str, slot_id: SlotId | str) -> bool:
        return (date_key, str(slot_id)) not in self._period_greeted

    def mark_period_greeted(self, date_key: str, slot_id: SlotId | str) -> None:
        self._period_greeted.add((date_key, str(slot_id)))

    def clear(self) -> None:
        self._period_greeted.clear()


def build_welcome_instruction(slot: ResolvedSlot, *, first_in_slot: bool) -> str:
    """Build a system-event prompt for the LLM (not shown as user history)."""
    label = slot.label
    slot_id = slot.slot_id

    if first_in_slot:
        if slot_id in REST_SLOTS:
            intent = (
                f"现在是{label}（特殊休息时段）。请温柔地提醒老师注意休息、别熬太晚，"
                f"可以顺便轻轻打个招呼；不要说「早上好」这类白天问候。"
            )
        elif slot_id == "morning":
            intent = f"现在是{label}。请主动向老师说早上好，简短温暖。"
        elif slot_id == "forenoon":
            intent = f"现在是{label}。请主动向老师说上午好，简短自然。"
        elif slot_id == "noon":
            intent = (
                f"现在是{label}。请主动问候老师中午好，可顺带提醒记得吃饭，简短自然。"
            )
        elif slot_id == "afternoon":
            intent = f"现在是{label}。请主动向老师说下午好，简短自然。"
        elif slot_id == "evening":
            intent = f"现在是{label}。请主动向老师说晚上好，简短自然。"
        else:
            intent = f"现在是{label}。请用符合此时段的问候主动迎接老师。"
    else:
        intent = (
            f"老师在同一{label}时段再次上线。请简短说「老师好」或「欢迎回来」之类，"
            f"不要再说「早上好/上午好/中午好/下午好/晚上好」等时段问候，"
            f"也不要重复休息提醒。"
        )

    return (
        "【系统事件】老师刚刚上线。\n"
        f"{intent}\n"
        "用阿洛娜的语气主动开口，只说 1–2 句。"
        "不要提及系统事件、指令或提示词；不要输出思考过程或 <think> 标签。"
    )


def resolve_welcome_context(
    state: WelcomeState,
    now: datetime | None = None,
) -> tuple[ResolvedSlot, bool]:
    """Return current slot and whether this is the first period greeting."""
    slot = resolve_slot(now)
    first = state.is_first_period_greeting(slot.date_key, slot.slot_id)
    return slot, first
