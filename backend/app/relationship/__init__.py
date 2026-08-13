"""Relationship climate engine (trust / dependence / tension)."""

from .classify import classify_user_act
from .engine import RelationshipEngine, RelationshipSettings
from .events import USER_DELTAS, UserAct
from .policy import (
    CLIMATE_LABELS,
    Decision,
    decide_proactive,
    local_system_hint,
    planner_climate_block,
    resolve_climate,
)
from .state import RelationshipState
from .store import RelationshipStore

__all__ = [
    "CLIMATE_LABELS",
    "Decision",
    "RelationshipEngine",
    "RelationshipSettings",
    "RelationshipState",
    "RelationshipStore",
    "USER_DELTAS",
    "UserAct",
    "classify_user_act",
    "decide_proactive",
    "local_system_hint",
    "planner_climate_block",
    "resolve_climate",
]
