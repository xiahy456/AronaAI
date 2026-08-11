# 模型 / Models

本目录存放 AronaAI 运行所需的**本地模型权重**（已在 `.gitignore` 中忽略，需自行下载放置）。

This directory holds local model weights used by AronaAI (gitignored — download and place them yourself).

---

## 目录结构 / Layout

```
models/
├── aronalm-v2.0-normal/              # 后端推理：AronaLM GGUF（必需）
│   └── aronalm-v2.0-normal.Q4_K_M.gguf
└── bge-small-zh-v1.5/                # 知识 RAG 嵌入模型（启用 knowledge 时需要）
```

> TTS 权重放在 `gpt-sovits/GPT_weights_v2/`、`gpt-sovits/SoVITS_weights_v2/`，只要客户端 / API 配置中的路径能正确解析即可。

---

## 后端推理（必需） / Backend Inference (Required)

| 模型 | 路径 | 用途 | 配置项 |
|------|------|------|--------|
| **AronaLM v2.0** | `aronalm-v2.0-normal/aronalm-v2.0-normal.Q4_K_M.gguf` | 对话生成（`llama-cpp-python` 加载 Q4_K_M GGUF） | `backend/config.yaml` → `model.gguf_path` |

- 下载：[xiahy456/aronalm-v2.0-normal](https://www.modelscope.cn/models/xiahy456/aronalm-v2.0-normal)（ModelScope）
- 默认配置路径：`../models/aronalm-v2.0-normal/aronalm-v2.0-normal.Q4_K_M.gguf`（相对 `backend/`）

---

## 知识 RAG（按需） / Knowledge RAG (Optional)

| 模型 | 路径 | 用途 | 配置项 |
|------|------|------|--------|
| **BGE-small-zh-v1.5** | `bge-small-zh-v1.5/` | 世界观知识语料向量化与检索（ChromaDB） | `knowledge.embedding_model_path` |

- 启用前：在 `config.yaml` 中设 `knowledge.enabled: true`，并先执行 `backend/scripts/ingest_knowledge.py` 灌库
- 默认路径：`../models/bge-small-zh-v1.5`（相对 `backend/`）
- 可从 Hugging Face / ModelScope 搜索 `BAAI/bge-small-zh-v1.5` 下载完整目录到此处

---

## 非本地模型 / External (Cloud) Models

以下不放入本目录，通过 API Key 配置：

| 服务 | 用途 | 配置位置 |
|------|------|----------|
| **DeepSeek** | 长期记忆异步抽取（无 Key 时降级为正则） | `backend/config.yaml` → `memory.extractor` |
| **腾讯云 ASR** | 桌面端语音识别 | 客户端 `config.json` → `tencent_speech_recognizer` |

---

## 最小可运行集合 / Minimum to Run Backend

只跑后端对话时，至少需要：

```
models/aronalm-v2.0-normal/aronalm-v2.0-normal.Q4_K_M.gguf
```

启用知识库时再补上 `bge-small-zh-v1.5/`；启用语音时再配置 GPT-SoVITS 权重与参考音频。
