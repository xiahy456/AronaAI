"""AronaAI backend entrypoint."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path

from fastapi import FastAPI, WebSocket

from .cache import ResponseCache
from .config import get_config
from .conversation import ConversationManager
from .knowledge import KnowledgeRetriever
from .memory.extractor import MemoryExtractor
from .memory.store import MemoryStore
from .model_loader import get_model_loader
from .orchestrator import Orchestrator
from .ws_handler import AppState, websocket_endpoint

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def _configure_stdio_utf8() -> None:
    """Force UTF-8 for terminal / redirected stdout & stderr (esp. Windows)."""
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYTHONUTF8", "1")
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError):
            pass
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            ctypes.windll.kernel32.SetConsoleCP(65001)
        except Exception:
            pass


def _configure_logging() -> None:
    """Attach console + rotating file handlers (re-callable after uvicorn resets root)."""
    config = get_config()
    level_name = (config.logging.level or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    formatter = logging.Formatter(_LOG_FORMAT)

    log_dir = config.logging_dir_abs_path
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = config.logging_file_abs_path.resolve()

    root = logging.getLogger()
    root.setLevel(level)

    has_stream = False
    has_file = False
    for handler in root.handlers:
        handler.setLevel(level)
        handler.setFormatter(formatter)
        if isinstance(handler, logging.StreamHandler) and not isinstance(
            handler, logging.FileHandler
        ):
            has_stream = True
        if isinstance(handler, RotatingFileHandler):
            try:
                if Path(getattr(handler, "baseFilename", "")).resolve() == log_file:
                    has_file = True
            except OSError:
                pass

    if not has_stream:
        stream = logging.StreamHandler(sys.stdout)
        stream.setLevel(level)
        stream.setFormatter(formatter)
        root.addHandler(stream)

    if not has_file:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=config.logging.max_bytes,
            backupCount=config.logging.backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    # Keep app pipeline logs visible even if uvicorn tweaks root handlers later.
    for name in (
        "app",
        "app.main",
        "app.ws_handler",
        "app.orchestrator",
        "app.model_loader",
        "app.knowledge",
        "app.memory.store",
        "app.memory.extractor",
    ):
        logging.getLogger(name).setLevel(level)


_configure_stdio_utf8()
_configure_logging()
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    config = get_config()
    model = get_model_loader()
    conversations = ConversationManager(
        max_history_turns=config.conversation.max_history_turns
    )
    memory_store = MemoryStore(config.memory_db_abs_path)
    extractor = MemoryExtractor(memory_store, config.memory.extractor)
    knowledge = KnowledgeRetriever(config)
    cache = ResponseCache(max_size=config.cache.max_size)
    orchestrator = Orchestrator(
        config,
        model=model,
        conversations=conversations,
        memory_store=memory_store,
        extractor=extractor,
        knowledge=knowledge,
        cache=cache,
    )
    state = AppState(config, orchestrator, conversations)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Uvicorn often resets root handlers; re-attach file logging after startup.
        _configure_logging()
        logger.info("Starting AronaAI backend")
        logger.info("Logging to %s", config.logging_file_abs_path.resolve())
        model.load(config)
        await asyncio.to_thread(memory_store.warmup)
        if knowledge.enabled:
            try:
                await asyncio.to_thread(knowledge.warmup)
            except Exception:
                logger.exception("Knowledge warmup failed; RAG will retry on first use")
        await extractor.start()
        app.state.arona = state  # type: ignore[attr-defined]
        yield
        await extractor.stop()
        logger.info("AronaAI backend stopped")

    app = FastAPI(title="AronaAI Backend", lifespan=lifespan)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    ws_path = config.server.ws_path or "/ws"

    @app.websocket(ws_path)
    async def ws_route(websocket: WebSocket) -> None:
        await websocket_endpoint(websocket, state)

    return app


app = create_app()


def main() -> None:
    import uvicorn

    config = get_config()
    _configure_stdio_utf8()
    _configure_logging()
    uvicorn.run(
        "app.main:app",
        host=config.server.host,
        port=config.server.port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
