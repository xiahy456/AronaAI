"""Async DeepSeek memory extraction queue."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

import httpx

from ..config import ExtractorConfig
from .fallback import regex_extract_memories
from .store import MemoryStore

logger = logging.getLogger(__name__)

EXTRACT_SYSTEM = """你是记忆抽取助手。根据对话片段，提取需要长期记住的用户（老师）事实。
只输出 JSON，格式：
{"memories":[{"op":"upsert或delete","key":"英文蛇形键","content":"短中文陈述句","category":"preference|profile|other"}]}
规则：
- 只提取稳定事实（名字、偏好、约定），不要闲聊、不要世界观百科
- 无值得记忆的内容时返回 {"memories":[]}
- content 必须是短陈述句，例如「老师喜欢草莓牛奶」
- key 稳定可复用，同事实用同一 key
"""


class MemoryExtractor:
    def __init__(self, store: MemoryStore, config: ExtractorConfig) -> None:
        self.store = store
        self.config = config
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._worker_task: asyncio.Task[None] | None = None
        self._calls_today = 0
        self._calls_day = time.strftime("%Y-%m-%d")

    async def start(self) -> None:
        if self._worker_task is None:
            self._worker_task = asyncio.create_task(self._worker(), name="memory-extractor")

    async def stop(self) -> None:
        if self._worker_task is not None:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None

    async def enqueue(self, *, transcript: str, user_text: str) -> None:
        if not self.config.enabled:
            return
        await self._queue.put({"transcript": transcript, "user_text": user_text})

    def _reset_daily_if_needed(self) -> None:
        today = time.strftime("%Y-%m-%d")
        if today != self._calls_day:
            self._calls_day = today
            self._calls_today = 0

    def _under_quota(self) -> bool:
        self._reset_daily_if_needed()
        return self._calls_today < self.config.max_calls_per_day

    async def _worker(self) -> None:
        while True:
            job = await self._queue.get()
            try:
                await self._process(job)
            except Exception:
                logger.exception("Memory extraction job failed")
            finally:
                self._queue.task_done()

    async def _process(self, job: dict[str, Any]) -> None:
        transcript = job.get("transcript") or ""
        user_text = job.get("user_text") or ""

        memories: list[dict[str, Any]] = []
        used_api = False

        if self._under_quota() and self.config.api_key and self.config.api_key != "YOUR_DEEPSEEK_API_KEY":
            try:
                memories = await self._call_deepseek(transcript)
                used_api = True
                self._calls_today += 1
            except Exception as exc:
                logger.warning("DeepSeek extract failed: %s", exc)
                memories = []

        if not memories and self.config.fallback == "regex":
            memories = regex_extract_memories(user_text)
            if memories:
                logger.info("Applied regex fallback memories: %s", memories)

        source = "deepseek" if used_api else "regex"
        self._apply(memories, source=source)

    async def _call_deepseek(self, transcript: str) -> list[dict[str, Any]]:
        url = self.config.base_url.rstrip("/") + "/chat/completions"
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": EXTRACT_SYSTEM},
                {"role": "user", "content": transcript},
            ],
            "temperature": 0.1,
            "max_tokens": 512,
            "response_format": {"type": "json_object"},
            # DeepSeek V4: disable thinking for extraction
            "thinking": {"type": "disabled"},
        }
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self.config.timeout_sec) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        content = data["choices"][0]["message"]["content"] or "{}"
        parsed = json.loads(content)
        items = parsed.get("memories") or []
        if not isinstance(items, list):
            return []
        return [item for item in items if isinstance(item, dict)]

    def _apply(self, memories: list[dict[str, Any]], *, source: str) -> None:
        for item in memories:
            op = (item.get("op") or "upsert").lower()
            key = str(item.get("key") or "").strip()
            content = str(item.get("content") or "").strip()
            category = item.get("category")
            if not key:
                continue
            if op == "delete":
                self.store.delete(key)
            elif op == "upsert" and content:
                self.store.upsert(key, content, category=category, source=source)
