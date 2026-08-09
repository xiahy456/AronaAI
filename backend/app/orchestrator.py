"""Chat orchestrator: retrieve -> prompt -> generate -> async memory extract."""

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
from .model_loader import ModelLoader, strip_think_tags
from .prompt import build_messages
from .protocol import msg_chat_response, msg_chat_stream

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
    ) -> None:
        self.config = config
        self.model = model
        self.conversations = conversations
        self.memory_store = memory_store
        self.extractor = extractor
        self.knowledge = knowledge
        self.cache = cache
        self.stats: dict[str, Any] = {
            "chat_count": 0,
            "cache_hits": 0,
            "stream_count": 0,
        }

    async def handle_chat(
        self,
        *,
        session_id: str,
        content: str,
        stream: bool | None,
        options: dict[str, Any],
        send: SendFn,
    ) -> None:
        user_text = (content or "").strip()
        if not user_text:
            logger.info("chat empty content session=%s", session_id)
            await send(msg_chat_response("", context_used="none", latency=0.0))
            return

        use_cache = bool(options.get("use_cache", self.config.cache.enabled))
        use_rag = bool(options.get("use_rag", self.config.knowledge.enabled))
        use_memory = bool(options.get("use_memory", True))
        do_stream = self.config.model.stream if stream is None else bool(stream)

        start = time.perf_counter()
        context_parts: list[str] = []

        logger.info(
            "chat start session=%s stream=%s use_cache=%s use_rag=%s use_memory=%s request=%r",
            session_id,
            do_stream,
            use_cache and self.config.cache.enabled,
            use_rag,
            use_memory,
            user_text,
        )

        if use_cache and self.config.cache.enabled:
            cached = self.cache.get(user_text)
            if cached is not None:
                self.stats["cache_hits"] += 1
                self.conversations.append(session_id, "user", user_text)
                self.conversations.append(session_id, "assistant", cached)
                latency = time.perf_counter() - start
                logger.info(
                    "cache hit session=%s latency=%.3fs response=%r",
                    session_id,
                    latency,
                    cached,
                )
                if do_stream:
                    await send(msg_chat_stream(cached, False))
                    await send(msg_chat_stream("", True))
                else:
                    await send(
                        msg_chat_response(
                            cached,
                            from_cache=True,
                            context_used="cache",
                            latency=round(latency, 4),
                        )
                    )
                await self._maybe_extract(session_id, user_text)
                self.stats["chat_count"] += 1
                logger.info(
                    "chat done session=%s stream=%s context=cache latency=%.3fs "
                    "request=%r response=%r",
                    session_id,
                    do_stream,
                    latency,
                    user_text,
                    cached,
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
            "prompt built session=%s messages=%d system_chars=%d context=%s",
            session_id,
            len(messages),
            system_chars,
            context_used,
        )

        if do_stream:
            self.stats["stream_count"] += 1
            logger.info("llm generate start session=%s mode=stream", session_id)
            t0 = time.perf_counter()
            full = await self._stream_generate(messages, send)
            logger.info(
                "llm generate done session=%s mode=stream latency=%.3fs chars=%d response=%r",
                session_id,
                time.perf_counter() - t0,
                len(full),
                full,
            )
        else:
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
                )
            )

        self.conversations.append(session_id, "user", user_text)
        self.conversations.append(session_id, "assistant", full)

        if use_cache and self.config.cache.enabled and full:
            self.cache.put(user_text, full)
            logger.info("cache put session=%s", session_id)

        await self._maybe_extract(session_id, user_text)
        self.stats["chat_count"] += 1
        total_latency = time.perf_counter() - start
        logger.info(
            "chat done session=%s stream=%s context=%s latency=%.3fs "
            "request=%r response=%r",
            session_id,
            do_stream,
            context_used,
            total_latency,
            user_text,
            full,
        )

    async def _stream_generate(self, messages: list[dict[str, str]], send: SendFn) -> str:
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[str | None] = asyncio.Queue()

        def _producer() -> None:
            try:
                for piece in self.model.generate_stream(messages, self.config):
                    asyncio.run_coroutine_threadsafe(queue.put(piece), loop).result()
            finally:
                asyncio.run_coroutine_threadsafe(queue.put(None), loop).result()

        producer_future = loop.run_in_executor(None, _producer)
        parts: list[str] = []
        while True:
            item = await queue.get()
            if item is None:
                break
            parts.append(item)
            await send(msg_chat_stream(item, False))

        await producer_future
        full = strip_think_tags("".join(parts))
        await send(msg_chat_stream("", True))
        logger.info(
            "stream finished chunks=%d chars=%d",
            len(parts),
            len(full),
        )
        return full

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
