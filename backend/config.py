"""
Arona AI 后端配置文件
"""
import os
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# ========== 模型配置 ==========
MODEL_CONFIG = {
    "base_model_name": "D:/Code/projects/Arona/arona-ai/models/hunyuan",
    "lora_path": "D:/Code/projects/Arona/arona-ai/models/aronalm/normal",
    "torch_dtype": "float16",
    "device_map": "auto",
    "max_new_tokens": 128,
    "temperature": 0.7,
    "top_p": 0.9,
    "top_k": 50,
    "repetition_penalty": 1.1,
    "max_length": 512,
}

# ========== 嵌入模型配置 ==========
EMBEDDING_CONFIG = {
    "use_external": True,  # True=使用外部sentence-transformers模型, False=使用本地TF-IDF+SVD
    "model_name": "paraphrase-multilingual-MiniLM-L12-v2",  # 支持中文的轻量级嵌入模型
    "device": "cpu",
}

# ========== 向量数据库配置 ==========
VECTOR_DB_CONFIG = {
    "persist_directory": str(PROJECT_ROOT / "backend" / "data" / "vector_db"),
    "collection_name": "arona_knowledge",
    "similarity_top_k": 3,
}

# ========== 语义缓存配置 ==========
CACHE_CONFIG = {
    "cache_dir": str(PROJECT_ROOT / "backend" / "data" / "cache"),
    "similarity_threshold": 0.92,  # 语义相似度阈值，高于此值命中缓存（提高阈值减少误匹配）
    "max_cache_size": 1000,        # 最大缓存条目数
    "ttl": 3600,                   # 缓存过期时间（秒）
}

# ========== 对话历史配置 ==========
CONVERSATION_CONFIG = {
    "max_history_turns": 10,       # 保留的最大对话轮次
    "max_history_tokens": 2048,    # 历史对话最大token数
    "session_ttl": 1800,           # 会话过期时间（秒）
}

# ========== 记忆配置 ==========
MEMORY_CONFIG = {
    "memory_collection": "arona_memory",
    "similarity_top_k": 5,
    "min_memory_length": 10,       # 最小记忆长度（字符数）
}

# ========== 链路压缩配置 ==========
COMPRESSOR_CONFIG = {
    "max_context_length": 4096,    # 压缩后的最大上下文长度
    "summary_ratio": 0.3,          # 摘要压缩比例
}

# ========== 知识库配置 ==========
KNOWLEDGE_CONFIG = {
    "chunk_size": 256,
    "chunk_overlap": 32,
    "knowledge_collection": "arona_knowledge",
}

# ========== 数据目录 ==========
DATA_DIR = str(PROJECT_ROOT / "backend" / "data")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(VECTOR_DB_CONFIG["persist_directory"], exist_ok=True)
os.makedirs(CACHE_CONFIG["cache_dir"], exist_ok=True)

