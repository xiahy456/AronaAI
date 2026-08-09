"""WebSocket connection handler for Qt-compatible protocol."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from .config import AppConfig
from .conversation import ConversationManager
from .logging_utils import preview
from .orchestrator import Orchestrator
from .protocol import (
    CODE_BAD_REQUEST,
    CODE_INTERNAL,
    CODE_INVALID_JSON,
    TYPE_CHAT,
    TYPE_CHAT_RESPONSE,
    TYPE_CHAT_STREAM,
    TYPE_CLEAR_SESSION,
    TYPE_CONNECTED,
    TYPE_GET_STATS,
    TYPE_PING,
    TYPE_PONG,
    msg_connected,
    msg_error,
    msg_pong,
    msg_result,
    msg_stats,
)

logger = logging.getLogger(__name__)


class AppState:
    def __init__(
        self,
        config: AppConfig,
        orchestrator: Orchestrator,
        conversations: ConversationManager,
    ) -> None:
        self.config = config
        self.orchestrator = orchestrator
        self.conversations = conversations


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

    async def send(payload: dict[str, Any]) -> None:
        msg_type = payload.get("type")
        if msg_type == TYPE_CHAT_RESPONSE:
            logger.info(
                "WS send session=%s type=%s from_cache=%s context=%s latency=%s content=%r",
                session_id,
                msg_type,
                payload.get("from_cache"),
                payload.get("context_used"),
                payload.get("latency"),
                payload.get("content", ""),
            )
        elif msg_type == TYPE_CHAT_STREAM:
            if payload.get("done"):
                logger.info("WS send session=%s type=%s done=True", session_id, msg_type)
            else:
                logger.debug(
                    "WS send session=%s type=%s chunk=%s",
                    session_id,
                    msg_type,
                    preview(str(payload.get("content", "")), 80),
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

    chat_task: asyncio.Task[None] | None = None

    async def _run_chat(
        content: str,
        stream: bool | None,
        options: dict[str, Any],
    ) -> None:
        try:
            await state.orchestrator.handle_chat(
                session_id=session_id,
                content=content,
                stream=stream,
                options=options,
                send=send,
            )
        except asyncio.CancelledError:
            logger.info("chat cancelled session=%s", session_id)
            raise
        except Exception as exc:
            logger.exception("Handler error session=%s", session_id)
            try:
                await send(msg_error(CODE_INTERNAL, str(exc)))
            except Exception:
                pass

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
                    if chat_task is not None and not chat_task.done():
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
                    content = data.get("content", "")
                    stream = data.get("stream")
                    options = data.get("options") or {}
                    if not isinstance(options, dict):
                        options = {}
                    logger.info(
                        "WS chat recv session=%s stream=%s options=%s content=%r",
                        session_id,
                        stream,
                        options,
                        content,
                    )
                    chat_task = asyncio.create_task(
                        _run_chat(
                            str(content),
                            stream if isinstance(stream, bool) else None,
                            options,
                        )
                    )
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
        if chat_task is not None and not chat_task.done():
            chat_task.cancel()
            try:
                await chat_task
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception("Error while cancelling chat task session=%s", session_id)
        state.conversations.drop(session_id)
