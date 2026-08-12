# AronaAI Backend

本地桌面陪伴后端：FastAPI WebSocket + AronaLM（llama-cpp）+ SQLite 记忆 + DeepSeek 异步抽取 + 向量知识 RAG。

对话默认走 **Planner（DeepSeek）→ 意图卡 → Renderer（AronaLM）**；Planner 关闭或失败时回落本地单模型路径。

## 模块详解

| 模块 | 路径 | 功能描述 |
|------|------|----------|
| **服务入口** | `app/main.py` | FastAPI 应用、健康检查、WebSocket 路由 |
| **对话编排** | `app/orchestrator.py` | 缓存 → 记忆/知识检索 → Planner 或本地 → Prompt → 生成 → 异步记忆抽取 |
| **Planner** | `app/planner/` | DeepSeek 意图卡、情感白名单、简单/复杂路由 |
| **模型加载** | `app/model_loader.py` | llama-cpp-python 加载 GGUF，支持流式与 `<think>` 过滤 |
| **WebSocket** | `app/ws_handler.py` | 会话连接、消息分发、ASR 过滤接入 |
| **输入过滤** | `app/input_filter.py` | 丢弃空串 / 腾讯云 ASR 错误模板，避免误触发对话 |
| **协议** | `app/protocol.py` | 客户端/服务端消息类型定义 |
| **对话历史** | `app/conversation.py` | 多轮历史管理与截断 |
| **知识 RAG** | `app/knowledge.py` | ChromaDB 检索世界观知识 |
| **嵌入** | `app/embeddings.py` | 本地 BGE 编码器（记忆 / 知识共用） |
| **记忆存储** | `app/memory/store.py` | SQLite + FTS5 + Chroma 混合长期记忆 |
| **记忆抽取** | `app/memory/extractor.py` | DeepSeek 异步抽取（失败走正则） |
| **响应缓存** | `app/cache.py` | 相同输入快速返回 |
| **Prompt** | `app/prompt.py` | 默认 Renderer 意图卡消息组装；本地回落路径 Prompt |

## 快速开始

创建并激活 conda 环境 `shittim-chest`：

```bash
conda activate shittim-chest
cd backend
pip install -r requirements.txt   # 若缺 fastapi/httpx/chromadb 等再装；无需重装 llama-cpp-python

# 复制配置并填写 DeepSeek API Key（可选；不填则记忆走正则降级）
copy config.example.yaml config.yaml

# 启动（工作目录必须是 backend/）
python -m app.main
# 或
uvicorn app.main:app --host 127.0.0.1 --port 20456
```

默认 WebSocket：`ws://127.0.0.1:20456/ws`（与 Qt 客户端一致）。

## 联调脚本

```bash
python scripts/smoke_ws.py
python scripts/test_input_filter.py   # ASR / 空串脏文本过滤断言
```

确保服务已启动后再跑 `smoke_ws.py`。脚本会发送 `ping` / `chat`，并打印响应。

## ASR 脏文本过滤

腾讯云 ASR 空结果曾被前端误当成识别成功，把  
`[Tencent Speech Recognizer]Didnt recognize vailable content!` 整段发进 `chat`，从而误触发 Planner。

**后端兜底**（[`app/input_filter.py`](app/input_filter.py) + [`app/ws_handler.py`](app/ws_handler.py)）：

- 空串、仅空白，或匹配腾讯云 ASR / SDK 错误模板的 `content` 在 WS 入口直接丢弃
- **不**调用 Orchestrator / Planner / 记忆抽取，**不**写入 session history
- 回一条轻量 `chat_response`：`刚才没听清，请再说一次～`，`emotion=curious`，`context_used=asr_filter`

**前端根因修复**（需重编客户端）：[`TencentSpeechRecognizer.cpp`](../frontend/AronaAI_Spine_WindowsClient/QtUtils/TencentSpeechRecognizer.cpp) 空结果改走 `errorOccurred`；[`MainController.cpp`](../frontend/AronaAI_Spine_WindowsClient/QtMainFile/MainController.cpp) 对同类脏串不再 `sendChatMessage`。

## 世界观知识 RAG

1. 按 [`data/knowledge/WRITING.md`](data/knowledge/WRITING.md) 在 `data/knowledge/corpus/` 编写 Markdown（`##` 切块）
2. 嵌入模型默认使用本地目录 `../models/bge-small-zh-v1.5`（配置项 `knowledge.embedding_model_path`）
3. 灌库：

```bash
python scripts/ingest_knowledge.py
# 大幅改标题/结构后建议：
python scripts/ingest_knowledge.py --rebuild
```

4. 冒烟检索：`python scripts/test_knowledge_rag.py`
5. 在 `config.yaml` 设 `knowledge.enabled: true` 后重启后端

## 配置

由 `config.example.yaml` 复制为 `config.yaml`（已 gitignore），主要段落：

| 配置段 | 说明 |
|--------|------|
| `server` | 监听地址、端口、WebSocket 路径（默认 `/ws`） |
| `model` | GGUF 路径（默认 Renderer v2.1）、上下文长度、采样参数、本地回落用 system prompt |
| `conversation` | 多轮历史保留轮数 |
| `knowledge` | 世界观 RAG（语料目录、Chroma、嵌入模型、检索阈值） |
| `memory` | SQLite + Chroma 路径、混合检索、DeepSeek 抽取器（`every_n_turns` / `extract_buffer_turns`）与正则降级 |
| `planner` | 默认开启的双模型 Planner（DeepSeek 意图卡、路由开关；无 Key / `enabled: false` 则回落本地） |
| `cache` | 响应缓存开关与容量 |
| `token_budget` | memory / knowledge / history 注入预算 |
| `logging` | 日志目录、文件名、级别与滚动策略 |

关键项速查：
- 模型：`model.gguf_path`（示例默认 AronaLM-Renderer-V2.1；回落见注释中的 AronaLM-Generator-V2.0）
- 模板：`config.example.yaml` → 本地：`config.yaml`

本地数据路径（均已 gitignore）：
- 记忆库：`data/memory/memory.db`
- 记忆向量索引：`data/memory/chroma/`
- 知识向量库：`data/knowledge/chroma/`（由 ingest 生成）
- 运行日志：`logs/arona-backend.log`

## 协议摘要

连接后服务端发送 `{"type":"connected","session_id":"..."}`。

客户端 `chat`：

```json
{"type":"chat","content":"你好","options":{"use_cache":true,"use_rag":true,"use_memory":true}}
```

正常回复：`{"type":"chat_response","content":"...","emotion":"...","from_cache":false,"context_used":"...","latency":...}`。

若 `content` 被判定为 ASR 脏文本，仍返回 `chat_response`，但 `context_used` 为 `"asr_filter"`，且不会进入双模型链路。
