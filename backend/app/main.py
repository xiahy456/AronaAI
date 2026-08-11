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
from .embeddings import LocalBgeEncoder
from .knowledge import KnowledgeRetriever
from .logging_utils import configure_logging
from .memory.extractor import MemoryExtractor
from .memory.store import MemoryStore
from .model_loader import get_model_loader
from .orchestrator import Orchestrator
from .planner import PlannerClient
from .ws_handler import AppState, websocket_endpoint


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


_configure_stdio_utf8()
configure_logging()
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    config = get_config()
    model = get_model_loader()
    conversations = ConversationManager(
        max_history_turns=config.conversation.max_history_turns
    )
    # Shared BGE encoder for memory + knowledge retrieval.
    shared_encoder = LocalBgeEncoder(config.knowledge_embedding_abs_path)
    memory_store = MemoryStore(config, encoder=shared_encoder)
    extractor = MemoryExtractor(memory_store, config.memory.extractor)
    knowledge = KnowledgeRetriever(config, encoder=shared_encoder)
    cache = ResponseCache(max_size=config.cache.max_size)
    planner = PlannerClient(config.planner)
    orchestrator = Orchestrator(
        config,
        model=model,
        conversations=conversations,
        memory_store=memory_store,
        extractor=extractor,
        knowledge=knowledge,
        cache=cache,
        planner=planner,
    )
    state = AppState(config, orchestrator, conversations)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        log_path = configure_logging()
        logger.info("Starting AronaAI backend")
        logger.info("Logging to %s", log_path)
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
    configure_logging()
    uvicorn.run(
        "app.main:app",
        host=config.server.host,
        port=config.server.port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
