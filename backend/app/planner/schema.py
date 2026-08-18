"""Intent draft parsing, gating, and renderer-facing serialization (V2.4)."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from .emotions import DEFAULT_EMOTION, normalize_emotion

logger = logging.getLogger(__name__)

_JSON_OBJECT_RE = re.compile(r"\{[\s\S]*\}")


def _as_str(value: object | None, default: str = "") -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default


def _as_bool(value: object | None, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes"}
    return default


def _as_str_list(value: object | None) -> list[str]:
    """Legacy helper for old card fields ignored after parse."""
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
    return out


@dataclass
class IntentCard:
    """V2.4 intent: draft + emotion + followup_ok.

    Legacy card fields may still appear in raw JSON; they are parsed then ignored
    for rendering (to_renderer only exposes draft).
    """

    draft: str = ""
    arona_emotion: str = DEFAULT_EMOTION
    followup_ok: bool = False
    # Legacy (ignored by Renderer; kept so old payloads / tests don't explode)
    user_emotion: str = ""
    topic: str = ""
    stance: str = ""
    must_say: list[str] = field(default_factory=list)
    must_not: list[str] = field(default_factory=list)
    facts_to_use: list[str] = field(default_factory=list)
    tone: str = ""
    length: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IntentCard:
        draft = _as_str(data.get("draft"))
        # Soft migrate: if only old card fields exist, leave draft empty (gate fails).
        return cls(
            draft=draft,
            arona_emotion=normalize_emotion(data.get("arona_emotion")),
            followup_ok=_as_bool(data.get("followup_ok"), False),
            user_emotion=_as_str(data.get("user_emotion")),
            topic=_as_str(data.get("topic")),
            stance=_as_str(data.get("stance")),
            must_say=_as_str_list(data.get("must_say")),
            must_not=_as_str_list(data.get("must_not")),
            facts_to_use=_as_str_list(data.get("facts_to_use")),
            tone=_as_str(data.get("tone")),
            length=_as_str(data.get("length")),
        )

    def to_renderer_dict(self) -> dict[str, Any]:
        """Deprecated for V2.4; prefer to_renderer_draft()."""
        return {"draft": self.draft}

    def to_renderer_draft(self) -> str:
        return self.draft.strip()

    def to_renderer_text(self) -> str:
        return self.to_renderer_draft()


def extract_json_object(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if not raw:
        return None
    candidates = [raw]
    match = _JSON_OBJECT_RE.search(raw)
    if match:
        candidates.append(match.group(0))
    for cand in candidates:
        try:
            parsed = json.loads(cand)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def parse_and_gate_intent(raw_text: str) -> IntentCard | None:
    """Parse planner output into a gated IntentCard, or None on hard failure."""
    data = extract_json_object(raw_text)
    if data is None:
        return None
    card = IntentCard.from_dict(data)
    if not card.draft.strip():
        logger.info("planner gate failed: empty draft")
        return None
    return card
