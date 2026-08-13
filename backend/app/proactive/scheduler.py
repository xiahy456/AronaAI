"""Persist last activity / daily caps and pick at most one proactive motive."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal

from .care import (
    CARE_MEMORY_QUERY,
    HISTORY_CARE_MARKER,
    build_care_instruction,
    should_fire_care,
)
from .idle import (
    HISTORY_IDLE_MARKER,
    build_idle_instruction,
    idle_skip_reason,
    should_fire_idle,
)

logger = logging.getLogger(__name__)

MotiveKind = Literal["idle", "lunch", "sleep"]


@dataclass(frozen=True)
class Motive:
    kind: MotiveKind
    instruction: str
    history_marker: str
    retrieve_memory: bool = False
    memory_query: str = ""


@dataclass
class ProactiveState:
    last_user_at: str = ""
    last_proactive_at: str = ""
    last_idle_at: str = ""
    day: str = ""
    idle_count: int = 0
    care_done: list[str] = field(default_factory=list)

    def roll_day(self, now: datetime) -> None:
        today = now.date().isoformat()
        if self.day != today:
            self.day = today
            self.idle_count = 0
            self.care_done = []

    def to_dict(self) -> dict[str, Any]:
        return {
            "last_user_at": self.last_user_at,
            "last_proactive_at": self.last_proactive_at,
            "last_idle_at": self.last_idle_at,
            "day": self.day,
            "idle_count": self.idle_count,
            "care_done": list(self.care_done),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ProactiveState:
        if not data:
            return cls()
        done = data.get("care_done") or []
        if not isinstance(done, list):
            done = []
        return cls(
            last_user_at=str(data.get("last_user_at") or ""),
            last_proactive_at=str(data.get("last_proactive_at") or ""),
            last_idle_at=str(data.get("last_idle_at") or ""),
            day=str(data.get("day") or ""),
            idle_count=int(data.get("idle_count") or 0),
            care_done=[str(item) for item in done if item],
        )


def _parse_iso(value: str) -> datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


class ProactiveScheduler:
    def __init__(self, path: Path, *, idle_cfg: Any, care_cfg: Any) -> None:
        self.path = path
        self.idle_cfg = idle_cfg
        self.care_cfg = care_cfg
        self.state = self._load()

    def _load(self) -> ProactiveState:
        if not self.path.is_file():
            return ProactiveState(day=date.today().isoformat())
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.exception("proactive load failed path=%s", self.path)
            return ProactiveState(day=date.today().isoformat())
        if not isinstance(raw, dict):
            return ProactiveState(day=date.today().isoformat())
        state = ProactiveState.from_dict(raw)
        if not state.day:
            state.day = date.today().isoformat()
        return state

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(self.state.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(self.path)

    def note_user_activity(self, now: datetime | None = None) -> None:
        dt = now or datetime.now()
        self.state.roll_day(dt)
        self.state.last_user_at = dt.isoformat(timespec="seconds")
        self.save()

    def note_proactive(self, now: datetime | None = None) -> None:
        dt = now or datetime.now()
        self.state.roll_day(dt)
        self.state.last_proactive_at = dt.isoformat(timespec="seconds")
        self.save()

    def mark_fired(self, kind: MotiveKind, now: datetime | None = None) -> None:
        dt = now or datetime.now()
        self.state.roll_day(dt)
        stamp = dt.isoformat(timespec="seconds")
        self.state.last_proactive_at = stamp
        if kind == "idle":
            self.state.last_idle_at = stamp
            self.state.idle_count += 1
        elif kind not in self.state.care_done:
            self.state.care_done.append(kind)
        self.save()

    def pick_motive(
        self,
        now: datetime | None = None,
        *,
        last_user_act: str = "other",
        climate: str | None = None,
    ) -> Motive | None:
        dt = now or datetime.now()
        self.state.roll_day(dt)

        if getattr(self.care_cfg, "enabled", True):
            for kind, start, end in (
                ("lunch", self.care_cfg.lunch_start, self.care_cfg.lunch_end),
                ("sleep", self.care_cfg.sleep_start, self.care_cfg.sleep_end),
            ):
                if should_fire_care(
                    kind,  # type: ignore[arg-type]
                    dt,
                    done_today=self.state.care_done,
                    start=start,
                    end=end,
                ):
                    return Motive(
                        kind=kind,  # type: ignore[arg-type]
                        instruction=build_care_instruction(kind, climate),  # type: ignore[arg-type]
                        history_marker=HISTORY_CARE_MARKER,
                        retrieve_memory=True,
                        memory_query=CARE_MEMORY_QUERY,
                    )

        if getattr(self.idle_cfg, "enabled", True) and should_fire_idle(
            dt,
            last_user_at=_parse_iso(self.state.last_user_at),
            last_proactive_at=_parse_iso(self.state.last_proactive_at),
            last_idle_at=_parse_iso(self.state.last_idle_at),
            idle_count=self.state.idle_count,
            last_user_act=last_user_act,
            after_sec=float(self.idle_cfg.after_sec),
            cooldown_sec=float(self.idle_cfg.cooldown_sec),
            max_per_day=int(self.idle_cfg.max_per_day),
        ):
            return Motive(
                kind="idle",
                instruction=build_idle_instruction(climate),
                history_marker=HISTORY_IDLE_MARKER,
            )
        return None

    def idle_block_reason(
        self,
        now: datetime | None = None,
        *,
        last_user_act: str = "other",
    ) -> str | None:
        """Skip reason when user after_sec is already met but idle still cannot fire."""
        if not getattr(self.idle_cfg, "enabled", True):
            return None
        dt = now or datetime.now()
        self.state.roll_day(dt)
        after_sec = float(self.idle_cfg.after_sec)
        last_user_at = _parse_iso(self.state.last_user_at)
        elapsed_user = None if last_user_at is None else (dt - last_user_at).total_seconds()
        if elapsed_user is None or elapsed_user < after_sec:
            return None
        reason = idle_skip_reason(
            dt,
            last_user_at=last_user_at,
            last_proactive_at=_parse_iso(self.state.last_proactive_at),
            last_idle_at=_parse_iso(self.state.last_idle_at),
            idle_count=self.state.idle_count,
            last_user_act=last_user_act,
            after_sec=after_sec,
            cooldown_sec=float(self.idle_cfg.cooldown_sec),
            max_per_day=int(self.idle_cfg.max_per_day),
        )
        if reason is None or reason.startswith("after_user"):
            return None
        return reason
