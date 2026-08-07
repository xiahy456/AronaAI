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
            await send(msg_chat_response("", context_used="none", latency=0.0))
            return

        use_cache = bool(options.get("use_cache", self.config.cache.enabled))
        use_rag = bool(options.get("use_rag", self.config.knowledge.enabled))
        use_memory = bool(options.get("use_memory", True))
        do_stream = self.config.model.stream if stream is None else bool(stream)

        start = time.perf_counter()
        context_parts: list[str] = []

        if use_cache and self.config.cache.enabled:
            cached = self.cache.get(user_text)
            if cached is not None:
                self.stats["cache_hits"] += 1
                self.conversations.append(session_id, "user", user_text)
                self.conversations.append(session_id, "assistant", cached)
                latency = time.perf_counter() - start
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
                return

        memories: list[str] = []
        if use_memory:
            memories = await asyncio.to_thread(
                self.memory_store.retrieve,
                user_text,
                self.config.memory.retrieve_top_k,
            )
            if memories:
                context_parts.append("memory")

        knowledge_chunks: list[str] = []
        if use_rag:
            knowledge_chunks = await asyncio.to_thread(
                self.knowledge.retrieve,
                user_text,
                self.config.knowledge.retrieve_top_k,
            )
            if knowledge_chunks:
                context_parts.append("rag")

        history = self.conversations.get_history(session_id)
        if history:
            context_parts.append("history")

        messages = build_messages(
            self.config,
            user_text=user_text,
            history=history,
            memories=memories,
            knowledge=knowledge_chunks,
        )
        context_used = "+".join(context_parts) if context_parts else "none"

        if do_stream:
            self.stats["stream_count"] += 1
            full = await self._stream_generate(messages, send)
        else:
            full = await asyncio.to_thread(self.model.generate, messages, self.config)
            latency = time.perf_counter() - start
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

        if do_stream:
            # stream path already sent tokens; send final done already in _stream_generate
            pass

        await self._maybe_extract(session_id, user_text)
        self.stats["chat_count"] += 1
        logger.info(
            "chat session=%s stream=%s context=%s latency=%.3fs",
            session_id,
            do_stream,
            context_used,
            time.perf_counter() - start,
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
            return

        transcript = self.conversations.extract_buffer_transcript(session_id)
        if not transcript:
            return
        await self.extractor.enqueue(transcript=transcript, user_text=user_text)
        self.conversations.clear_extract_buffer(session_id)
