"""Process-level ticker: pick at most one motive and push to an idle session."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..ws_handler import AppState

logger = logging.getLogger(__name__)

TICK_SEC = 30.0


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

    goals: list[dict] = []
    if getattr(state.scheduler.goal_cfg, "enabled", False):
        goals = await asyncio.to_thread(
            state.orchestrator.memory_store.list_by_category, "goal"
        )

    motive = state.scheduler.pick_motive(
        dt, last_user_act=last_user_act, climate=climate, goals=goals
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
        extra_must_not = None
        if motive.kind == "goal":
            extra_must_not = [
                "催促",
                "盘问进展",
                "编造老师已经做了什么",
                "把问题抛回老师",
            ]
        ok = await state.orchestrator.handle_initiate(
            session_id=session_id,
            kind=motive.kind,
            instruction=motive.instruction,
            history_marker=motive.history_marker,
            send=send,
            retrieve_memory=motive.retrieve_memory,
            memory_query=motive.memory_query,
            extra_memories=list(motive.extra_memories),
            extra_must_not=extra_must_not,
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
