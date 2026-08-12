"""Intent card parsing, gating, and renderer-facing serialization."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from .emotions import DEFAULT_EMOTION, normalize_emotion
from .prompts import FIXED_MUST_NOT

logger = logging.getLogger(__name__)

_JSON_OBJECT_RE = re.compile(r"\{[\s\S]*\}")
_MAX_MUST_SAY = 2
_ALLOWED_LENGTH = "1-2句"


def _as_str_list(value: object | None) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
    return out


def _as_str(value: object | None, default: str = "") -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default


@dataclass
class IntentCard:
    user_emotion: str = ""
    topic: str = ""
    stance: str = ""
    must_say: list[str] = field(default_factory=list)
    must_not: list[str] = field(default_factory=list)
    facts_to_use: list[str] = field(default_factory=list)
    tone: str = "温柔短句"
    length: str = "1-2句"
    arona_emotion: str = DEFAULT_EMOTION

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IntentCard:
        return cls(
            user_emotion=_as_str(data.get("user_emotion")),
            topic=_as_str(data.get("topic")),
            stance=_as_str(data.get("stance")),
            must_say=_as_str_list(data.get("must_say")),
            must_not=_as_str_list(data.get("must_not")),
            facts_to_use=_as_str_list(data.get("facts_to_use")),
            tone=_as_str(data.get("tone"), "温柔短句"),
            length=_as_str(data.get("length"), "1-2句"),
            arona_emotion=normalize_emotion(data.get("arona_emotion")),
        )

    def merge_fixed_must_not(self) -> None:
        seen = set(self.must_not)
        for item in FIXED_MUST_NOT:
            if item not in seen:
                self.must_not.append(item)
                seen.add(item)

    def normalize_length_and_must_say(self) -> None:
        """Clamp length/must_say so Renderer is not forced into 3+ sentences."""
        if self.length != _ALLOWED_LENGTH:
            logger.info(
                "planner gate length normalized from %r to %r",
                self.length,
                _ALLOWED_LENGTH,
            )
            self.length = _ALLOWED_LENGTH
        if len(self.must_say) > _MAX_MUST_SAY:
            logger.info(
                "planner gate must_say truncated %d -> %d topic=%r",
                len(self.must_say),
                _MAX_MUST_SAY,
                self.topic,
            )
            self.must_say = self.must_say[:_MAX_MUST_SAY]

    def to_renderer_dict(self) -> dict[str, Any]:
        """Intent fields for AronaLM — emotion stripped."""
        return {
            "user_emotion": self.user_emotion,
            "topic": self.topic,
            "stance": self.stance,
            "must_say": self.must_say,
            "must_not": self.must_not,
            "facts_to_use": self.facts_to_use,
            "tone": self.tone,
            "length": self.length,
        }

    def to_renderer_text(self) -> str:
        payload = self.to_renderer_dict()
        return json.dumps(payload, ensure_ascii=False)


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
    card.merge_fixed_must_not()
    card.normalize_length_and_must_say()
    # Soft gate: empty planning is weak but still usable if emotion is valid.
    if not card.topic and not card.must_say and not card.stance:
        # Still allow if we at least got emotion; otherwise fail.
        if card.arona_emotion == DEFAULT_EMOTION and not data.get("arona_emotion"):
            return None
    return card
