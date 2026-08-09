"""AronaAI backend entrypoint."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager

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
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(level=logging.INFO, format=_LOG_FORMAT)
    else:
        root.setLevel(logging.INFO)
        for handler in root.handlers:
            handler.setLevel(logging.INFO)
            handler.setFormatter(logging.Formatter(_LOG_FORMAT))
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
        logging.getLogger(name).setLevel(logging.INFO)


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
        logger.info("Starting AronaAI backend")
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
