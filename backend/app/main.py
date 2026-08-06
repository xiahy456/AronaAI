"""AronaAI backend entrypoint."""

from __future__ import annotations

import logging
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
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
    uvicorn.run(
        "app.main:app",
        host=config.server.host,
        port=config.server.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
