"""Table-driven relationship deltas. LLM must never invent these floats."""

from __future__ import annotations

from typing import Literal

UserAct = Literal[
    "fatigue",
    "seek_validation",
    "self_disclose",
    "play_tease",
    "reject",
    "gratitude",
    "affection",
    "worry_bond",
    "depart",
    "instrumental",
    "short_ack",
    "other",
]

AronaAct = Literal[
    "followed_up",
    "gave_space",
    "teased",
    "greeted",
    "missed_promise",
]

# (trust, dependence, tension)
USER_DELTAS: dict[UserAct, tuple[float, float, float]] = {
    "fatigue": (0.0, 0.08, -0.05),
    "seek_validation": (0.04, 0.12, 0.08),
    "self_disclose": (0.08, 0.06, 0.04),
    "play_tease": (0.03, 0.0, 0.12),
    "reject": (-0.06, -0.04, 0.15),
    "gratitude": (0.10, 0.04, -0.04),
    "affection": (0.08, 0.04, -0.05),
    "worry_bond": (0.02, 0.10, 0.08),
    "depart": (0.0, -0.06, -0.06),
    "instrumental": (0.0, -0.06, -0.08),
    "short_ack": (0.0, 0.03, -0.06),
    "other": (0.0, 0.0, 0.0),
}

ARONA_DELTAS: dict[AronaAct, tuple[float, float, float]] = {
    "followed_up": (0.02, 0.03, 0.01),
    "gave_space": (0.0, -0.06, -0.04),
    "teased": (0.02, 0.0, 0.08),
    "greeted": (0.03, 0.0, 0.0),
    "missed_promise": (-0.12, 0.0, 0.06),
}


def user_delta(act: UserAct) -> tuple[float, float, float]:
    return USER_DELTAS.get(act, USER_DELTAS["other"])


def arona_delta(act: AronaAct) -> tuple[float, float, float]:
    return ARONA_DELTAS[act]
