# AronaAI Backend

本地桌面陪伴后端：FastAPI WebSocket + AronaLM（llama-cpp）+ SQLite 记忆 + DeepSeek 异步抽取 + 向量知识 RAG。

对话默认走 **Planner（DeepSeek）→ 意图卡 → Renderer（AronaLM）**；Planner 关闭或失败时回落本地单模型路径。

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

- 模板：`config.example.yaml`
- 本地：`config.yaml`（已 gitignore）
- 模型：`model.gguf_path`（示例默认 AronaLM-Renderer-V2.1；回落见注释中的 AronaLM-Generator-V2.0）
- 记忆库：`data/memory/memory.db`（已 gitignore）；向量索引：`data/memory/chroma`
- 知识向量库：`data/knowledge/chroma/`（已 gitignore，由 ingest 生成）

## 协议摘要

连接后服务端发送 `{"type":"connected","session_id":"..."}`。

客户端 `chat`：

```json
{"type":"chat","content":"你好","stream":false,"options":{"use_cache":true,"use_rag":true,"use_memory":true}}
```

正常回复：`{"type":"chat_response","content":"...","emotion":"...","from_cache":false,"context_used":"...","latency":...}`。

若 `content` 被判定为 ASR 脏文本，仍返回 `chat_response`，但 `context_used` 为 `"asr_filter"`，且不会进入双模型链路。
