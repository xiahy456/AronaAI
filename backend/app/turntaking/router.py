"""Hybrid addressee router: rules first, short LLM on low-confidence cases."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from .llm_router import LlmTurnRouter
from .rules import (
    ACTION_IGNORE,
    ACTION_REPLY,
    ACTION_WAIT,
    RuleDecision,
    decide_rules,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RouteResult:
    action: str
    reason: str
    source: str


class AddressRouter:
    def __init__(self, llm: LlmTurnRouter | None = None) -> None:
        self.llm = llm

    def rules(
        self,
        *,
        text: str,
        seconds_since_arona: float | None,
        continuation_window_sec: float,
        already_waited: bool = False,
    ) -> RuleDecision:
        return decide_rules(
            text=text,
            seconds_since_arona=seconds_since_arona,
            continuation_window_sec=continuation_window_sec,
            already_waited=already_waited,
        )

    async def decide(
        self,
        *,
        text: str,
        seconds_since_arona: float | None,
        continuation_window_sec: float,
        already_waited: bool,
        last_arona: str,
        silence_ms: int,
    ) -> RouteResult:
        rule = self.rules(
            text=text,
            seconds_since_arona=seconds_since_arona,
            continuation_window_sec=continuation_window_sec,
            already_waited=already_waited,
        )
        if rule.action == ACTION_WAIT:
            return RouteResult(ACTION_WAIT, rule.reason, "rules")
        if rule.confidence == "high":
            return RouteResult(rule.action, rule.reason, "rules")

        llm_action: str | None = None
        if self.llm is not None and self.llm.enabled:
            llm_action = await self.llm.route(
                user_text=text,
                last_arona=last_arona,
                silence_ms=silence_ms,
                seconds_since_arona=seconds_since_arona,
            )
        if llm_action in {ACTION_IGNORE, ACTION_WAIT, ACTION_REPLY}:
            logger.info(
                "router hybrid rules=%s/%s llm=%s",
                rule.action,
                rule.reason,
                llm_action,
            )
            return RouteResult(llm_action, "llm", "llm")

        logger.info(
            "router fallback rules action=%s reason=%s",
            rule.action,
            rule.reason,
        )
        return RouteResult(rule.action, rule.reason, "rules_fallback")
