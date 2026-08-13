"""OpenAI-compatible planner client (separate from memory extractor)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from ..config import PlannerConfig
from .prompts import PLANNER_SYSTEM, build_planner_user_message
from .schema import IntentCard, parse_and_gate_intent

logger = logging.getLogger(__name__)


class PlannerClient:
    def __init__(self, config: PlannerConfig) -> None:
        self.config = config

    @property
    def enabled(self) -> bool:
        key = (self.config.api_key or "").strip()
        return bool(
            self.config.enabled
            and key
            and key != "YOUR_DEEPSEEK_API_KEY"
        )

    async def plan(
        self,
        *,
        user_text: str,
        history: list[dict[str, str]],
        memories: list[str],
        knowledge: list[str],
        climate_block: str = "",
    ) -> IntentCard | None:
        if not self.enabled:
            logger.info("planner skipped reason=disabled_or_no_key")
            return None

        url = self.config.base_url.rstrip("/") + "/chat/completions"
        user_payload = build_planner_user_message(
            user_text=user_text,
            history=history,
            memories=memories,
            knowledge=knowledge,
            climate_block=climate_block,
        )
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": PLANNER_SYSTEM},
                {"role": "user", "content": user_payload},
            ],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
        }
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout_sec) as client:
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
            content = data["choices"][0]["message"]["content"] or ""
            logger.info("planner raw json=%s", content)
            card = parse_and_gate_intent(content)
            if card is None:
                logger.warning("planner parse/gate failed raw=%s", content)
                return None
            logger.info(
                "planner ok emotion=%s topic=%r stance=%r",
                card.arona_emotion,
                card.topic,
                card.stance,
            )
            return card
        except Exception as exc:
            logger.warning("planner call failed: %s", exc)
            return None
