"""Async DeepSeek memory extraction queue."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

import httpx

from ..config import ExtractorConfig, MemoryConfig
from .fallback import regex_extract_memories
from .normalize import normalize_memory_item
from .store import MemoryStore, normalize_content_for_compare
from .validate import memory_reject_reason

logger = logging.getLogger(__name__)

_HOT_KEYS = frozenset({"user_name", "preference_color", "user_birthday"})

EXTRACT_SYSTEM = """你是记忆抽取助手。根据「用户（老师）」与「阿洛娜」的对话片段，以及可选的【已有相关记忆】，提取需要长期记住或需要更新/清除的用户（老师）事实。
只输出 JSON，格式：
{"memories":[{"op":"upsert或delete","key":"英文蛇形键","content":"短中文陈述句","category":"preference|profile|goal|other"}]}
规则：
- 只提取已确认的精确事实（名字、偏好、约定、未完成的计划），不要闲聊、不要世界观百科。
- 无值得记忆的内容时返回 {"memories":[]}
- content 必须是短陈述句，例如「老师喜欢蓝色」；delete 时可省略 content 或沿用旧内容
- 禁止疑问句、反问、猜测或未确认信息；错误示例：「老师喜欢什么颜色吗」
- 不要把老师的提问本身当成事实写入
- category 含义：
  - preference：稳定偏好（颜色、食物等）
  - profile：档案信息（名字、生日等）
  - goal：未完成的计划/打算/约定（临时意图）
  - other：其它稳定事实
- 若提供了【已有相关记忆】：
  - 同主题新事实与旧记忆冲突时：upsert 新内容，并对旧 key 输出 op=delete（若新事实复用同一 key 则只需 upsert）
  - 优先复用已有记忆的 key；仅当主题全新时才新建 key
  - goal：对话表明该计划已执行、正在执行或已取消时，对该 goal 的 key 输出 op=delete，不要再 upsert
- 高频稳定 key（若适用请直接使用）：user_name、preference_color、user_birthday
- 只记录与用户（老师）相关的记忆；例如「老师喜欢蓝色」
- 记忆必须来自于用户（老师）所述。对于阿洛娜口述的老师记忆，除非得到老师肯定，否则判定为无效。
"""


def _format_existing_memories(entries: list[dict[str, Any]]) -> str:
    if not entries:
        return "【已有相关记忆】\n（无）"
    lines = ["【已有相关记忆】"]
    for e in entries:
        lines.append(
            f"- key={e.get('key')} | category={e.get('category') or 'other'} | content={e.get('content')}"
        )
    return "\n".join(lines)


def _category_of(item: dict[str, Any] | None, fallback: str | None = None) -> str:
    if item is not None:
        cat = item.get("category")
        if isinstance(cat, str) and cat.strip():
            return cat.strip()
    if isinstance(fallback, str) and fallback.strip():
        return fallback.strip()
    return "other"


def _pick_keep_key(
    new_key: str,
    candidates: list[dict[str, Any]],
) -> str:
    """Prefer hot slots, then new_key if already present, else highest-score candidate."""
    keys = {str(c.get("key") or "").strip() for c in candidates}
    keys.discard("")
    keys.add(new_key)

    for hot in ("preference_color", "user_name", "user_birthday"):
        if hot in keys:
            return hot
    if new_key in {str(c.get("key") or "").strip() for c in candidates}:
        return new_key
    ranked = sorted(
        (c for c in candidates if str(c.get("key") or "").strip()),
        key=lambda c: float(c.get("score") or 0.0),
        reverse=True,
    )
    if ranked:
        return str(ranked[0]["key"]).strip()
    return new_key


def _collapse_batch_upserts(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Within one extract batch, keep last upsert per normalized content; prefer hot keys."""
    deletes: list[dict[str, Any]] = []
    # group_key -> item (later overwrites earlier)
    groups: dict[str, dict[str, Any]] = {}
    group_order: list[str] = []

    for item in items:
        op = str(item.get("op") or "upsert").lower()
        if op == "delete":
            deletes.append(item)
            continue
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        gkey = normalize_content_for_compare(content)
        key = str(item.get("key") or "").strip()
        prev = groups.get(gkey)
        if prev is None:
            groups[gkey] = dict(item)
            group_order.append(gkey)
            continue
        # Later item wins content; prefer hot key when either side has one.
        merged = dict(item)
        prev_key = str(prev.get("key") or "").strip()
        if key not in _HOT_KEYS and prev_key in _HOT_KEYS:
            merged["key"] = prev_key
        elif key in _HOT_KEYS:
            merged["key"] = key
        elif prev_key and not key:
            merged["key"] = prev_key
        groups[gkey] = merged

    return deletes + [groups[k] for k in group_order]


class MemoryExtractor:
    def __init__(self, store: MemoryStore, config: ExtractorConfig) -> None:
        self.store = store
        self.config = config
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._worker_task: asyncio.Task[None] | None = None
        self._calls_today = 0
        self._calls_day = time.strftime("%Y-%m-%d")

    @property
    def memory_config(self) -> MemoryConfig:
        return self.store.config

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
            logger.info("memory extractor disabled; skip enqueue")
            return
        qsize = self._queue.qsize() + 1
        logger.info(
            "memory extract queued qsize=%d user_text=%r",
            qsize,
            user_text,
        )
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

    def _load_extract_context(self, user_text: str, transcript: str) -> list[dict[str, Any]]:
        query = (user_text or "").strip() or (transcript or "").strip()
        if not query:
            return []
        top_k = max(1, int(self.memory_config.extract_context_top_k))
        try:
            return self.store.retrieve_entries(query, top_k)
        except Exception:
            logger.exception("Failed to load extract context memories")
            return []

    async def _process(self, job: dict[str, Any]) -> None:
        transcript = job.get("transcript") or ""
        user_text = job.get("user_text") or ""
        logger.info(
            "memory extract start user_text=%r transcript_chars=%d",
            user_text,
            len(transcript),
        )

        existing = self._load_extract_context(user_text, transcript)
        memories: list[dict[str, Any]] = []
        used_api = False

        if self._under_quota() and self.config.api_key and self.config.api_key != "YOUR_DEEPSEEK_API_KEY":
            try:
                memories = await self._call_deepseek(transcript, existing)
                used_api = True
                self._calls_today += 1
                logger.info(
                    "DeepSeek extract ok calls_today=%d memories=%d items=%s",
                    self._calls_today,
                    len(memories),
                    memories,
                )
            except Exception as exc:
                logger.warning("DeepSeek extract failed: %s", exc)
                memories = []
        else:
            logger.info(
                "DeepSeek extract skipped under_quota=%s has_key=%s",
                self._under_quota(),
                bool(self.config.api_key and self.config.api_key != "YOUR_DEEPSEEK_API_KEY"),
            )

        if not memories and self.config.fallback == "regex":
            memories = regex_extract_memories(user_text)
            if memories:
                logger.info("Applied regex fallback memories: %s", memories)
            else:
                logger.info("regex fallback found no memories")

        source = "deepseek" if used_api else "regex"
        self._apply(memories, source=source)
        logger.info(
            "memory extract done source=%s applied=%d",
            source,
            len(memories),
        )

    async def _call_deepseek(
        self,
        transcript: str,
        existing: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        url = self.config.base_url.rstrip("/") + "/chat/completions"
        user_payload = (
            f"{_format_existing_memories(existing)}\n\n【对话片段】\n{transcript}"
        )
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": EXTRACT_SYSTEM},
                {"role": "user", "content": user_payload},
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

    def _reconcile_after_upsert(self, key: str, content: str, category: str | None) -> None:
        cfg = self.memory_config
        if not cfg.reconcile_enabled:
            return
        cat = (category or "other").strip() or "other"
        # Goals must only be cleared by explicit delete from extraction.
        if cat == "goal":
            return
        try:
            similar = self.store.find_similar(
                content,
                exclude_key=key,
                top_k=max(1, int(cfg.reconcile_top_k)),
                min_score=float(cfg.reconcile_min_score),
            )
        except Exception:
            logger.exception("reconcile find_similar failed key=%s", key)
            return

        for hit in similar:
            hit_key = str(hit.get("key") or "").strip()
            hit_cat = str(hit.get("category") or "other").strip() or "other"
            if not hit_key or hit_key == key:
                continue
            if hit_cat == "goal":
                continue
            if hit_cat != cat:
                continue
            score = float(hit.get("score") or 0.0)
            logger.info(
                "reconcile delete key=%s because of key=%s score=%.3f",
                hit_key,
                key,
                score,
            )
            self.store.delete(hit_key)

    def _collect_dedup_candidates(
        self,
        content: str,
        *,
        category: str,
        new_key: str,
    ) -> list[dict[str, Any]]:
        cfg = self.memory_config
        by_key: dict[str, dict[str, Any]] = {}

        try:
            for hit in self.store.find_exact_content(content):
                hit_key = str(hit.get("key") or "").strip()
                hit_cat = _category_of(hit)
                if not hit_key or hit_cat == "goal":
                    continue
                if hit_cat != category:
                    continue
                by_key[hit_key] = hit
        except Exception:
            logger.exception("dedup find_exact_content failed content=%r", content[:80])

        try:
            similar = self.store.find_similar(
                content,
                exclude_key=None,
                top_k=max(1, int(cfg.reconcile_top_k)),
                min_score=float(cfg.dedup_min_score),
            )
        except Exception:
            logger.exception("dedup find_similar failed content=%r", content[:80])
            similar = []

        for hit in similar:
            hit_key = str(hit.get("key") or "").strip()
            hit_cat = _category_of(hit)
            if not hit_key or hit_cat == "goal":
                continue
            if hit_cat != category:
                continue
            prev = by_key.get(hit_key)
            if prev is None or float(hit.get("score") or 0.0) > float(prev.get("score") or 0.0):
                by_key[hit_key] = hit

        # Self-hit on new_key alone is not a duplicate set.
        if set(by_key.keys()) <= {new_key}:
            return []
        return list(by_key.values())

    def _upsert_with_dedup(
        self,
        *,
        key: str,
        content: str,
        category: str | None,
        source: str,
    ) -> None:
        cfg = self.memory_config
        cat = (category or "other").strip() or "other"

        if not cfg.dedup_enabled or cat == "goal":
            self.store.upsert(key, content, category=category, source=source)
            self._reconcile_after_upsert(key, content, category)
            return

        candidates = self._collect_dedup_candidates(content, category=cat, new_key=key)
        if not candidates:
            self.store.upsert(key, content, category=category, source=source)
            self._reconcile_after_upsert(key, content, category)
            return

        keep_key = _pick_keep_key(key, candidates)
        drop_keys = sorted(
            {
                str(c.get("key") or "").strip()
                for c in candidates
                if str(c.get("key") or "").strip() and str(c.get("key") or "").strip() != keep_key
            }
            | ({key} if key != keep_key else set())
        )
        best_score = max((float(c.get("score") or 0.0) for c in candidates), default=0.0)
        self.store.upsert(keep_key, content, category=category, source=source)
        for drop in drop_keys:
            if drop == keep_key:
                continue
            self.store.delete(drop)
        logger.info(
            "dedup merge keep=%s drop=%s score=%.3f content=%r",
            keep_key,
            drop_keys,
            best_score,
            content,
        )
        self._reconcile_after_upsert(keep_key, content, category)

    def _apply(self, memories: list[dict[str, Any]], *, source: str) -> None:
        normalized: list[dict[str, Any]] = []
        for raw in memories:
            item = normalize_memory_item(raw)
            op = (item.get("op") or "upsert").lower()
            key = str(item.get("key") or "").strip()
            content = str(item.get("content") or "").strip()
            category = item.get("category")
            if isinstance(category, str):
                category = category.strip() or None
            else:
                category = None
            if not key:
                continue
            item = {
                "op": op,
                "key": key,
                "content": content,
                "category": category,
            }
            if op == "upsert" and content:
                reason = memory_reject_reason(key, content)
                if reason:
                    logger.info(
                        "memory upsert skipped reason=%s key=%r content=%r source=%s",
                        reason,
                        key,
                        content,
                        source,
                    )
                    continue
            normalized.append(item)

        for item in _collapse_batch_upserts(normalized):
            op = str(item.get("op") or "upsert").lower()
            key = str(item.get("key") or "").strip()
            content = str(item.get("content") or "").strip()
            category = item.get("category")
            if isinstance(category, str):
                category = category.strip() or None
            else:
                category = None
            if not key:
                continue
            if op == "delete":
                self.store.delete(key)
            elif op == "upsert" and content:
                self._upsert_with_dedup(
                    key=key,
                    content=content,
                    category=category,
                    source=source,
                )
