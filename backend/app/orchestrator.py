"""Chat orchestrator: retrieve -> (plan) -> prompt -> generate -> async memory extract."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

AbortCheck = Callable[[], bool]

from .config import AppConfig
from .conversation import ConversationManager
from .knowledge import KnowledgeRetriever
from .logging_utils import begin_trace, preview, preview_list, reset_trace, update_trace
from .memory.extractor import MemoryExtractor
from .memory.store import MemoryStore
from .memory.trigger import should_extract
from .model_loader import ModelLoader
from .planner import DEFAULT_EMOTION, IntentCard, PlannerClient
from .proactive import (
    HISTORY_USER_MARKER,
    ResolvedSlot,
    build_welcome_instruction,
)
from .proactive.followup import (
    HISTORY_CONTINUE_MARKER,
    build_continue_instruction,
    should_skip_continue,
    too_similar,
)
from .prompt import build_messages, build_renderer_messages, clip_knowledge_for_inject
from .protocol import msg_chat_response
from .relationship import (
    Decision,
    RelationshipEngine,
    local_system_hint,
    planner_climate_block,
)

logger = logging.getLogger(__name__)

SendFn = Callable[[dict[str, Any]], Awaitable[None]]


class Orchestrator:
    def __init__(
        self,
        config: AppConfig,
        *,
        model: ModelLoader,
        conversations: ConversationManager,
        memory_store: MemoryStore,
        extractor: MemoryExtractor,
        knowledge: KnowledgeRetriever,
        planner: PlannerClient | None = None,
        relationship: RelationshipEngine | None = None,
    ) -> None:
        self.config = config
        self.model = model
        self.conversations = conversations
        self.memory_store = memory_store
        self.extractor = extractor
        self.knowledge = knowledge
        self.planner = planner or PlannerClient(config.planner)
        self.relationship = relationship
        self.stats: dict[str, Any] = {
            "chat_count": 0,
            "welcome_count": 0,
            "idle_count": 0,
            "care_count": 0,
            "goal_count": 0,
            "continue_count": 0,
            "festival_count": 0,
            "silence_count": 0,
            "refuse_count": 0,
            "planner_hits": 0,
            "planner_fallbacks": 0,
            "local_route_count": 0,
            "dual_route_count": 0,
        }

    async def handle_chat(
        self,
        *,
        session_id: str,
        content: str,
        options: dict[str, Any],
        send: SendFn,
        request_json: str | None = None,
        started_at: float | None = None,
        abort_check: AbortCheck | None = None,
        on_committed: Callable[[], None] | None = None,
    ) -> bool:
        def _aborted() -> bool:
            return abort_check is not None and abort_check()

        def _committed() -> None:
            if on_committed is not None:
                on_committed()

        begin_trace(started_at=started_at, request_json=request_json)
        user_text = (content or "").strip()
        if not user_text:
            logger.info("chat empty content session=%s", session_id)
            await send(
                msg_chat_response(
                    "",
                    context_used="none",
                    latency=0.0,
                    emotion=DEFAULT_EMOTION,
                )
            )
            return True

        use_rag = bool(options.get("use_rag", self.config.knowledge.enabled))
        use_memory = bool(options.get("use_memory", True))

        start = time.perf_counter()
        context_parts: list[str] = []
        decision = self._note_user_relationship(user_text)
        if decision is not None:
            context_parts.append("climate")
        if decision is not None and decision.action in {"silence", "refuse"}:
            reset_trace()
            await self._skip_generation(
                session_id=session_id,
                user_text=user_text,
                decision=decision,
            )
            _committed()
            return True

        logger.info(
            "chat start session=%s use_rag=%s use_memory=%s request=%r",
            session_id,
            use_rag,
            use_memory,
            user_text,
        )

        need_rag = use_rag and self.knowledge.enabled
        query_embedding: list[float] | None = None
        if use_memory or need_rag:
            t0 = time.perf_counter()
            try:
                query_embedding = await asyncio.to_thread(
                    self.memory_store.encode_query, user_text
                )
                logger.info(
                    "query embedding session=%s latency=%.3fs dim=%d",
                    session_id,
                    time.perf_counter() - t0,
                    len(query_embedding),
                )
            except Exception:
                logger.exception(
                    "query embedding failed session=%s; retrieve will encode itself",
                    session_id,
                )
                query_embedding = None

        memories: list[str] = []
        if use_memory:
            t0 = time.perf_counter()
            memories = await asyncio.to_thread(
                self.memory_store.retrieve,
                user_text,
                self.config.memory.retrieve_top_k,
                query_embedding,
                apply_inject_cooldown=True,
            )
            logger.info(
                "memory retrieve session=%s hits=%d latency=%.3fs items=%s",
                session_id,
                len(memories),
                time.perf_counter() - t0,
                preview_list(memories),
            )
            if memories:
                context_parts.append("memory")
        else:
            logger.info("memory retrieve skipped session=%s", session_id)

        knowledge_chunks: list[str] = []
        if use_rag:
            t0 = time.perf_counter()
            knowledge_chunks = await asyncio.to_thread(
                self.knowledge.retrieve,
                user_text,
                self.config.knowledge.retrieve_top_k,
                query_embedding,
            )
            logger.info(
                "rag retrieve session=%s hits=%d latency=%.3fs items=%s",
                session_id,
                len(knowledge_chunks),
                time.perf_counter() - t0,
                preview_list(knowledge_chunks),
            )
            if knowledge_chunks:
                context_parts.append("rag")
            before_clip = len(knowledge_chunks)
            knowledge_chunks = clip_knowledge_for_inject(self.config, knowledge_chunks)
            if len(knowledge_chunks) < before_clip:
                logger.info(
                    "rag inject clipped session=%s before=%d after=%d",
                    session_id,
                    before_clip,
                    len(knowledge_chunks),
                )
        else:
            logger.info("rag retrieve skipped session=%s", session_id)

        history = self.conversations.get_history(session_id)
        if history:
            context_parts.append("history")
        logger.info(
            "history session=%s turns=%d",
            session_id,
            len(history),
        )

        use_dual = self.planner.enabled
        if use_dual:
            self.stats["dual_route_count"] += 1
        else:
            self.stats["local_route_count"] += 1

        emotion = DEFAULT_EMOTION
        intent: IntentCard | None = None
        if use_dual:
            context_parts.append("planner")
            t0 = time.perf_counter()
            intent = await self.planner.plan(
                user_text=user_text,
                history=history,
                memories=memories,
                knowledge=knowledge_chunks,
                climate_block=self._climate_block(decision),
            )
            logger.info(
                "planner session=%s ok=%s latency=%.3fs",
                session_id,
                intent is not None,
                time.perf_counter() - t0,
            )
            if intent is None:
                self.stats["planner_fallbacks"] += 1
                logger.info("planner fallback to local path session=%s", session_id)
            else:
                self.stats["planner_hits"] += 1
                emotion = intent.arona_emotion
                self._merge_decision_into_intent(intent, decision)
                self._note_planner_user_act(intent.user_act)
                if not intent.reply_ok:
                    reset_trace()
                    await self._skip_generation(
                        session_id=session_id,
                        user_text=user_text,
                        decision=decision,
                        reason="reply_ok_false",
                    )
                    _committed()
                    return True

        if intent is not None:
            messages = build_renderer_messages(
                self.config,
                draft=intent.to_renderer_draft(),
            )
            context_parts.append("renderer")
        else:
            messages = build_messages(
                self.config,
                user_text=user_text,
                history=history,
                memories=memories,
                knowledge=knowledge_chunks,
                extra_system=self._local_hint(decision),
            )

        update_trace(renderer_prompt=messages)
        context_used = "+".join(context_parts) if context_parts else "none"
        system_chars = len(messages[0]["content"]) if messages else 0
        logger.info(
            "prompt built session=%s mode=%s messages=%d system_chars=%d context=%s emotion=%s",
            session_id,
            "renderer" if intent is not None else "local",
            len(messages),
            system_chars,
            context_used,
            emotion,
        )

        logger.info("llm generate start session=%s mode=sync", session_id)
        t0 = time.perf_counter()
        full = await asyncio.to_thread(self.model.generate, messages, self.config)
        latency = time.perf_counter() - start
        logger.info(
            "llm generate done session=%s mode=sync latency=%.3fs chars=%d response=%r",
            session_id,
            time.perf_counter() - t0,
            len(full),
            full,
        )
        update_trace(renderer_text=full)
        if _aborted():
            logger.info("chat aborted before send session=%s", session_id)
            reset_trace()
            return False
        await send(
            msg_chat_response(
                full,
                context_used=context_used,
                latency=round(latency, 4),
                emotion=emotion,
            )
        )

        self.conversations.append(session_id, "user", user_text)
        self.conversations.append(session_id, "assistant", full)
        _committed()

        await self._maybe_extract(session_id, user_text)
        self._note_arona_relationship(decision, "speak")
        self.stats["chat_count"] += 1
        total_latency = time.perf_counter() - start
        logger.info(
            "chat done session=%s context=%s emotion=%s latency=%.3fs "
            "request=%r response=%r",
            session_id,
            context_used,
            emotion,
            total_latency,
            user_text,
            full,
        )
        await self._maybe_continue(
            session_id=session_id,
            intent=intent,
            previous=full,
            send=send,
            climate=decision.climate if decision is not None else None,
            decision=decision,
            abort_check=abort_check,
        )
        return True

    async def handle_welcome(
        self,
        *,
        session_id: str,
        slot: ResolvedSlot,
        first_in_slot: bool,
        send: SendFn,
    ) -> bool:
        """Generate and push an online welcome greeting. Returns True on success."""
        climate = None
        if self.relationship is not None and self.config.proactive.relationship.enabled:
            climate = self.relationship.peek_climate()
        return await self.handle_initiate(
            session_id=session_id,
            kind="welcome",
            instruction=build_welcome_instruction(
                slot, first_in_slot=first_in_slot, climate=climate
            ),
            history_marker=HISTORY_USER_MARKER,
            send=send,
            retrieve_memory=False,
            climate_block=self._welcome_climate_block(climate),
            climate=climate,
        )

    async def handle_initiate(
        self,
        *,
        session_id: str,
        kind: str,
        instruction: str,
        history_marker: str,
        send: SendFn,
        retrieve_memory: bool = False,
        memory_query: str = "",
        extra_memories: list[str] | tuple[str, ...] | None = None,
        climate_block: str = "",
        climate: str | None = None,
        decision: Decision | None = None,
        continue_previous: str | None = None,
    ) -> bool:
        """Generate a system-event line (welcome / idle / care / goal / continue). Returns True on success."""
        user_text = instruction
        start = time.perf_counter()
        begin_trace(started_at=start)
        context_parts: list[str] = [kind]
        if climate or decision is not None:
            context_parts.append("climate")

        logger.info(
            "initiate start session=%s kind=%s instruction=%r",
            session_id,
            kind,
            user_text,
        )

        memories: list[str] = []
        injected = [
            item.strip()
            for item in (extra_memories or ())
            if (item or "").strip()
        ]
        if injected:
            memories = injected
            context_parts.append("memory")
            logger.info(
                "initiate memory injected session=%s kind=%s hits=%d",
                session_id,
                kind,
                len(memories),
            )
        elif retrieve_memory and memory_query:
            t0 = time.perf_counter()
            memories = await asyncio.to_thread(
                self.memory_store.retrieve,
                memory_query,
                self.config.memory.retrieve_top_k,
                apply_inject_cooldown=True,
            )
            logger.info(
                "initiate memory retrieve session=%s kind=%s hits=%d latency=%.3fs",
                session_id,
                kind,
                len(memories),
                time.perf_counter() - t0,
            )
            if memories:
                context_parts.append("memory")
        else:
            logger.info(
                "initiate memory retrieve skipped session=%s kind=%s",
                session_id,
                kind,
            )

        history = self.conversations.get_history(session_id)
        if history:
            context_parts.append("history")

        use_dual = self.planner.enabled
        if use_dual:
            self.stats["dual_route_count"] += 1
        else:
            self.stats["local_route_count"] += 1

        emotion = DEFAULT_EMOTION
        intent: IntentCard | None = None
        block = climate_block or self._climate_block(decision)
        if use_dual:
            context_parts.append("planner")
            t0 = time.perf_counter()
            intent = await self.planner.plan(
                user_text=user_text,
                history=history,
                memories=memories,
                knowledge=[],
                climate_block=block,
            )
            logger.info(
                "initiate planner session=%s kind=%s ok=%s latency=%.3fs",
                session_id,
                kind,
                intent is not None,
                time.perf_counter() - t0,
            )
            if intent is not None and not intent.reply_ok:
                if not intent.to_renderer_draft():
                    logger.info(
                        "initiate reply_ok=false empty draft treated as miss "
                        "session=%s kind=%s",
                        session_id,
                        kind,
                    )
                    intent = None
                else:
                    logger.info(
                        "initiate ignoring reply_ok=false session=%s kind=%s",
                        session_id,
                        kind,
                    )
            if intent is None:
                self.stats["planner_fallbacks"] += 1
                logger.info(
                    "initiate planner fallback session=%s kind=%s", session_id, kind
                )
            else:
                self.stats["planner_hits"] += 1
                emotion = intent.arona_emotion
                self._merge_decision_into_intent(intent, decision)

        if intent is not None:
            messages = build_renderer_messages(
                self.config,
                draft=intent.to_renderer_draft(),
            )
            context_parts.append("renderer")
        else:
            messages = build_messages(
                self.config,
                user_text=user_text,
                history=history,
                memories=memories,
                knowledge=[],
                extra_system=self._local_hint(decision) if decision is not None else None,
            )

        update_trace(renderer_prompt=messages)
        context_used = "+".join(context_parts)
        logger.info(
            "initiate prompt built session=%s kind=%s mode=%s context=%s emotion=%s",
            session_id,
            kind,
            "renderer" if intent is not None else "local",
            context_used,
            emotion,
        )

        t0 = time.perf_counter()
        full = await asyncio.to_thread(self.model.generate, messages, self.config)
        latency = time.perf_counter() - start
        logger.info(
            "initiate llm done session=%s kind=%s latency=%.3fs chars=%d response=%r",
            session_id,
            kind,
            time.perf_counter() - t0,
            len(full),
            full,
        )

        if not (full or "").strip():
            logger.warning(
                "initiate empty response session=%s kind=%s", session_id, kind
            )
            reset_trace()
            return False

        if kind == "continue" and too_similar(continue_previous or "", full):
            logger.info(
                "continue discarded session=%s reason=too_similar previous=%r cont=%r",
                session_id,
                continue_previous,
                full,
            )
            reset_trace()
            return False

        update_trace(renderer_text=full)
        await send(
            msg_chat_response(
                full,
                context_used=context_used,
                latency=round(latency, 4),
                emotion=emotion,
            )
        )

        self.conversations.append(session_id, "user", history_marker)
        self.conversations.append(session_id, "assistant", full)

        if self.relationship is not None and self.config.proactive.relationship.enabled:
            used_climate = (
                decision.climate if decision is not None else climate
            ) or "steady"
            if kind == "continue":
                self.relationship.on_arona_action("continue", used_climate)
            else:
                motive = None if kind == "welcome" else kind
                self.relationship.on_arona_action(
                    "initiate", used_climate, motive_kind=motive
                )
        stat_key = {
            "welcome": "welcome_count",
            "idle": "idle_count",
            "goal": "goal_count",
            "continue": "continue_count",
            "festival": "festival_count",
        }.get(kind, "care_count")
        self.stats[stat_key] = int(self.stats.get(stat_key, 0)) + 1
        self.stats["chat_count"] += 1
        logger.info(
            "initiate done session=%s kind=%s context=%s emotion=%s latency=%.3fs response=%r",
            session_id,
            kind,
            context_used,
            emotion,
            time.perf_counter() - start,
            full,
        )
        return True

    def _note_user_relationship(self, user_text: str) -> Decision | None:
        if self.relationship is None or not self.config.proactive.relationship.enabled:
            return None
        _act, decision = self.relationship.on_user_text(user_text)
        return decision

    def _note_planner_user_act(self, act: str) -> None:
        if self.relationship is None or not self.config.proactive.relationship.enabled:
            return
        self.relationship.note_planner_user_act(act)

    def _note_arona_relationship(
        self, decision: Decision | None, action: str
    ) -> None:
        if self.relationship is None or not self.config.proactive.relationship.enabled:
            return
        climate = decision.climate if decision is not None else "steady"
        user_act = decision.user_act if decision is not None else "other"
        self.relationship.on_arona_action(action, climate, user_act)  # type: ignore[arg-type]

    async def _maybe_continue(
        self,
        *,
        session_id: str,
        intent: IntentCard | None,
        previous: str,
        send: SendFn,
        climate: str | None,
        decision: Decision | None,
        abort_check: AbortCheck | None = None,
    ) -> None:
        if intent is None or not intent.followup_ok:
            return
        if not self.config.proactive.continue_line.enabled:
            return
        if not (previous or "").strip():
            return
        if should_skip_continue(previous):
            logger.info(
                "continue skipped session=%s reason=already_two_sentences",
                session_id,
            )
            return
        delay = float(self.config.proactive.continue_line.delay_sec or 0)
        if delay > 0:
            logger.info("continue delay session=%s sec=%s", session_id, delay)
            await asyncio.sleep(delay)
        if abort_check is not None and abort_check():
            logger.info("continue aborted session=%s", session_id)
            return
        logger.info("continue start session=%s", session_id)
        await self.handle_initiate(
            session_id=session_id,
            kind="continue",
            instruction=build_continue_instruction(previous),
            history_marker=HISTORY_CONTINUE_MARKER,
            send=send,
            retrieve_memory=False,
            climate=climate,
            decision=decision,
            continue_previous=previous.strip(),
        )

    def _climate_block(self, decision: Decision | None) -> str:
        if decision is None:
            return ""
        return planner_climate_block(decision)

    def _local_hint(self, decision: Decision | None) -> str | None:
        if decision is None:
            return None
        return local_system_hint(decision)

    def _welcome_climate_block(self, climate: str | None) -> str:
        if not climate:
            return ""
        from .relationship.policy import CLIMATE_LABELS

        label = CLIMATE_LABELS.get(climate, climate)
        return (
            f"【关系气候】{label}\n"
            "【建议姿态】简短迎接；可以加一句轻问帮老师开场。\n"
            "【本轮禁区】把问题抛回老师；\n"
            "draft 以问候为主，允许一句轻问。不要提及关系数值、信任度、依赖度或张力。"
        )

    def _merge_decision_into_intent(
        self, intent: IntentCard, decision: Decision | None
    ) -> None:
        """Relationship climate already reaches Planner via climate_block.

        V2.4: do not mutate draft from Decision card fields (must_not/stance/tone).
        """
        _ = intent, decision
        return

    async def _skip_generation(
        self,
        *,
        session_id: str,
        user_text: str,
        decision: Decision | None,
        reason: str | None = None,
    ) -> None:
        action = "silence" if reason == "reply_ok_false" else (
            decision.action if decision is not None else "silence"
        )
        key = "silence_count" if action == "silence" else "refuse_count"
        self.stats[key] = int(self.stats.get(key, 0)) + 1
        self.conversations.append(session_id, "user", user_text)
        if decision is not None:
            self._note_arona_relationship(decision, action)
        logger.info(
            "chat skipped session=%s action=%s climate=%s user_act=%s reason=%s request=%r",
            session_id,
            action,
            decision.climate if decision is not None else None,
            decision.user_act if decision is not None else None,
            reason or action,
            user_text,
        )

    async def _maybe_extract(self, session_id: str, user_text: str) -> None:
        # Buffer this completed turn (history was already appended by caller).
        history = self.conversations.get_history(session_id)
        if len(history) >= 2:
            self.conversations.append_extract_buffer(
                session_id, history[-2]["role"], history[-2]["content"]
            )
            self.conversations.append_extract_buffer(
                session_id, history[-1]["role"], history[-1]["content"]
            )

        ext = self.config.memory.extractor
        turn_count = self.conversations.turn_count(session_id)
        buffer_turns = self.conversations.extract_buffer_turn_count(session_id)
        if not should_extract(
            user_text,
            turn_count=turn_count,
            every_n_turns=ext.every_n_turns,
            buffer_turns=buffer_turns,
            extract_buffer_turns=ext.extract_buffer_turns,
        ):
            logger.info(
                "memory extract skipped session=%s turns=%d buffer_turns=%d",
                session_id,
                turn_count,
                buffer_turns,
            )
            return

        transcript = self.conversations.extract_buffer_transcript(session_id)
        if not transcript:
            logger.info("memory extract skipped session=%s reason=empty_transcript", session_id)
            return
        logger.info(
            "memory extract enqueue session=%s turns=%d buffer_turns=%d transcript=%s",
            session_id,
            turn_count,
            buffer_turns,
            preview(transcript, 300),
        )
        await self.extractor.enqueue(transcript=transcript, user_text=user_text)
        self.conversations.clear_extract_buffer(session_id)
