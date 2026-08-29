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

"""WebSocket connection handler for Qt-compatible protocol."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from .config import AppConfig
from .conversation import ConversationManager
from .input_filter import (
    ASR_FALLBACK_EMOTION,
    ASR_FALLBACK_REPLY,
    is_unusable_user_text,
)
from .logging_utils import begin_trace, format_interactive_log, preview, reset_trace
from .orchestrator import Orchestrator
from .proactive import ConnectionHub, ProactiveScheduler, WelcomeState, resolve_welcome_context
from .proactive.goal import wants_goal_mute
from .proactive.loop import deliver_festival, load_birthday_content
from .protocol import (
    CODE_BAD_REQUEST,
    CODE_INTERNAL,
    CODE_INVALID_JSON,
    TYPE_CHAT,
    TYPE_CHAT_RESPONSE,
    TYPE_CLEAR_SESSION,
    TYPE_CONNECTED,
    TYPE_GET_STATS,
    TYPE_INTERRUPT,
    TYPE_LISTEN_STATE,
    TYPE_PING,
    TYPE_PONG,
    TYPE_TRANSCRIPT,
    msg_chat_response,
    msg_connected,
    msg_error,
    msg_pong,
    msg_result,
    msg_stats,
)
from .turntaking import (
    TurnBuffer,
    is_teacher_speaker,
    looks_incomplete,
)
from .turntaking.speaker import normalize_speaker

logger = logging.getLogger(__name__)


class AppState:
    def __init__(
        self,
        config: AppConfig,
        orchestrator: Orchestrator,
        conversations: ConversationManager,
        welcome: WelcomeState | None = None,
        hub: ConnectionHub | None = None,
        scheduler: ProactiveScheduler | None = None,
    ) -> None:
        self.config = config
        self.orchestrator = orchestrator
        self.conversations = conversations
        self.welcome = welcome or WelcomeState()
        self.hub = hub or ConnectionHub()
        self.scheduler = scheduler


async def websocket_endpoint(websocket: WebSocket, state: AppState) -> None:
    await websocket.accept()
    session_id = str(uuid.uuid4())
    client = getattr(websocket, "client", None)
    client_host = getattr(client, "host", None) if client else None
    client_port = getattr(client, "port", None) if client else None
    logger.info(
        "WS connected session=%s client=%s:%s",
        session_id,
        client_host,
        client_port,
    )

    chat_recv_at: float | None = None

    turn_buffer = TurnBuffer()
    listen_cfg = state.config.listen
    generation_id = 0
    inflight_user: str | None = None
    commit_task: asyncio.Task[None] | None = None
    wait_extended = False

    async def send(payload: dict[str, Any]) -> None:
        msg_type = payload.get("type")
        if msg_type == TYPE_CHAT_RESPONSE:
            if str(payload.get("content") or "").strip():
                turn_buffer.note_arona_spoke()
            logger.info("%s", format_interactive_log(payload))
            reset_trace()
            logger.info(
                "WS send session=%s type=%s context=%s latency=%s content=%r",
                session_id,
                msg_type,
                payload.get("context_used"),
                payload.get("latency"),
                payload.get("content", ""),
            )
        elif msg_type not in (TYPE_PONG, TYPE_CONNECTED):
            logger.info(
                "WS send session=%s type=%s payload=%s",
                session_id,
                msg_type,
                preview(json.dumps(payload, ensure_ascii=False), 240),
            )
        await websocket.send_text(json.dumps(payload, ensure_ascii=False))

    await send(msg_connected(session_id))
    state.hub.register(session_id, send)
    if state.scheduler is not None:
        state.scheduler.note_user_activity()

    chat_task: asyncio.Task[None] | None = None

    def _clear_inflight() -> None:
        nonlocal inflight_user
        inflight_user = None

    async def _cancel_commit() -> None:
        nonlocal commit_task
        task = commit_task
        commit_task = None
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def _run_chat(
        content: str,
        options: dict[str, Any],
        request_json: str | None,
        started_at: float | None,
        abort_check: Any | None = None,
    ) -> None:
        state.hub.set_busy(session_id, True)
        if state.scheduler is not None:
            state.scheduler.note_user_activity()
            if wants_goal_mute(content):
                muted = state.scheduler.mute_last_goal()
                if muted:
                    logger.info("goal muted by user key=%s", muted)
        try:
            await state.orchestrator.handle_chat(
                session_id=session_id,
                content=content,
                options=options,
                send=send,
                request_json=request_json,
                started_at=started_at,
                abort_check=abort_check,
                on_committed=_clear_inflight,
            )
            if inflight_user:
                turn_buffer.prepend(inflight_user)
                _clear_inflight()
        except asyncio.CancelledError:
            logger.info("chat cancelled session=%s", session_id)
            raise
        except Exception as exc:
            logger.exception("Handler error session=%s", session_id)
            try:
                await send(msg_error(CODE_INTERNAL, str(exc)))
            except Exception:
                pass
        finally:
            state.hub.set_busy(session_id, False)

    async def _interrupt_generation(*, restore_inflight: bool) -> None:
        nonlocal chat_task, generation_id, inflight_user
        generation_id += 1
        if restore_inflight and inflight_user:
            turn_buffer.prepend(inflight_user)
            inflight_user = None
        if chat_task is not None and not chat_task.done():
            chat_task.cancel()
            try:
                await chat_task
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception(
                    "Error while interrupting chat task session=%s", session_id
                )

    async def _commit_turn(*, force: bool = False) -> None:
        nonlocal commit_task, chat_task, inflight_user, wait_extended, generation_id
        commit_task = None
        if not force and not turn_buffer.listening:
            return
        drained = turn_buffer.drain()
        if not drained or is_unusable_user_text(drained):
            logger.info(
                "listen commit skipped session=%s reason=unusable text=%r",
                session_id,
                drained,
            )
            return
        wait_extended = False
        logger.info("listen commit session=%s text=%r", session_id, drained)
        if chat_task is not None and not chat_task.done():
            await _interrupt_generation(restore_inflight=True)
        my_id = generation_id
        inflight_user = drained
        started = time.perf_counter()
        request_json = json.dumps(
            {"type": "transcript", "content": drained},
            ensure_ascii=False,
        )
        chat_task = asyncio.create_task(
            _run_chat(
                drained,
                {},
                request_json,
                started,
                lambda: generation_id != my_id,
            )
        )

    async def _commit_after(delay_sec: float) -> None:
        try:
            await asyncio.sleep(delay_sec)
            await _commit_turn()
        except asyncio.CancelledError:
            raise

    def _schedule_commit() -> None:
        nonlocal commit_task, wait_extended
        wait_extended = False
        if commit_task is not None and not commit_task.done():
            commit_task.cancel()
        delay_ms = listen_cfg.silence_commit_ms
        if looks_incomplete(turn_buffer.last_text()):
            delay_ms = listen_cfg.incomplete_commit_ms
            wait_extended = True
        commit_task = asyncio.create_task(_commit_after(max(0.05, delay_ms / 1000.0)))

    async def _run_welcome() -> None:
        state.hub.set_busy(session_id, True)
        try:
            slot, first = resolve_welcome_context(state.welcome)
            logger.info(
                "welcome trigger session=%s slot=%s first=%s date=%s",
                session_id,
                slot.slot_id,
                first,
                slot.date_key,
            )
            climate = None
            relationship = state.orchestrator.relationship
            if (
                relationship is not None
                and state.config.proactive.relationship.enabled
            ):
                climate = relationship.peek_climate()

            hit = None
            if state.scheduler is not None:
                birthday = await load_birthday_content(state)
                hit = state.scheduler.pending_festival(birthday_content=birthday)
            if hit is not None:
                decision = None
                if (
                    relationship is not None
                    and state.config.proactive.relationship.enabled
                ):
                    decision = relationship.decide_proactive("festival")
                    if decision.action != "initiate":
                        logger.info(
                            "festival welcome skipped by policy climate=%s action=%s",
                            decision.climate,
                            decision.action,
                        )
                        hit = None
                if hit is not None:
                    ok = await deliver_festival(
                        state,
                        session_id=session_id,
                        send=send,
                        hit=hit,
                        now=datetime.now(),
                        climate=climate,
                        decision=decision,
                    )
                    if ok and first:
                        state.welcome.mark_period_greeted(
                            slot.date_key, slot.slot_id
                        )
                        logger.info(
                            "welcome period marked session=%s date=%s slot=%s via=festival",
                            session_id,
                            slot.date_key,
                            slot.slot_id,
                        )
                    elif not ok:
                        logger.warning(
                            "festival welcome failed session=%s (not marked)",
                            session_id,
                        )
                    return

            ok = await state.orchestrator.handle_welcome(
                session_id=session_id,
                slot=slot,
                first_in_slot=first,
                send=send,
            )
            if ok and first:
                state.welcome.mark_period_greeted(slot.date_key, slot.slot_id)
                logger.info(
                    "welcome period marked session=%s date=%s slot=%s",
                    session_id,
                    slot.date_key,
                    slot.slot_id,
                )
            if ok and state.scheduler is not None:
                state.scheduler.note_proactive()
            elif not ok:
                logger.warning("welcome failed session=%s (period not marked)", session_id)
        except asyncio.CancelledError:
            logger.info("welcome cancelled session=%s", session_id)
            raise
        except Exception:
            logger.exception("welcome error session=%s", session_id)
        finally:
            state.hub.set_busy(session_id, False)

    if state.config.proactive.welcome.enabled:
        chat_task = asyncio.create_task(_run_welcome())
    else:
        logger.info("welcome skipped session=%s reason=disabled", session_id)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning(
                    "WS invalid JSON session=%s raw=%s",
                    session_id,
                    preview(raw, 200),
                )
                await send(msg_error(CODE_INVALID_JSON, "Invalid JSON"))
                continue

            if not isinstance(data, dict):
                logger.warning("WS non-object message session=%s", session_id)
                await send(msg_error(CODE_BAD_REQUEST, "Message must be a JSON object"))
                continue

            msg_type = data.get("type")
            try:
                if msg_type == TYPE_PING:
                    logger.debug("WS ping session=%s", session_id)
                    await send(msg_pong())
                elif msg_type == TYPE_CLEAR_SESSION:
                    logger.info("WS clear_session session=%s", session_id)
                    state.conversations.clear(session_id)
                    await send(msg_result(True, "session cleared"))
                elif msg_type == TYPE_GET_STATS:
                    logger.info("WS get_stats session=%s", session_id)
                    await send(
                        msg_stats(
                            {
                                "session_id": session_id,
                                "memory_count": state.orchestrator.memory_store.count(),
                                **state.orchestrator.stats,
                            }
                        )
                    )
                elif msg_type == TYPE_CHAT:
                    if (chat_task is not None and not chat_task.done()) or state.hub.is_busy(
                        session_id
                    ):
                        logger.warning(
                            "WS chat rejected session=%s reason=in_progress",
                            session_id,
                        )
                        await send(
                            msg_error(
                                CODE_BAD_REQUEST,
                                "A chat request is already in progress",
                            )
                        )
                        continue
                    chat_recv_at = time.perf_counter()
                    content = data.get("content", "")
                    options = data.get("options") or {}
                    if not isinstance(options, dict):
                        options = {}
                    logger.info(
                        "WS chat recv session=%s options=%s content=%r",
                        session_id,
                        options,
                        content,
                    )
                    if is_unusable_user_text(str(content)):
                        logger.warning(
                            "WS chat dropped session=%s reason=unusable_user_text "
                            "content=%r",
                            session_id,
                            content,
                        )
                        begin_trace(
                            started_at=chat_recv_at,
                            request_json=raw,
                        )
                        await send(
                            msg_chat_response(
                                ASR_FALLBACK_REPLY,
                                context_used="asr_filter",
                                latency=0.0,
                                emotion=ASR_FALLBACK_EMOTION,
                            )
                        )
                        continue
                    chat_task = asyncio.create_task(
                        _run_chat(
                            str(content),
                            options,
                            raw,
                            chat_recv_at,
                        )
                    )
                elif msg_type == TYPE_LISTEN_STATE:
                    raw_state = data.get("state") or data.get("listening")
                    if isinstance(raw_state, bool):
                        listening = raw_state
                    else:
                        listening = str(raw_state or "").strip().lower() in {
                            "on",
                            "true",
                            "1",
                            "start",
                        }
                    logger.info(
                        "WS listen_state session=%s listening=%s",
                        session_id,
                        listening,
                    )
                    await _cancel_commit()
                    wait_extended = False
                    if listening:
                        turn_buffer.set_listening(True)
                        state.hub.set_listening(session_id, True)
                    else:
                        logger.info(
                            "WS listen stop flush session=%s pending=%r",
                            session_id,
                            turn_buffer.joined(),
                        )
                        await _commit_turn(force=True)
                        turn_buffer.set_listening(False)
                        state.hub.set_listening(session_id, False)
                elif msg_type == TYPE_TRANSCRIPT:
                    text = str(data.get("content") or data.get("text") or "")
                    speaker = normalize_speaker(data.get("speaker"))
                    is_final = bool(data.get("is_final", True))
                    silence_ms = int(data.get("silence_ms") or 0)
                    segment_id = str(data.get("segment_id") or "")
                    logger.info(
                        "WS transcript session=%s final=%s speaker=%s silence_ms=%s "
                        "segment=%s content=%r",
                        session_id,
                        is_final,
                        speaker,
                        silence_ms,
                        segment_id,
                        text,
                    )
                    if not turn_buffer.listening:
                        logger.info(
                            "WS transcript ignored session=%s reason=not_listening",
                            session_id,
                        )
                        continue
                    if not is_final:
                        continue
                    if not is_teacher_speaker(speaker):
                        logger.info(
                            "WS transcript dropped session=%s reason=non_teacher speaker=%s",
                            session_id,
                            speaker,
                        )
                        continue
                    if is_unusable_user_text(text):
                        logger.info(
                            "WS transcript dropped session=%s reason=unusable content=%r",
                            session_id,
                            text,
                        )
                        continue
                    if state.scheduler is not None:
                        state.scheduler.note_user_activity()
                    turn_buffer.push(
                        text=text,
                        speaker=speaker,
                        segment_id=segment_id,
                        silence_ms=silence_ms,
                    )
                    _schedule_commit()
                elif msg_type == TYPE_INTERRUPT:
                    logger.info("WS interrupt session=%s", session_id)
                    await _interrupt_generation(restore_inflight=True)
                    if state.scheduler is not None:
                        state.scheduler.note_user_activity()
                else:
                    logger.warning(
                        "WS unknown type session=%s type=%r",
                        session_id,
                        msg_type,
                    )
                    await send(msg_error(CODE_BAD_REQUEST, f"Unknown type: {msg_type}"))
            except Exception as exc:
                logger.exception("Handler error session=%s", session_id)
                await send(msg_error(CODE_INTERNAL, str(exc)))
    except WebSocketDisconnect:
        logger.info("WS disconnected session=%s", session_id)
    finally:
        if commit_task is not None and not commit_task.done():
            commit_task.cancel()
            try:
                await commit_task
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception(
                    "Error while cancelling listen commit session=%s", session_id
                )
        if chat_task is not None and not chat_task.done():
            chat_task.cancel()
            try:
                await chat_task
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception("Error while cancelling chat task session=%s", session_id)
        state.hub.unregister(session_id)
        state.conversations.drop(session_id)
