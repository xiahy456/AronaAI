"""Facade: classify → update A/B/C → decide → persist."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .classify import classify_user_act
from .events import AronaAct, UserAct, arona_delta, user_delta
from .policy import Action, Climate, Decision, decide, map_arona_act
from .state import RelationshipState
from .store import RelationshipStore

logger = logging.getLogger(__name__)


@dataclass
class RelationshipSettings:
    enabled: bool = True
    alpha: float = 0.3
    beta: float = 0.02
    daily_abs_cap: float = 0.35
    makeup_tension: float = 0.7
    makeup_trust_scale: float = 1.5
    cling_dependence: float = 0.55
    high_dependence: float = 0.7
    climate_stick_turns: int = 3
    baseline_trust: float = 0.55
    baseline_dependence: float = 0.30
    baseline_tension: float = 0.25

    @property
    def baseline(self) -> tuple[float, float, float]:
        return (
            self.baseline_trust,
            self.baseline_dependence,
            self.baseline_tension,
        )

    @classmethod
    def from_config(cls, rel_cfg: Any) -> RelationshipSettings:
        return cls(
            enabled=bool(getattr(rel_cfg, "enabled", True)),
            alpha=float(getattr(rel_cfg, "alpha", 0.3)),
            beta=float(getattr(rel_cfg, "beta", 0.02)),
            daily_abs_cap=float(getattr(rel_cfg, "daily_abs_cap", 0.35)),
            makeup_tension=float(getattr(rel_cfg, "makeup_tension", 0.7)),
            makeup_trust_scale=float(getattr(rel_cfg, "makeup_trust_scale", 1.5)),
            cling_dependence=float(getattr(rel_cfg, "cling_dependence", 0.55)),
            high_dependence=float(getattr(rel_cfg, "high_dependence", 0.7)),
            climate_stick_turns=int(getattr(rel_cfg, "climate_stick_turns", 3)),
            baseline_trust=float(getattr(rel_cfg, "baseline_trust", 0.55)),
            baseline_dependence=float(getattr(rel_cfg, "baseline_dependence", 0.30)),
            baseline_tension=float(getattr(rel_cfg, "baseline_tension", 0.25)),
        )


class RelationshipEngine:
    def __init__(self, settings: RelationshipSettings, store: RelationshipStore) -> None:
        self.settings = settings
        self.store = store
        self.state = store.load()

    @classmethod
    def from_path(cls, path: Path, settings: RelationshipSettings) -> RelationshipEngine:
        return cls(settings, RelationshipStore(path))

    def _apply(self, delta: tuple[float, float, float]) -> None:
        s = self.settings
        self.state.apply_delta(
            delta,
            alpha=s.alpha,
            beta=s.beta,
            baseline=s.baseline,
            daily_abs_cap=s.daily_abs_cap,
            makeup_tension=s.makeup_tension,
            makeup_trust_scale=s.makeup_trust_scale,
        )

    def on_user_text(self, text: str) -> tuple[UserAct, Decision]:
        act = classify_user_act(text)
        self._apply(user_delta(act))
        decision = decide(
            self.state,
            act,
            cling_dependence=self.settings.cling_dependence,
            high_dependence=self.settings.high_dependence,
            stick_turns=self.settings.climate_stick_turns,
        )
        self.state.last_user_act = act
        self.store.save(self.state)
        logger.info(
            "relationship user_act=%s climate=%s action=%s "
            "trust=%.3f dependence=%.3f tension=%.3f",
            act,
            decision.climate,
            decision.action,
            self.state.trust,
            self.state.dependence,
            self.state.tension,
        )
        return act, decision

    def peek_climate(self) -> str:
        from .policy import resolve_climate

        return resolve_climate(
            self.state.trust,
            self.state.dependence,
            self.state.tension,
            cling_dependence=self.settings.cling_dependence,
        )

    def on_arona_action(
        self,
        action: Action,
        climate: Climate,
        user_act: UserAct = "other",
    ) -> AronaAct | None:
        event = map_arona_act(action, climate, user_act)
        if event is None:
            return None
        self._apply(arona_delta(event))
        self.store.save(self.state)
        logger.info(
            "relationship arona_act=%s trust=%.3f dependence=%.3f tension=%.3f",
            event,
            self.state.trust,
            self.state.dependence,
            self.state.tension,
        )
        return event
