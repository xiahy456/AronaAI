# AronaAI Backend

本地桌面陪伴后端：FastAPI WebSocket + AronaLM（llama-cpp）+ SQLite 记忆 + DeepSeek 异步抽取。

## 快速开始

推荐使用已有 conda 环境 `arona`（已含 `llama-cpp-python`）：

```bash
conda activate arona
cd backend
pip install -r requirements.txt   # 若缺 fastapi/httpx 等再装；无需重装 llama-cpp-python

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
```

确保服务已启动。脚本会发送 `ping` / `chat`，并打印响应。

## 配置

- 模板：`config.example.yaml`
- 本地：`config.yaml`（已 gitignore）
- 记忆库：`data/memory.db`（已 gitignore）

## 协议摘要

连接后服务端发送 `{"type":"connected","session_id":"..."}`。

客户端 `chat`：

```json
{"type":"chat","content":"你好","stream":false,"options":{"use_cache":true,"use_rag":true,"use_memory":true}}
```
