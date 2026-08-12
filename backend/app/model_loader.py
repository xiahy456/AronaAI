"""llama-cpp-python GGUF loader with sync generation."""

from __future__ import annotations

import logging
import re
import threading
import time
from typing import Any

from .config import AppConfig

logger = logging.getLogger(__name__)

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_LEADING_JUNK_PUNCT = frozenset(".,。、;；:：!！?？")
_ELLIPSIS_CHAR = "…"


def strip_think_tags(text: str) -> str:
    cleaned = _THINK_RE.sub("", text or "")
    return cleaned.strip()


def strip_leading_junk(text: str) -> str:
    """Remove accidental leading punctuation; keep ellipsis (… / ... / ......)."""
    s = (text or "").lstrip()
    while s:
        if s[0] == _ELLIPSIS_CHAR:
            break
        n = 0
        while n < len(s) and s[n] == ".":
            n += 1
        if n >= 3:
            break
        if n > 0:
            s = s[n:].lstrip()
            continue
        if s[0] in _LEADING_JUNK_PUNCT:
            s = s[1:].lstrip()
            continue
        break
    return s


def clean_model_output(text: str) -> str:
    return strip_leading_junk(strip_think_tags(text))


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

    def warmup(self) -> None:
        """Run a tiny sync completion so first user request is not GPU-cold."""
        if self._llm is None:
            logger.warning("Local LLM warmup skipped: model not loaded")
            return
        logger.info("Warming up local LLM")
        t0 = time.perf_counter()
        try:
            with self._lock:
                self._llm.create_chat_completion(
                    messages=[{"role": "user", "content": "hi"}],
                    max_tokens=1,
                    temperature=0,
                    stream=False,
                )
            logger.info(
                "Local LLM warmup done latency=%.3fs",
                time.perf_counter() - t0,
            )
        except Exception:
            logger.exception(
                "Local LLM warmup failed latency=%.3fs; first request may be cold",
                time.perf_counter() - t0,
            )

    @property
    def ready(self) -> bool:
        return self._llm is not None

    def generate(self, messages: list[dict[str, str]], config: AppConfig | None = None) -> str:
        cfg = config or self._config
        if cfg is None:
            raise RuntimeError("Model not configured")
        if self._llm is None:
            raise RuntimeError("Model not loaded")

        logger.info(
            "create_chat_completion sync messages=%d max_tokens=%s temperature=%s",
            len(messages),
            cfg.model.max_new_tokens,
            cfg.model.temperature,
        )
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
        cleaned = clean_model_output(content)
        usage = result.get("usage") or {}
        logger.info(
            "create_chat_completion sync done raw_chars=%d cleaned_chars=%d usage=%s",
            len(content),
            len(cleaned),
            usage,
        )
        return cleaned


_model_loader: ModelLoader | None = None


def get_model_loader() -> ModelLoader:
    global _model_loader
    if _model_loader is None:
        _model_loader = ModelLoader()
    return _model_loader
