"""
Arona AI 后端配置文件
支持从 config.yaml 加载配置，同时保持向后兼容
"""
import os
import yaml
from pathlib import Path

# 当前文件所在目录
_BACKEND_DIR = Path(__file__).parent

# YAML 配置文件路径
_CONFIG_YAML_PATH = _BACKEND_DIR / "config.yaml"


def _load_yaml_config() -> dict:
    """
    从 YAML 文件加载配置
    如果文件不存在或加载失败，返回空字典
    """
    if not _CONFIG_YAML_PATH.exists():
        print(f"警告: 配置文件 {_CONFIG_YAML_PATH} 不存在，将使用默认配置")
        return {}

    try:
        with open(_CONFIG_YAML_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        if config is None:
            return {}
        return config
    except Exception as e:
        print(f"警告: 加载配置文件失败: {e}，将使用默认配置")
        return {}


# 加载 YAML 配置
_YAML_CONFIG = _load_yaml_config()

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# ========== 模型配置 ==========
MODEL_CONFIG = {
    # "gguf" = llama-cpp-python 加载 GGUF；"hf" = Transformers + PEFT LoRA
    "backend": "gguf",
    "gguf_path": str(
        PROJECT_ROOT
        / "models"
        / "aronalm-v2.0-normal-gguf"
        / "Qwen3-1.7B.Q4_K_M.gguf"
    ),
    "n_ctx": 2048,
    "n_gpu_layers": -1,  # -1 = 尽量全部上 GPU；OOM 时改为较小正整数
    "base_model_name": "D:/Code/projects/Arona/arona-ai/models/hunyuan",
    "lora_path": "D:/Code/projects/Arona/arona-ai/models/aronalm/normal",
    "torch_dtype": "float16",
    "device_map": "auto",
    "max_new_tokens": 128,
    "temperature": 0.6,
    "top_p": 0.85,
    "top_k": 50,
    "repetition_penalty": 1.1,
    "max_length": 512,
}

# 从 YAML 覆盖（如果存在）
if "model" in _YAML_CONFIG:
    MODEL_CONFIG.update(_YAML_CONFIG["model"])

# 相对 gguf_path 基于项目根目录解析
_gguf = MODEL_CONFIG.get("gguf_path")
if _gguf and not os.path.isabs(_gguf):
    MODEL_CONFIG["gguf_path"] = str((PROJECT_ROOT / _gguf).resolve())

# ========== 嵌入模型配置 ==========
EMBEDDING_CONFIG = {
    "use_external": True,  # True=使用外部sentence-transformers模型, False=使用本地TF-IDF+SVD
    "model_name": "paraphrase-multilingual-MiniLM-L12-v2",  # 支持中文的轻量级嵌入模型
    "model_path": "D:/Code/projects/Arona/arona-ai/models/paraphrase-multilingual-MiniLM-L12-v2",  # 本地模型路径
    "device": "cpu",
}

# 从 YAML 覆盖（如果存在）
if "embedding" in _YAML_CONFIG:
    EMBEDDING_CONFIG.update(_YAML_CONFIG["embedding"])

# ========== 向量数据库配置 ==========
VECTOR_DB_CONFIG = {
    "persist_directory": str(PROJECT_ROOT / "backend" / "data" / "vector_db"),
    "collection_name": "arona_knowledge",
    "similarity_top_k": 3,
}

# 从 YAML 覆盖（如果存在）
if "vector_db" in _YAML_CONFIG:
    yaml_vdb = _YAML_CONFIG["vector_db"]
    # 处理相对路径：如果 persist_directory 是相对路径，则相对于 backend 目录
    if "persist_directory" in yaml_vdb:
        persist_path = yaml_vdb["persist_directory"]
        if not os.path.isabs(persist_path):
            persist_path = str(_BACKEND_DIR / persist_path)
        VECTOR_DB_CONFIG["persist_directory"] = persist_path
    VECTOR_DB_CONFIG["collection_name"] = yaml_vdb.get("collection_name", VECTOR_DB_CONFIG["collection_name"])
    VECTOR_DB_CONFIG["similarity_top_k"] = yaml_vdb.get("similarity_top_k", VECTOR_DB_CONFIG["similarity_top_k"])

# ========== 语义缓存配置 ==========
CACHE_CONFIG = {
    "cache_dir": str(PROJECT_ROOT / "backend" / "data" / "cache"),
    "similarity_threshold": 0.92,  # 语义相似度阈值，高于此值命中缓存（提高阈值减少误匹配）
    "max_similarity_threshold": 0.99,  # 动态阈值上限，避免短文本阈值超过余弦相似度上限
    "max_cache_size": 1000,        # 最大缓存条目数
    "ttl": 3600,                   # 缓存过期时间（秒）
}

# 从 YAML 覆盖（如果存在）
if "cache" in _YAML_CONFIG:
    yaml_cache = _YAML_CONFIG["cache"]
    # 处理相对路径：如果 cache_dir 是相对路径，则相对于 backend 目录
    if "cache_dir" in yaml_cache:
        cache_path = yaml_cache["cache_dir"]
        if not os.path.isabs(cache_path):
            cache_path = str(_BACKEND_DIR / cache_path)
        CACHE_CONFIG["cache_dir"] = cache_path
    CACHE_CONFIG["similarity_threshold"] = yaml_cache.get("similarity_threshold", CACHE_CONFIG["similarity_threshold"])
    CACHE_CONFIG["max_similarity_threshold"] = yaml_cache.get("max_similarity_threshold", CACHE_CONFIG["max_similarity_threshold"])
    CACHE_CONFIG["max_cache_size"] = yaml_cache.get("max_cache_size", CACHE_CONFIG["max_cache_size"])
    CACHE_CONFIG["ttl"] = yaml_cache.get("ttl", CACHE_CONFIG["ttl"])

# ========== 对话历史配置 ==========
CONVERSATION_CONFIG = {
    "max_history_turns": 10,       # 保留的最大对话轮次
    "max_history_tokens": 2048,    # 历史对话最大token数
    "session_ttl": 1800,           # 会话过期时间（秒）
}

# 从 YAML 覆盖（如果存在）
if "conversation" in _YAML_CONFIG:
    CONVERSATION_CONFIG.update(_YAML_CONFIG["conversation"])

# ========== 记忆配置 ==========
MEMORY_CONFIG = {
    "memory_collection": "arona_memory",
    "similarity_top_k": 5,
    "min_memory_length": 2,        # 最小记忆长度（字符数），降低以支持短记忆如名字
}

# 从 YAML 覆盖（如果存在）
if "memory" in _YAML_CONFIG:
    MEMORY_CONFIG.update(_YAML_CONFIG["memory"])

# ========== 链路压缩配置 ==========
COMPRESSOR_CONFIG = {
    "max_context_length": 4096,    # 压缩后的最大上下文长度
    "summary_ratio": 0.3,          # 摘要压缩比例
    "tfidf_score_weight": 3.0,      # TF-IDF相似度在句子打分中的权重
    "simple_query_context_ratio": 0.6,   # 简单问题使用更强压缩
    "medium_query_context_ratio": 0.8,   # 中等复杂度问题保留更多上下文
    "complex_query_context_ratio": 1.0,  # 复杂问题保留调用方允许的完整长度
    "use_bge_embedding": True,           # 是否启用BGE微模型替换TF-IDF辅助句子打分
    "bge_model_name": "BAAI/bge-small-zh-v1.5",  # BGE小中文嵌入模型
    "bge_device": "auto",                   # BGE模型运行设备（auto自动选CUDA/CPU）
    "bge_score_weight": 3.0,              # BGE相似度在句子打分中的权重
    "bge_model_path": "D:/Code/projects/Arona/arona-ai/models/bge-small-zh-v1.5"  # 本地BGE模型路径
}

# 从 YAML 覆盖（如果存在）
if "compressor" in _YAML_CONFIG:
    COMPRESSOR_CONFIG.update(_YAML_CONFIG["compressor"])

# ========== 知识库配置 ==========
KNOWLEDGE_CONFIG = {
    "chunk_size": 256,
    "chunk_overlap": 32,
    "knowledge_collection": "arona_knowledge",
}

# 从 YAML 覆盖（如果存在）
if "knowledge" in _YAML_CONFIG:
    KNOWLEDGE_CONFIG.update(_YAML_CONFIG["knowledge"])

# ========== 数据目录 ==========
DATA_DIR = str(PROJECT_ROOT / "backend" / "data")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(VECTOR_DB_CONFIG["persist_directory"], exist_ok=True)
os.makedirs(CACHE_CONFIG["cache_dir"], exist_ok=True)
