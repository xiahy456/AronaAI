"""Load and validate backend configuration from YAML."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field


BACKEND_DIR = Path(__file__).resolve().parent.parent


class ServerConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 20456
    ws_path: str = "/ws"


class ModelConfig(BaseModel):
    gguf_path: str = "../models/AronaLM-Generator-V2.0/AronaLM-Generator-V2.0.Q4_K_M.gguf"
    n_ctx: int = 2048
    n_gpu_layers: int = -1
    max_new_tokens: int = 128
    temperature: float = 0.6
    top_p: float = 0.85
    repeat_penalty: float = 1.1


class PromptConfig(BaseModel):
    local_system_prompt: str = ""


class ConversationConfig(BaseModel):
    max_history_turns: int = 6


class KnowledgeConfig(BaseModel):
    enabled: bool = False
    corpus_dir: str = "data/knowledge/corpus"
    chroma_path: str = "data/knowledge/chroma"
    collection: str = "arona_lore"
    embedding_model_path: str = "../models/bge-small-zh-v1.5"
    retrieve_top_k: int = 2
    candidate_top_k: int = 8
    max_inject_chars: int = 400
    min_score: float = 0.45
    score_margin: float = 0.08


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
    extract_context_top_k: int = 8
    reconcile_enabled: bool = True
    reconcile_min_score: float = 0.82
    reconcile_top_k: int = 5
    dedup_enabled: bool = True
    dedup_min_score: float = 0.88
    extractor: ExtractorConfig = Field(default_factory=ExtractorConfig)


class PlannerConfig(BaseModel):
    """Big-LLM intent planner (separate from memory extractor)."""

    enabled: bool = True
    base_url: str = "https://api.deepseek.com"
    api_key: str = ""
    model: str = "deepseek-v4-flash"
    timeout_sec: float = 20
    temperature: float = 0.3
    max_tokens: int = 512
    # When True, greetings/identity use local AronaLM only.
    router_enabled: bool = True


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


class WelcomeConfig(BaseModel):
    enabled: bool = True


class IdleConfig(BaseModel):
    enabled: bool = True
    after_sec: float = 900
    cooldown_sec: float = 1800
    max_per_day: int = 3


class CareConfig(BaseModel):
    enabled: bool = True
    persist_path: str = "data/memory/proactive.json"
    lunch_start: str = "12:00"
    lunch_end: str = "12:30"
    sleep_start: str = "23:00"
    sleep_end: str = "23:20"


class GoalConfig(BaseModel):
    enabled: bool = True
    min_after_user_sec: float = 300
    cooldown_sec: float = 21600
    mute_sec: float = 604800
    max_per_day: int = 1


class FestivalConfig(BaseModel):
    enabled: bool = True


class ContinueConfig(BaseModel):
    enabled: bool = True
    delay_sec: float = 2


class RelationshipConfig(BaseModel):
    enabled: bool = True
    persist_path: str = "data/memory/relationship.json"
    alpha: float = 0.3
    beta: float = 0.02
    daily_abs_cap: float = 0.35
    makeup_tension: float = 0.7
    makeup_trust_scale: float = 1.5
    cling_dependence: float = 0.55
    high_dependence: float = 0.7
    climate_stick_turns: int = 3
    baseline_trust: float = 0.55
    baseline_dependence: float = 0.30
    baseline_tension: float = 0.25


class ProactiveConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    welcome: WelcomeConfig = Field(default_factory=WelcomeConfig)
    relationship: RelationshipConfig = Field(default_factory=RelationshipConfig)
    idle: IdleConfig = Field(default_factory=IdleConfig)
    care: CareConfig = Field(default_factory=CareConfig)
    goal: GoalConfig = Field(default_factory=GoalConfig)
    festival: FestivalConfig = Field(default_factory=FestivalConfig)
    continue_line: ContinueConfig = Field(
        default_factory=ContinueConfig,
        alias="continue",
    )


class AppConfig(BaseModel):
    server: ServerConfig = Field(default_factory=ServerConfig)
    model: ModelConfig = Field(default_factory=ModelConfig)
    prompt: PromptConfig = Field(default_factory=PromptConfig)
    conversation: ConversationConfig = Field(default_factory=ConversationConfig)
    knowledge: KnowledgeConfig = Field(default_factory=KnowledgeConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    planner: PlannerConfig = Field(default_factory=PlannerConfig)
    proactive: ProactiveConfig = Field(default_factory=ProactiveConfig)
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
    def relationship_abs_path(self) -> Path:
        return self.resolve_path(self.proactive.relationship.persist_path)

    @property
    def proactive_abs_path(self) -> Path:
        return self.resolve_path(self.proactive.care.persist_path)

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
