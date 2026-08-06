"""WebSocket connection handler for Qt-compatible protocol."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from .config import AppConfig
from .conversation import ConversationManager
from .orchestrator import Orchestrator
from .protocol import (
    CODE_BAD_REQUEST,
    CODE_INTERNAL,
    CODE_INVALID_JSON,
    TYPE_CHAT,
    TYPE_CLEAR_SESSION,
    TYPE_GET_STATS,
    TYPE_PING,
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
    logger.info("WS connected session=%s", session_id)

    async def send(payload: dict[str, Any]) -> None:
        await websocket.send_text(json.dumps(payload, ensure_ascii=False))

    await send(msg_connected(session_id))

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await send(msg_error(CODE_INVALID_JSON, "Invalid JSON"))
                continue

            if not isinstance(data, dict):
                await send(msg_error(CODE_BAD_REQUEST, "Message must be a JSON object"))
                continue

            msg_type = data.get("type")
            try:
                if msg_type == TYPE_PING:
                    await send(msg_pong())
                elif msg_type == TYPE_CLEAR_SESSION:
                    state.conversations.clear(session_id)
                    await send(msg_result(True, "session cleared"))
                elif msg_type == TYPE_GET_STATS:
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
                    content = data.get("content", "")
                    stream = data.get("stream")
                    options = data.get("options") or {}
                    if not isinstance(options, dict):
                        options = {}
                    await state.orchestrator.handle_chat(
                        session_id=session_id,
                        content=str(content),
                        stream=stream if isinstance(stream, bool) else None,
                        options=options,
                        send=send,
                    )
                else:
                    await send(msg_error(CODE_BAD_REQUEST, f"Unknown type: {msg_type}"))
            except Exception as exc:
                logger.exception("Handler error session=%s", session_id)
                await send(msg_error(CODE_INTERNAL, str(exc)))
    except WebSocketDisconnect:
        logger.info("WS disconnected session=%s", session_id)
    finally:
        state.conversations.drop(session_id)
