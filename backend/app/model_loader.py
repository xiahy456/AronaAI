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


class _LeadingJunkFilter:
    """Streaming filter that strips accidental leading punctuation once at the start."""

    def __init__(self) -> None:
        self._buf = ""
        self._done = False

    def feed(self, piece: str) -> str:
        if self._done:
            return piece or ""
        if not piece:
            return ""
        self._buf += piece
        if not self._can_release():
            return ""
        out = strip_leading_junk(self._buf)
        self._buf = ""
        if out:
            self._done = True
            return out
        return ""

    def _can_release(self) -> bool:
        s = self._buf.lstrip()
        if not s:
            return False
        if s[0] == _ELLIPSIS_CHAR:
            return True
        n = 0
        while n < len(s) and s[n] == ".":
            n += 1
        if 1 <= n < 3 and n == len(s):
            # 1–2 dots alone may still become an ellipsis
            return False
        return True

    def flush(self) -> str:
        if self._done:
            return ""
        out = strip_leading_junk(self._buf)
        self._buf = ""
        self._done = True
        return out


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

    def generate_stream(
        self, messages: list[dict[str, str]], config: AppConfig | None = None
    ) -> Iterator[str]:
        """Yield visible token deltas with think blocks and leading junk filtered out."""
        cfg = config or self._config
        if cfg is None:
            raise RuntimeError("Model not configured")
        if self._llm is None:
            raise RuntimeError("Model not loaded")

        logger.info(
            "create_chat_completion stream messages=%d max_tokens=%s temperature=%s",
            len(messages),
            cfg.model.max_new_tokens,
            cfg.model.temperature,
        )
        think_filter = _ThinkFilter()
        lead_filter = _LeadingJunkFilter()
        visible_chars = 0
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
                visible = lead_filter.feed(think_filter.feed(piece))
                if visible:
                    visible_chars += len(visible)
                    yield visible
            tail = lead_filter.feed(think_filter.flush())
            if tail:
                visible_chars += len(tail)
                yield tail
            final = lead_filter.flush()
            if final:
                visible_chars += len(final)
                yield final
        logger.info(
            "create_chat_completion stream done visible_chars=%d",
            visible_chars,
        )


_model_loader: ModelLoader | None = None


def get_model_loader() -> ModelLoader:
    global _model_loader
    if _model_loader is None:
        _model_loader = ModelLoader()
    return _model_loader
