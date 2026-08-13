"""Chat orchestrator: retrieve -> (plan) -> prompt -> generate -> async memory extract."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from .cache import ResponseCache
from .config import AppConfig
from .conversation import ConversationManager
from .knowledge import KnowledgeRetriever
from .logging_utils import preview, preview_list
from .memory.extractor import MemoryExtractor
from .memory.store import MemoryStore
from .memory.trigger import should_extract
from .model_loader import ModelLoader
from .planner import DEFAULT_EMOTION, IntentCard, PlannerClient, route_mode
from .proactive import HISTORY_USER_MARKER, ResolvedSlot, build_welcome_instruction
from .prompt import build_messages, build_renderer_messages
from .protocol import msg_chat_response

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
        cache: ResponseCache,
        planner: PlannerClient | None = None,
    ) -> None:
        self.config = config
        self.model = model
        self.conversations = conversations
        self.memory_store = memory_store
        self.extractor = extractor
        self.knowledge = knowledge
        self.cache = cache
        self.planner = planner or PlannerClient(config.planner)
        self.stats: dict[str, Any] = {
            "chat_count": 0,
            "welcome_count": 0,
            "cache_hits": 0,
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
    ) -> None:
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
            return

        use_cache = bool(options.get("use_cache", self.config.cache.enabled))
        use_rag = bool(options.get("use_rag", self.config.knowledge.enabled))
        use_memory = bool(options.get("use_memory", True))

        start = time.perf_counter()
        context_parts: list[str] = []

        logger.info(
            "chat start session=%s use_cache=%s use_rag=%s use_memory=%s request=%r",
            session_id,
            use_cache and self.config.cache.enabled,
            use_rag,
            use_memory,
            user_text,
        )

        if use_cache and self.config.cache.enabled:
            cached = self.cache.get(user_text)
            if cached is not None:
                cached_text, cached_emotion = cached
                self.stats["cache_hits"] += 1
                self.conversations.append(session_id, "user", user_text)
                self.conversations.append(session_id, "assistant", cached_text)
                latency = time.perf_counter() - start
                logger.info(
                    "cache hit session=%s latency=%.3fs emotion=%s response=%r",
                    session_id,
                    latency,
                    cached_emotion,
                    cached_text,
                )
                await send(
                    msg_chat_response(
                        cached_text,
                        from_cache=True,
                        context_used="cache",
                        latency=round(latency, 4),
                        emotion=cached_emotion,
                    )
                )
                await self._maybe_extract(session_id, user_text)
                self.stats["chat_count"] += 1
                logger.info(
                    "chat done session=%s context=cache latency=%.3fs "
                    "request=%r response=%r",
                    session_id,
                    latency,
                    user_text,
                    cached_text,
                )
                return
            logger.info("cache miss session=%s", session_id)

        memories: list[str] = []
        if use_memory:
            t0 = time.perf_counter()
            memories = await asyncio.to_thread(
                self.memory_store.retrieve,
                user_text,
                self.config.memory.retrieve_top_k,
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

        mode = "local"
        if self.config.planner.router_enabled:
            mode = route_mode(user_text)
        elif self.planner.enabled:
            mode = "dual"

        use_dual = mode == "dual" and self.planner.enabled
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

        if intent is not None:
            messages = build_renderer_messages(
                self.config,
                user_text=user_text,
                intent_card=intent.to_renderer_dict(),
                history=history,
                max_history_turns=2,
            )
            context_parts.append("renderer")
        else:
            messages = build_messages(
                self.config,
                user_text=user_text,
                history=history,
                memories=memories,
                knowledge=knowledge_chunks,
            )

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
        await send(
            msg_chat_response(
                full,
                from_cache=False,
                context_used=context_used,
                latency=round(latency, 4),
                emotion=emotion,
            )
        )

        self.conversations.append(session_id, "user", user_text)
        self.conversations.append(session_id, "assistant", full)

        if use_cache and self.config.cache.enabled and full:
            self.cache.put(user_text, full, emotion)
            logger.info("cache put session=%s emotion=%s", session_id, emotion)

        await self._maybe_extract(session_id, user_text)
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

    async def handle_welcome(
        self,
        *,
        session_id: str,
        slot: ResolvedSlot,
        first_in_slot: bool,
        send: SendFn,
    ) -> bool:
        """Generate and push an online welcome greeting. Returns True on success."""
        user_text = build_welcome_instruction(slot, first_in_slot=first_in_slot)
        start = time.perf_counter()
        context_parts: list[str] = ["welcome"]

        logger.info(
            "welcome start session=%s slot=%s first=%s date=%s instruction=%r",
            session_id,
            slot.slot_id,
            first_in_slot,
            slot.date_key,
            user_text,
        )

        memories: list[str] = []
        t0 = time.perf_counter()
        memories = await asyncio.to_thread(
            self.memory_store.retrieve,
            user_text,
            self.config.memory.retrieve_top_k,
        )
        logger.info(
            "welcome memory retrieve session=%s hits=%d latency=%.3fs items=%s",
            session_id,
            len(memories),
            time.perf_counter() - t0,
            preview_list(memories),
        )
        if memories:
            context_parts.append("memory")

        history = self.conversations.get_history(session_id)
        if history:
            context_parts.append("history")

        mode = "local"
        if self.config.planner.router_enabled:
            mode = route_mode(user_text)
        elif self.planner.enabled:
            mode = "dual"

        use_dual = mode == "dual" and self.planner.enabled
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
                knowledge=[],
            )
            logger.info(
                "welcome planner session=%s ok=%s latency=%.3fs",
                session_id,
                intent is not None,
                time.perf_counter() - t0,
            )
            if intent is None:
                self.stats["planner_fallbacks"] += 1
                logger.info(
                    "welcome planner fallback to local path session=%s", session_id
                )
            else:
                self.stats["planner_hits"] += 1
                emotion = intent.arona_emotion

        if intent is not None:
            messages = build_renderer_messages(
                self.config,
                user_text=user_text,
                intent_card=intent.to_renderer_dict(),
                history=history,
                max_history_turns=2,
            )
            context_parts.append("renderer")
        else:
            messages = build_messages(
                self.config,
                user_text=user_text,
                history=history,
                memories=memories,
                knowledge=[],
            )

        context_used = "+".join(context_parts)
        logger.info(
            "welcome prompt built session=%s mode=%s context=%s emotion=%s",
            session_id,
            "renderer" if intent is not None else "local",
            context_used,
            emotion,
        )

        t0 = time.perf_counter()
        full = await asyncio.to_thread(self.model.generate, messages, self.config)
        latency = time.perf_counter() - start
        logger.info(
            "welcome llm done session=%s latency=%.3fs chars=%d response=%r",
            session_id,
            time.perf_counter() - t0,
            len(full),
            full,
        )

        if not (full or "").strip():
            logger.warning("welcome empty response session=%s", session_id)
            return False

        await send(
            msg_chat_response(
                full,
                from_cache=False,
                context_used=context_used,
                latency=round(latency, 4),
                emotion=emotion,
            )
        )

        # Keep history clean: short marker instead of system instruction.
        self.conversations.append(session_id, "user", HISTORY_USER_MARKER)
        self.conversations.append(session_id, "assistant", full)

        self.stats["welcome_count"] += 1
        self.stats["chat_count"] += 1
        logger.info(
            "welcome done session=%s context=%s emotion=%s latency=%.3fs response=%r",
            session_id,
            context_used,
            emotion,
            time.perf_counter() - start,
            full,
        )
        return True

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
