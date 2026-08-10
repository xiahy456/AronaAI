"""Load and validate backend configuration from YAML."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


BACKEND_DIR = Path(__file__).resolve().parent.parent


class ServerConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 20456
    ws_path: str = "/ws"


class ModelConfig(BaseModel):
    gguf_path: str = "../models/aronalm-v2.0-normal/aronalm-v2.0-normal.Q4_K_M.gguf"
    n_ctx: int = 2048
    n_gpu_layers: int = -1
    max_new_tokens: int = 128
    temperature: float = 0.6
    top_p: float = 0.85
    repeat_penalty: float = 1.1
    stream: bool = False
    system_prompt: str = ""


class ConversationConfig(BaseModel):
    max_history_turns: int = 6


class KnowledgeConfig(BaseModel):
    enabled: bool = False
    corpus_dir: str = "data/knowledge/corpus"
    chroma_path: str = "data/knowledge/chroma"
    collection: str = "arona_lore"
    embedding_model_path: str = "../models/bge-small-zh-v1.5"
    retrieve_top_k: int = 3
    max_inject_chars: int = 400
    min_score: float = 0.3


class ExtractorConfig(BaseModel):
    enabled: bool = True
    base_url: str = "https://api.deepseek.com"
    api_key: str = ""
    model: str = "deepseek-v4-flash"
    timeout_sec: float = 15
    max_calls_per_day: int = 200
    every_n_turns: int = 6
    extract_buffer_turns: int = 6
    fallback: str = "regex"


class MemoryConfig(BaseModel):
    db_path: str = "data/memory/memory.db"
    chroma_path: str = "data/memory/chroma"
    collection: str = "arona_memory"
    retrieve_top_k: int = 3
    candidate_top_k: int = 10
    min_score: float = 0.35
    max_inject_chars: int = 400
    extractor: ExtractorConfig = Field(default_factory=ExtractorConfig)


class CacheConfig(BaseModel):
    enabled: bool = True
    max_size: int = 256


class TokenBudgetConfig(BaseModel):
    memory: int = 250
    knowledge: int = 250
    history: int = 700


class LoggingConfig(BaseModel):
    dir: str = "logs"
    filename: str = "arona-backend.log"
    level: str = "INFO"
    max_bytes: int = 10_485_760
    backup_count: int = 5


class AppConfig(BaseModel):
    server: ServerConfig = Field(default_factory=ServerConfig)
    model: ModelConfig = Field(default_factory=ModelConfig)
    conversation: ConversationConfig = Field(default_factory=ConversationConfig)
    knowledge: KnowledgeConfig = Field(default_factory=KnowledgeConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    token_budget: TokenBudgetConfig = Field(default_factory=TokenBudgetConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    def resolve_path(self, relative: str) -> Path:
        path = Path(relative)
        if path.is_absolute():
            return path
        return (BACKEND_DIR / path).resolve()

    @property
    def gguf_abs_path(self) -> Path:
        return self.resolve_path(self.model.gguf_path)

    @property
    def memory_db_abs_path(self) -> Path:
        return self.resolve_path(self.memory.db_path)

    @property
    def memory_chroma_abs_path(self) -> Path:
        return self.resolve_path(self.memory.chroma_path)

    @property
    def knowledge_corpus_abs_path(self) -> Path:
        return self.resolve_path(self.knowledge.corpus_dir)

    @property
    def knowledge_chroma_abs_path(self) -> Path:
        return self.resolve_path(self.knowledge.chroma_path)

    @property
    def knowledge_embedding_abs_path(self) -> Path:
        return self.resolve_path(self.knowledge.embedding_model_path)

    @property
    def logging_dir_abs_path(self) -> Path:
        return self.resolve_path(self.logging.dir)

    @property
    def logging_file_abs_path(self) -> Path:
        return self.logging_dir_abs_path / self.logging.filename


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(config_path: Path | None = None) -> AppConfig:
    example_path = BACKEND_DIR / "config.example.yaml"
    user_path = config_path or (BACKEND_DIR / "config.yaml")

    data: dict[str, Any] = {}
    if example_path.is_file():
        with example_path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

    if user_path.is_file():
        with user_path.open(encoding="utf-8") as f:
            user_data = yaml.safe_load(f) or {}
        data = _deep_merge(data, user_data)

    return AppConfig.model_validate(data)


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    return load_config()
