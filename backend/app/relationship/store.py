"""JSON persistence for relationship climate."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .state import RelationshipState

logger = logging.getLogger(__name__)


class RelationshipStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> RelationshipState:
        if not self.path.is_file():
            return RelationshipState()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.exception("relationship load failed path=%s", self.path)
            return RelationshipState()
        if not isinstance(raw, dict):
            return RelationshipState()
        return RelationshipState.from_dict(raw)

    def save(self, state: RelationshipState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(state.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(self.path)
