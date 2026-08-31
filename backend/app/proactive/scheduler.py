# Copyright 2026 xia_hy456. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Persist last activity / daily caps and pick at most one proactive motive."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from ..config import FestivalConfig, GoalConfig
from .care import (
    CARE_MEMORY_QUERY,
    HISTORY_CARE_MARKER,
    build_care_instruction,
    care_skip_reason,
)
from .festival import (
    HISTORY_FESTIVAL_MARKER,
    FestivalHit,
    build_festival_instruction,
    match_festival,
)
from .goal import (
    HISTORY_GOAL_MARKER,
    build_goal_instruction,
    can_attempt_goal,
    has_important_goal,
    select_goal,
)
from .idle import (
    HISTORY_IDLE_MARKER,
    build_idle_instruction,
    idle_skip_reason,
    should_fire_idle,
)

logger = logging.getLogger(__name__)

MotiveKind = Literal["idle", "lunch", "sleep", "goal", "festival"]


@dataclass(frozen=True)
class Motive:
    kind: MotiveKind
    instruction: str
    history_marker: str
    retrieve_memory: bool = False
    memory_query: str = ""
    goal_key: str = ""
    festival_id: str = ""
    extra_memories: tuple[str, ...] = ()


@dataclass
class ProactiveState:
    last_user_at: str = ""
    last_proactive_at: str = ""
    last_idle_at: str = ""
    day: str = ""
    idle_count: int = 0
    care_done: list[str] = field(default_factory=list)
    goal_last: dict[str, str] = field(default_factory=dict)
    goal_mute: dict[str, str] = field(default_factory=dict)
    goal_count: int = 0
    last_goal_key: str = ""
    festival_done: list[str] = field(default_factory=list)

    def roll_day(self, now: datetime) -> None:
        today = now.date().isoformat()
        if self.day != today:
            self.day = today
            self.idle_count = 0
            self.care_done = []
            self.goal_count = 0
            self.festival_done = []

    def to_dict(self) -> dict[str, Any]:
        return {
            "last_user_at": self.last_user_at,
            "last_proactive_at": self.last_proactive_at,
            "last_idle_at": self.last_idle_at,
            "day": self.day,
            "idle_count": self.idle_count,
            "care_done": list(self.care_done),
            "goal_last": dict(self.goal_last),
            "goal_mute": dict(self.goal_mute),
            "goal_count": self.goal_count,
            "last_goal_key": self.last_goal_key,
            "festival_done": list(self.festival_done),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ProactiveState:
        if not data:
            return cls()
        done = data.get("care_done") or []
        if not isinstance(done, list):
            done = []
        festivals = data.get("festival_done") or []
        if not isinstance(festivals, list):
            festivals = []
        return cls(
            last_user_at=str(data.get("last_user_at") or ""),
            last_proactive_at=str(data.get("last_proactive_at") or ""),
            last_idle_at=str(data.get("last_idle_at") or ""),
            day=str(data.get("day") or ""),
            idle_count=int(data.get("idle_count") or 0),
            care_done=[str(item) for item in done if item],
            goal_last=_as_str_dict(data.get("goal_last")),
            goal_mute=_as_str_dict(data.get("goal_mute")),
            goal_count=int(data.get("goal_count") or 0),
            last_goal_key=str(data.get("last_goal_key") or ""),
            festival_done=[str(item) for item in festivals if item],
        )


def _as_str_dict(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    out: dict[str, str] = {}
    for key, item in value.items():
        k = str(key or "").strip()
        v = str(item or "").strip()
        if k and v:
            out[k] = v
    return out


def _parse_iso(value: str) -> datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


class ProactiveScheduler:
    def __init__(
        self,
        path: Path,
        *,
        idle_cfg: Any,
        care_cfg: Any,
        goal_cfg: Any | None = None,
        festival_cfg: Any | None = None,
    ) -> None:
        self.path = path
        self.idle_cfg = idle_cfg
        self.care_cfg = care_cfg
        self.goal_cfg = goal_cfg if goal_cfg is not None else GoalConfig()
        self.festival_cfg = (
            festival_cfg if festival_cfg is not None else FestivalConfig()
        )
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

    def mark_fired(
        self,
        kind: MotiveKind,
        now: datetime | None = None,
        *,
        goal_key: str = "",
        festival_id: str = "",
    ) -> None:
        dt = now or datetime.now()
        self.state.roll_day(dt)
        stamp = dt.isoformat(timespec="seconds")
        self.state.last_proactive_at = stamp
        if kind == "idle":
            self.state.last_idle_at = stamp
            self.state.idle_count += 1
        elif kind == "goal":
            self.state.goal_count += 1
            key = (goal_key or "").strip()
            if key:
                self.state.last_goal_key = key
                self.state.goal_last[key] = stamp
        elif kind == "festival":
            fid = (festival_id or "").strip()
            if fid and fid not in self.state.festival_done:
                self.state.festival_done.append(fid)
        elif kind not in self.state.care_done:
            self.state.care_done.append(kind)
        self.save()

    def mute_last_goal(self, now: datetime | None = None) -> str | None:
        key = (self.state.last_goal_key or "").strip()
        if not key:
            return None
        dt = now or datetime.now()
        mute_sec = float(getattr(self.goal_cfg, "mute_sec", 604800))
        until = dt + timedelta(seconds=mute_sec)
        self.state.goal_mute[key] = until.isoformat(timespec="seconds")
        self.save()
        logger.info("goal muted key=%s until=%s", key, self.state.goal_mute[key])
        return key

    def pending_festival(
        self,
        now: datetime | None = None,
        *,
        birthday_content: str = "",
    ) -> FestivalHit | None:
        if not getattr(self.festival_cfg, "enabled", True):
            return None
        dt = now or datetime.now()
        self.state.roll_day(dt)
        hit = match_festival(dt, birthday_content)
        if hit is None or hit.id in self.state.festival_done:
            return None
        return hit

    def pick_motive(
        self,
        now: datetime | None = None,
        *,
        last_user_act: str = "other",
        climate: str | None = None,
        goals: list[dict[str, object]] | None = None,
        birthday_content: str = "",
    ) -> Motive | None:
        dt = now or datetime.now()
        self.state.roll_day(dt)

        if last_user_act != "depart":
            hit = self.pending_festival(dt, birthday_content=birthday_content)
            if hit is not None:
                extra = (hit.extra_memory,) if hit.extra_memory else ()
                return Motive(
                    kind="festival",
                    instruction=build_festival_instruction(hit, climate),
                    history_marker=HISTORY_FESTIVAL_MARKER,
                    festival_id=hit.id,
                    extra_memories=extra,
                )

        if getattr(self.care_cfg, "enabled", True):
            after_sec = float(getattr(self.idle_cfg, "after_sec", 0) or 0)
            last_proactive_at = _parse_iso(self.state.last_proactive_at)
            for kind, start, end in (
                ("lunch", self.care_cfg.lunch_start, self.care_cfg.lunch_end),
                ("sleep", self.care_cfg.sleep_start, self.care_cfg.sleep_end),
            ):
                reason = care_skip_reason(
                    kind,  # type: ignore[arg-type]
                    dt,
                    done_today=self.state.care_done,
                    start=start,
                    end=end,
                    last_proactive_at=last_proactive_at,
                    after_sec=after_sec,
                )
                if reason is None:
                    return Motive(
                        kind=kind,  # type: ignore[arg-type]
                        instruction=build_care_instruction(kind, climate),  # type: ignore[arg-type]
                        history_marker=HISTORY_CARE_MARKER,
                        retrieve_memory=True,
                        memory_query=CARE_MEMORY_QUERY,
                    )
                if reason.startswith("after_welcome"):
                    return None

        if getattr(self.goal_cfg, "enabled", True):
            horizon = float(
                getattr(self.goal_cfg, "important_horizon_hours", 36) or 36
            )
            important_cd = float(
                getattr(self.goal_cfg, "important_cooldown_sec", 1800) or 1800
            )
            goals_list = goals or []
            has_important = has_important_goal(
                goals_list,
                dt,
                goal_mute=self.state.goal_mute,
                horizon_hours=horizon,
            )
            if can_attempt_goal(
                dt,
                last_user_at=_parse_iso(self.state.last_user_at),
                last_user_act=last_user_act,
                goal_count=self.state.goal_count,
                min_after_user_sec=float(self.goal_cfg.min_after_user_sec),
                max_per_day=int(self.goal_cfg.max_per_day),
                has_important=has_important,
            ):
                selected = select_goal(
                    goals_list,
                    dt,
                    goal_last=self.state.goal_last,
                    goal_mute=self.state.goal_mute,
                    cooldown_sec=float(self.goal_cfg.cooldown_sec),
                    important_horizon_hours=horizon,
                    important_cooldown_sec=important_cd,
                    goal_count=self.state.goal_count,
                    max_per_day=int(self.goal_cfg.max_per_day),
                )
                if selected is not None:
                    key = str(selected.get("key") or "").strip()
                    content = str(selected.get("content") or "").strip()
                    if key and content:
                        return Motive(
                            kind="goal",
                            instruction=build_goal_instruction(content, climate),
                            history_marker=HISTORY_GOAL_MARKER,
                            goal_key=key,
                            extra_memories=(content,),
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

    def care_block_reason(self, now: datetime | None = None) -> str | None:
        """Skip reason when lunch/sleep is in window but waiting after_sec."""
        if not getattr(self.care_cfg, "enabled", True):
            return None
        dt = now or datetime.now()
        self.state.roll_day(dt)
        after_sec = float(getattr(self.idle_cfg, "after_sec", 0) or 0)
        last_proactive_at = _parse_iso(self.state.last_proactive_at)
        for kind, start, end in (
            ("lunch", self.care_cfg.lunch_start, self.care_cfg.lunch_end),
            ("sleep", self.care_cfg.sleep_start, self.care_cfg.sleep_end),
        ):
            reason = care_skip_reason(
                kind,  # type: ignore[arg-type]
                dt,
                done_today=self.state.care_done,
                start=start,
                end=end,
                last_proactive_at=last_proactive_at,
                after_sec=after_sec,
            )
            if reason is not None and reason.startswith("after_welcome"):
                return f"{kind} {reason}"
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
