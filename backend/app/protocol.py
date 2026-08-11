"""WebSocket message type helpers aligned with Qt client."""

from __future__ import annotations

from typing import Any


# Client -> server
TYPE_CHAT = "chat"
TYPE_CLEAR_SESSION = "clear_session"
TYPE_GET_STATS = "get_stats"
TYPE_PING = "ping"

# Server -> client
TYPE_CONNECTED = "connected"
TYPE_CHAT_RESPONSE = "chat_response"
TYPE_CHAT_STREAM = "chat_stream"
TYPE_ERROR = "error"
TYPE_STATS = "stats"
TYPE_RESULT = "result"
TYPE_PONG = "pong"

CODE_INVALID_JSON = "INVALID_JSON"
CODE_INTERNAL = "INTERNAL_ERROR"
CODE_BAD_REQUEST = "BAD_REQUEST"


def msg_connected(session_id: str) -> dict[str, Any]:
    return {"type": TYPE_CONNECTED, "session_id": session_id}


def msg_pong() -> dict[str, Any]:
    return {"type": TYPE_PONG}


def msg_error(code: str, message: str) -> dict[str, Any]:
    return {"type": TYPE_ERROR, "code": code, "message": message}


def msg_chat_response(
    content: str,
    *,
    from_cache: bool = False,
    context_used: str = "none",
    latency: float = 0.0,
    emotion: str = "normal",
) -> dict[str, Any]:
    return {
        "type": TYPE_CHAT_RESPONSE,
        "content": content,
        "from_cache": from_cache,
        "context_used": context_used,
        "latency": latency,
        "emotion": emotion,
    }


def msg_chat_stream(content: str, done: bool) -> dict[str, Any]:
    return {"type": TYPE_CHAT_STREAM, "content": content, "done": done}


def msg_result(success: bool, message: str) -> dict[str, Any]:
    return {"type": TYPE_RESULT, "success": success, "message": message}


def msg_stats(payload: dict[str, Any]) -> dict[str, Any]:
    return {"type": TYPE_STATS, **payload}
