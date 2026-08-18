"""Process-level ticker: pick at most one motive and push to an idle session."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from .care import CARE_MEMORY_QUERY, HISTORY_CARE_MARKER, build_care_instruction
from .festival import (
    HISTORY_FESTIVAL_MARKER,
    FestivalHit,
    birthday_from_profiles,
    build_festival_instruction,
    needs_rest_followup,
)

if TYPE_CHECKING:
    from ..ws_handler import AppState

logger = logging.getLogger(__name__)

TICK_SEC = 30.0


async def load_birthday_content(state: "AppState") -> str:
    if not getattr(state.scheduler.festival_cfg, "enabled", False):
        return ""
    rows = await asyncio.to_thread(
        state.orchestrator.memory_store.list_by_category, "profile"
    )
    return birthday_from_profiles(rows)


async def deliver_festival(
    state: "AppState",
    *,
    session_id: str,
    send: Any,
    hit: FestivalHit,
    now: datetime,
    climate: str | None,
    decision: Any,
) -> bool:
    """Send festival line; in REST_SLOTS follow with a rest reminder. Marks on success."""
    extra = [hit.extra_memory] if hit.extra_memory else []
    ok = await state.orchestrator.handle_initiate(
        session_id=session_id,
        kind="festival",
        instruction=build_festival_instruction(hit, climate),
        history_marker=HISTORY_FESTIVAL_MARKER,
        send=send,
        extra_memories=extra,
        climate=climate,
        decision=decision,
    )
    if not ok:
        logger.warning(
            "festival generate failed session=%s id=%s (not marked)",
            session_id,
            hit.id,
        )
        return False
    state.scheduler.mark_fired("festival", now, festival_id=hit.id)
    logger.info("festival fired session=%s id=%s", session_id, hit.id)

    if (
        needs_rest_followup(now)
        and "sleep" not in state.scheduler.state.care_done
    ):
        rest_ok = await state.orchestrator.handle_initiate(
            session_id=session_id,
            kind="sleep",
            instruction=build_care_instruction("sleep", climate),
            history_marker=HISTORY_CARE_MARKER,
            send=send,
            retrieve_memory=True,
            memory_query=CARE_MEMORY_QUERY,
            climate=climate,
            decision=decision,
        )
        if rest_ok:
            state.scheduler.mark_fired("sleep", now)
            logger.info("festival rest followup session=%s", session_id)
        else:
            logger.warning(
                "festival rest followup failed session=%s (festival kept)",
                session_id,
            )
    return True


async def run_proactive_loop(state: "AppState") -> None:
    while True:
        await asyncio.sleep(TICK_SEC)
        try:
            await tick_once(state)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("proactive tick failed")


async def tick_once(state: "AppState", now: datetime | None = None) -> bool:
    """Evaluate motives and maybe generate. Returns True if a line was sent."""
    targets = state.hub.idle_sessions()
    if not targets:
        return False

    dt = now or datetime.now()
    relationship = state.orchestrator.relationship
    last_user_act = "other"
    climate = None
    if relationship is not None and state.config.proactive.relationship.enabled:
        last_user_act = relationship.state.last_user_act or "other"
        climate = relationship.peek_climate()

    birthday = await load_birthday_content(state)
    goals: list[dict] = []
    if getattr(state.scheduler.goal_cfg, "enabled", False):
        goals = await asyncio.to_thread(
            state.orchestrator.memory_store.list_by_category, "goal"
        )

    motive = state.scheduler.pick_motive(
        dt,
        last_user_act=last_user_act,
        climate=climate,
        goals=goals,
        birthday_content=birthday,
    )
    if motive is None:
        reason = state.scheduler.idle_block_reason(dt, last_user_act=last_user_act)
        if reason:
            logger.info("proactive idle skipped reason=%s", reason)
        return False

    decision = None
    if relationship is not None and state.config.proactive.relationship.enabled:
        decision = relationship.decide_proactive(motive.kind)
        if decision.action != "initiate":
            logger.info(
                "proactive skipped by policy kind=%s climate=%s action=%s",
                motive.kind,
                decision.climate,
                decision.action,
            )
            return False

    session_id, send = targets[0]
    state.hub.set_busy(session_id, True)
    try:
        if motive.kind == "festival":
            hit = state.scheduler.pending_festival(dt, birthday_content=birthday)
            if hit is None:
                return False
            return await deliver_festival(
                state,
                session_id=session_id,
                send=send,
                hit=hit,
                now=dt,
                climate=climate,
                decision=decision,
            )

        ok = await state.orchestrator.handle_initiate(
            session_id=session_id,
            kind=motive.kind,
            instruction=motive.instruction,
            history_marker=motive.history_marker,
            send=send,
            retrieve_memory=motive.retrieve_memory,
            memory_query=motive.memory_query,
            extra_memories=list(motive.extra_memories),
            climate=climate,
            decision=decision,
        )
    finally:
        state.hub.set_busy(session_id, False)

    if ok:
        state.scheduler.mark_fired(motive.kind, dt, goal_key=motive.goal_key)
        logger.info(
            "proactive fired session=%s kind=%s", session_id, motive.kind
        )
    else:
        logger.warning(
            "proactive generate failed session=%s kind=%s (not marked)",
            session_id,
            motive.kind,
        )
    return ok
