"""Proactive companion actions (welcome, idle check-in, time-of-day care)."""

from .care import (
    CARE_MEMORY_QUERY,
    HISTORY_CARE_MARKER,
    build_care_instruction,
    in_window,
    should_fire_care,
)
from .hub import ConnectionHub
from .idle import HISTORY_IDLE_MARKER, build_idle_instruction, should_fire_idle
from .loop import TICK_SEC, run_proactive_loop, tick_once
from .scheduler import Motive, ProactiveScheduler, ProactiveState
from .slots import REST_SLOTS, SLOT_LABELS, ResolvedSlot, SlotId, resolve_slot
from .welcome import (
    HISTORY_USER_MARKER,
    WELCOME_MEMORY_QUERY,
    WelcomeState,
    build_welcome_instruction,
    resolve_welcome_context,
)

__all__ = [
    "CARE_MEMORY_QUERY",
    "ConnectionHub",
    "HISTORY_CARE_MARKER",
    "HISTORY_IDLE_MARKER",
    "HISTORY_USER_MARKER",
    "Motive",
    "ProactiveScheduler",
    "ProactiveState",
    "REST_SLOTS",
    "ResolvedSlot",
    "SLOT_LABELS",
    "SlotId",
    "TICK_SEC",
    "WELCOME_MEMORY_QUERY",
    "WelcomeState",
    "build_care_instruction",
    "build_idle_instruction",
    "build_welcome_instruction",
    "in_window",
    "resolve_slot",
    "resolve_welcome_context",
    "run_proactive_loop",
    "should_fire_care",
    "should_fire_idle",
    "tick_once",
]
