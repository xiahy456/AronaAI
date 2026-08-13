"""Proactive companion actions (welcome, future reminders, etc.)."""

from .slots import REST_SLOTS, SLOT_LABELS, ResolvedSlot, SlotId, resolve_slot
from .welcome import (
    HISTORY_USER_MARKER,
    WelcomeState,
    build_welcome_instruction,
    resolve_welcome_context,
)

__all__ = [
    "HISTORY_USER_MARKER",
    "REST_SLOTS",
    "SLOT_LABELS",
    "ResolvedSlot",
    "SlotId",
    "WelcomeState",
    "build_welcome_instruction",
    "resolve_slot",
    "resolve_welcome_context",
]
