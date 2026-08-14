"""Proactive companion actions (welcome, idle, care, goal follow-up)."""

from .care import (
    CARE_MEMORY_QUERY,
    HISTORY_CARE_MARKER,
    build_care_instruction,
    in_window,
    should_fire_care,
)
from .followup import HISTORY_CONTINUE_MARKER, build_continue_instruction
from .goal import (
    HISTORY_GOAL_MARKER,
    build_goal_instruction,
    can_attempt_goal,
    select_goal,
    wants_goal_mute,
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
    "HISTORY_CONTINUE_MARKER",
    "HISTORY_GOAL_MARKER",
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
    "build_continue_instruction",
    "build_goal_instruction",
    "build_idle_instruction",
    "build_welcome_instruction",
    "can_attempt_goal",
    "in_window",
    "resolve_slot",
    "resolve_welcome_context",
    "run_proactive_loop",
    "select_goal",
    "should_fire_care",
    "should_fire_idle",
    "tick_once",
    "wants_goal_mute",
]
