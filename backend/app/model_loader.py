"""llama-cpp-python GGUF loader with sync and true streaming generation."""

from __future__ import annotations

import logging
import re
import threading
from collections.abc import Iterator
from typing import Any

from .config import AppConfig

logger = logging.getLogger(__name__)

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_OPEN_THINK = "<think>"
_CLOSE_THINK = "</think>"


def strip_think_tags(text: str) -> str:
    cleaned = _THINK_RE.sub("", text or "")
    return cleaned.strip()


class _ThinkFilter:
    """Streaming filter that drops <think>...</think> spans (including empty ones)."""

    def __init__(self) -> None:
        self._buf = ""
        self._in_think = False

    def feed(self, piece: str) -> str:
        if not piece:
            return ""
        self._buf += piece
        out: list[str] = []
        while self._buf:
            if self._in_think:
                end = self._buf.lower().find(_CLOSE_THINK)
                if end < 0:
                    keep = len(_CLOSE_THINK) - 1
                    if len(self._buf) > keep:
                        self._buf = self._buf[-keep:]
                    break
                self._buf = self._buf[end + len(_CLOSE_THINK) :].lstrip("\n\r")
                self._in_think = False
                continue

            start = self._buf.lower().find(_OPEN_THINK)
            if start < 0:
                hold = len(_OPEN_THINK) - 1
                if len(self._buf) > hold:
                    out.append(self._buf[:-hold] if hold else self._buf)
                    self._buf = self._buf[-hold:] if hold else ""
                break
            if start > 0:
                out.append(self._buf[:start])
            self._buf = self._buf[start + len(_OPEN_THINK) :]
            self._in_think = True
        return "".join(out)

    def flush(self) -> str:
        if self._in_think:
            self._buf = ""
            return ""
        leftover = self._buf
        self._buf = ""
        return leftover


class ModelLoader:
    """Process-wide singleton wrapper around llama-cpp Llama."""

    def __init__(self) -> None:
        self._llm: Any = None
        self._lock = threading.Lock()
        self._config: AppConfig | None = None

    def load(self, config: AppConfig) -> None:
        with self._lock:
            if self._llm is not None:
                return
            from llama_cpp import Llama

            path = config.gguf_abs_path
            if not path.is_file():
                raise FileNotFoundError(f"GGUF not found: {path}")

            logger.info("Loading GGUF from %s (n_ctx=%s)", path, config.model.n_ctx)
            self._llm = Llama(
                model_path=str(path),
                n_ctx=config.model.n_ctx,
                n_gpu_layers=config.model.n_gpu_layers,
                verbose=False,
            )
            self._config = config
            logger.info("Model loaded")

    @property
    def ready(self) -> bool:
        return self._llm is not None

    def generate(self, messages: list[dict[str, str]], config: AppConfig | None = None) -> str:
        cfg = config or self._config
        if cfg is None:
            raise RuntimeError("Model not configured")
        if self._llm is None:
            raise RuntimeError("Model not loaded")

        with self._lock:
            result = self._llm.create_chat_completion(
                messages=messages,
                max_tokens=cfg.model.max_new_tokens,
                temperature=cfg.model.temperature,
                top_p=cfg.model.top_p,
                repeat_penalty=cfg.model.repeat_penalty,
                stream=False,
            )
        content = result["choices"][0]["message"]["content"] or ""
        return strip_think_tags(content)

    def generate_stream(
        self, messages: list[dict[str, str]], config: AppConfig | None = None
    ) -> Iterator[str]:
        """Yield visible token deltas with <think> blocks filtered out."""
        cfg = config or self._config
        if cfg is None:
            raise RuntimeError("Model not configured")
        if self._llm is None:
            raise RuntimeError("Model not loaded")

        think_filter = _ThinkFilter()
        with self._lock:
            stream = self._llm.create_chat_completion(
                messages=messages,
                max_tokens=cfg.model.max_new_tokens,
                temperature=cfg.model.temperature,
                top_p=cfg.model.top_p,
                repeat_penalty=cfg.model.repeat_penalty,
                stream=True,
            )
            for chunk in stream:
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                piece = delta.get("content") or ""
                visible = think_filter.feed(piece)
                if visible:
                    yield visible
            tail = think_filter.flush()
            if tail:
                yield tail


_model_loader: ModelLoader | None = None


def get_model_loader() -> ModelLoader:
    global _model_loader
    if _model_loader is None:
        _model_loader = ModelLoader()
    return _model_loader
