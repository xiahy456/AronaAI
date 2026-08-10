"""Shared helpers for structured pipeline logging."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .config import get_config

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

_APP_LOGGERS = (
    "app",
    "app.main",
    "app.ws_handler",
    "app.orchestrator",
    "app.model_loader",
    "app.knowledge",
    "app.memory.store",
    "app.memory.extractor",
)


def preview(text: str | None, max_len: int = 200) -> str:
    """Collapse whitespace and truncate for compact log lines."""
    s = " ".join((text or "").split())
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


def preview_list(items: list[str] | None, *, item_max: int = 80, list_max: int = 3) -> str:
    """Format a short preview of a string list for logs."""
    if not items:
        return "[]"
    shown = [preview(x, item_max) for x in items[:list_max]]
    extra = len(items) - list_max
    body = "; ".join(shown)
    if extra > 0:
        return f"[{body}; +{extra} more]"
    return f"[{body}]"


def _is_console_handler(handler: logging.Handler) -> bool:
    return isinstance(handler, logging.StreamHandler) and not isinstance(
        handler, logging.FileHandler
    )


def _is_target_file_handler(handler: logging.Handler, log_path: Path) -> bool:
    if not isinstance(handler, RotatingFileHandler):
        return False
    try:
        return Path(handler.baseFilename).resolve() == log_path.resolve()
    except Exception:
        return False


def configure_logging() -> Path:
    """Attach console + rotating file handlers to the root logger (idempotent)."""
    config = get_config()
    level_name = (config.logging.level or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    formatter = logging.Formatter(_LOG_FORMAT)

    log_dir = config.logging_dir_abs_path
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = config.logging_file_abs_path

    root = logging.getLogger()
    root.setLevel(level)

    has_console = False
    has_file = False
    for handler in root.handlers:
        handler.setLevel(level)
        handler.setFormatter(formatter)
        if _is_console_handler(handler):
            has_console = True
        if _is_target_file_handler(handler, log_path):
            has_file = True

    if not has_console:
        console = logging.StreamHandler()
        console.setLevel(level)
        console.setFormatter(formatter)
        root.addHandler(console)

    if not has_file:
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=config.logging.max_bytes,
            backupCount=config.logging.backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    # Keep app pipeline logs visible even if uvicorn tweaks root handlers later.
    for name in _APP_LOGGERS:
        logging.getLogger(name).setLevel(level)

    return log_path
