"""Per-session sliding conversation window."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ConversationManager:
    max_history_turns: int = 6
    _sessions: dict[str, list[dict[str, str]]] = field(default_factory=dict)
    _turn_counts: dict[str, int] = field(default_factory=dict)

    def get_history(self, session_id: str) -> list[dict[str, str]]:
        return list(self._sessions.get(session_id, []))

    def append(self, session_id: str, role: str, content: str) -> None:
        history = self._sessions.setdefault(session_id, [])
        history.append({"role": role, "content": content})
        # Keep last N turns = 2N messages (user+assistant)
        max_messages = max(1, self.max_history_turns) * 2
        if len(history) > max_messages:
            self._sessions[session_id] = history[-max_messages:]
        if role == "user":
            self._turn_counts[session_id] = self._turn_counts.get(session_id, 0) + 1

    def turn_count(self, session_id: str) -> int:
        return self._turn_counts.get(session_id, 0)

    def clear(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        self._turn_counts.pop(session_id, None)

    def drop(self, session_id: str) -> None:
        self.clear(session_id)

    def recent_transcript(self, session_id: str, turns: int = 3) -> str:
        history = self.get_history(session_id)
        # last `turns` user+assistant pairs
        slice_msgs = history[-(turns * 2) :]
        lines: list[str] = []
        for msg in slice_msgs:
            role = "老师" if msg["role"] == "user" else "阿洛娜"
            lines.append(f"{role}: {msg['content']}")
        return "\n".join(lines)
