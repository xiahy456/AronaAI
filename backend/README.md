# AronaAI Backend

非交互式桌面AI 的本地后端：FastAPI WebSocket + AronaLM（llama-cpp）+ 关系气候决策 + SQLite 记忆 + DeepSeek 异步抽取 + 向量知识 RAG。

对话默认走 **关系决策 → Planner（DeepSeek）→ 意图卡 → Renderer（AronaLM）**；Planner 关闭或失败时回落本地单模型路径。决策层可以选择沉默，不调用 LLM。

## 模块详解

| 模块 | 路径 | 功能描述 |
|------|------|----------|
| **服务入口** | `app/main.py` | FastAPI 应用、健康检查、WebSocket 路由；启动时加载关系引擎 |
| **对话编排** | `app/orchestrator.py` | 分类/更新关系 → 决策 →（可选）检索 → Planner 或本地 → 生成 → 回写自身行动 → 异步记忆抽取 |
| **关系气候** | `app/relationship/` | 信任/依赖/张力状态、事件 Δ 表、规则分类、气候分区与行动策略、JSON 落盘 |
| **主动事件** | `app/proactive/` | 上线欢迎、空闲轻搭话、午饭/睡觉照料、goal 回访、节日问候、同轮补充；连接表 + 调度落盘 |
| **Planner** | `app/planner/` | DeepSeek 意图卡、情感白名单；只读气候档位与姿态，不见 A/B/C 数字 |
| **模型加载** | `app/model_loader.py` | llama-cpp-python 加载 GGUF，支持流式与 `<think>` 过滤 |
| **WebSocket** | `app/ws_handler.py` | 会话连接、上线欢迎、消息分发、ASR 过滤接入 |
| **输入过滤** | `app/input_filter.py` | 丢弃空串 / 腾讯云 ASR 错误模板，避免误触发对话 |
| **协议** | `app/protocol.py` | 客户端/服务端消息类型定义 |
| **对话历史** | `app/conversation.py` | 多轮历史管理与截断 |
| **知识 RAG** | `app/knowledge.py` | ChromaDB 检索世界观知识 |
| **嵌入** | `app/embeddings.py` | 本地 BGE 编码器（记忆 / 知识共用） |
| **记忆存储** | `app/memory/store.py` | SQLite + FTS5 + Chroma 混合长期记忆 |
| **记忆抽取** | `app/memory/extractor.py` | DeepSeek 异步抽取（失败走正则） |
| **Prompt** | `app/prompt.py`、`app/planner/prompts.py` | Renderer / 本地回落消息组装；Planner system + user 模板。部件清单见下节 |

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
python scripts/test_input_filter.py        # ASR / 空串脏文本过滤断言
python scripts/test_relationship_unit.py   # 关系公式 / 分区 / 分类 / 沉默（不加载 GGUF）
python scripts/test_welcome_unit.py        # 欢迎时段与指令（不加载 GGUF）
python scripts/test_proactive_unit.py      # 空闲 / 照料 / goal / 节日 / continue / 调度落盘（不加载 GGUF）
```

确保服务已启动后再跑 `smoke_ws.py`。脚本会发送 `ping` / `chat`，并打印响应。

## 对话链路

每条用户 `chat` 先过关系层，再决定是否生成：

```text
用户文本
  → 规则分类 user_act
  → 查表 Δ 更新信任 / 依赖 / 张力
  → 气候分区 + 姿态（action / stance / must_not）
  → silence / refuse：写入历史，不调用 LLM，不发 chat_response
  → speak：记忆/知识检索 → Planner 或本地 → Renderer → chat_response
  → 回写阿洛娜自身行动（followed_up / gave_space / teased / greeted）
```

Planner 只看见【关系气候】档位与【建议姿态】，禁止下发 A/B/C 浮点或「提升信任度」。缓存命中也会先分类、后回写，避免绕过关系层。

`action` 目前实际用到的是 `speak`（开口）、`silence`（沉默）、`initiate`（欢迎 / 空闲 / 照料 / goal 回访 / 节日）与 `continue`（同轮补一句）。欢迎与节日回写 `greeted`，空闲与 goal 回写 `checked_in`，照料回写 `cared`（均不抬依赖）；同轮补充回写 `followed_up`。

## Prompt 部件

双模型路径最终拼出两条 prompt：Planner（DeepSeek）与 Renderer（AronaLM）。组装入口：

| 最终产物 | 组装函数 | 文件 |
|----------|----------|------|
| Planner prompt | `PlannerClient.plan()` | [`app/planner/client.py`](app/planner/client.py) |
| Renderer prompt | `build_renderer_messages()` | [`app/prompt.py`](app/prompt.py) |

调用方是 [`app/orchestrator.py`](app/orchestrator.py)：客户端用户输入走 `handle_chat()`；后端系统消息走 `handle_initiate()` / `handle_welcome()` / `_maybe_continue()`。Planner 关闭或失败时走 `build_messages()`（本地单模型），不拼 Renderer prompt。

```text
用户 chat / 系统 instruction
        │
        ├─【关系气候】policy.py 或 orchestrator._welcome_climate_block
        ├─ 记忆 / 知识 / 历史（运行时检索，非独立 prompt 文件）
        └─ 本轮文本：用户原话 或 6 套 build_*_instruction
                │
                ▼
     Planner prompt  (planner/prompts.py + client.py)
                │  JSON draft
                ▼
     Renderer prompt (prompt.py + renderer_*_v24.txt)
```

### Planner prompt

结构固定为两条 message：`system = PLANNER_SYSTEM`，`user = climate + 记忆 + 知识 + 历史 +「老师本轮消息」+ 收尾句`。

| 部件 | 位置 |
|------|------|
| `PLANNER_SYSTEM`（人设、边界、JSON schema） | [`app/planner/prompts.py`](app/planner/prompts.py) |
| `{EMOTION_WHITELIST_CSV}` 插值 | [`app/planner/emotions.py`](app/planner/emotions.py) |
| user 模板 `build_planner_user_message()` | [`app/planner/prompts.py`](app/planner/prompts.py) |

`FIXED_MUST_NOT` 仍在 `prompts.py`，V2.4 **不再注入**。

`build_planner_user_message()` 按顺序拼：可选 `climate_block` → `【长期记忆】` → `【相关知识】` → `【近期对话】` → `【老师本轮消息】` → 收尾「若有【关系气候】，按建议姿态写草稿」。

**`【老师本轮消息】` 按来源分套：**

| 场景 | 构建函数 | 文件 |
|------|----------|------|
| 客户端用户输入 | 原样写入，无额外 instruction | `Orchestrator.handle_chat()` |
| 上线欢迎 | `build_welcome_instruction()` | [`app/proactive/welcome.py`](app/proactive/welcome.py) |
| 空闲搭话 | `build_idle_instruction()` | [`app/proactive/idle.py`](app/proactive/idle.py) |
| 午饭 / 睡觉提醒 | `build_care_instruction()` + `_CARE_INTENTS` | [`app/proactive/care.py`](app/proactive/care.py) |
| 节日 / 生日 | `build_festival_instruction()` | [`app/proactive/festival.py`](app/proactive/festival.py) |
| goal 回访 | `build_goal_instruction()` | [`app/proactive/goal.py`](app/proactive/goal.py) |
| 同轮补充 | `build_continue_instruction()` | [`app/proactive/followup.py`](app/proactive/followup.py) |

欢迎时段文案还会用到 [`app/proactive/slots.py`](app/proactive/slots.py) 的 `SLOT_LABELS`。调度入口：[`app/proactive/scheduler.py`](app/proactive/scheduler.py)（idle / care / goal / festival）、[`app/proactive/loop.py`](app/proactive/loop.py)（festival / sleep 补发）。

**`【关系气候】` 块：**

| 场景 | 函数 | 文件 |
|------|------|------|
| 普通对话 / 主动事件（有 Decision） | `planner_climate_block()` | [`app/relationship/policy.py`](app/relationship/policy.py) |
| 欢迎（peek climate，无完整 Decision） | `_welcome_climate_block()` | [`app/orchestrator.py`](app/orchestrator.py) |

`planner_climate_block` 的文案来自同文件：`CLIMATE_LABELS`（气候中文名）、`_POLICY`（对话姿态 / 禁区 / 语气）、`decide_proactive()`（idle / care / festival / goal 另一套姿态与禁区）。

### Renderer prompt

结构也是两条 message，**不拼接 yaml 人设、不带历史**：`system = RENDERER_SYSTEM`，`user = 【意图草稿】 + draft + RENDERER_USER_TAIL`。

| 部件 | 加载 / 组装 | 源 |
|------|-------------|----|
| `RENDERER_SYSTEM` | [`app/prompt.py`](app/prompt.py) 常量 | 代码内编码 |
| `RENDERER_USER_TAIL` | [`app/prompt.py`](app/prompt.py) 常量 | 代码内编码 |
| user 包装 `format_renderer_user()` | [`app/prompt.py`](app/prompt.py) | `【意图草稿】` + tail |
| draft 内容 | `IntentCard.to_renderer_draft()` | [`app/planner/schema.py`](app/planner/schema.py) |

后端不读取 `llm/aronaLM/finetune/prompts/`；该目录只给微调数据管线使用。

### 本地回落（非 dual）

`build_messages()`（[`app/prompt.py`](app/prompt.py)）：

| 部件 | 位置 |
|------|------|
| 本地人设 | `config.yaml` 的 `prompt.local_system_prompt`（模板见 [`config.example.yaml`](config.example.yaml)） |
| 关系 hint | `local_system_hint()` → [`app/relationship/policy.py`](app/relationship/policy.py) |
| 记忆 / 知识 / 历史 / user_text | 运行时拼进 system / user |

`handle_initiate` 在 planner 失败时，系统 instruction 会直接当 `user_text` 送给本地模型。

### 不进这条链路

- 记忆抽取：`EXTRACT_SYSTEM` 在 [`app/memory/extractor.py`](app/memory/extractor.py)（另一路 DeepSeek）

改话术时：用户对话改 `PLANNER_SYSTEM`；欢迎/空闲/照料等改对应 `build_*_instruction`；关系口吻改 `policy.py`；阿洛娜最终台词风格改 `app/prompt.py` 的 `RENDERER_SYSTEM`。

## 关系气候

三个慢变量，值域 `[-1, 1]`，默认 baseline 约 `(信任 0.55, 依赖 0.30, 张力 0.25)`：

| 维度 | 含义 |
|------|------|
| 信任 A | 防备 ↔ 安心托付 |
| 依赖 B | 当工具 ↔ 过度黏着 |
| 张力 C | 死气 ↔ 对立/过激 |

更新公式（惯性 + 微弱回归 + 日封顶；张力高时正向信任修正放大）：

```text
new = clamp(old + α * Δ - β * (old - baseline), -1, 1)
```

Δ 由事件表给出，不让 LLM 发明浮点。用户侧事件包括 `fatigue` / `seek_validation` / `self_disclose` / `play_tease` / `reject` / `gratitude` / `affection` / `worry_bond` / `depart` / `instrumental` / `short_ack` / `other`。未识别为 `other`（Δ 为 0）。

气候分区（连续若干轮保持同一姿态，紧急档可立即切换）：

| 气候 | 条件（概要） | 姿态 |
|------|--------------|------|
| `secure_play` | A 高、B 中、C 中 | 可轻松、可轻玩笑 |
| `cling_risk` | B 高、C 低 | 短回应；短「嗯」或疲惫可沉默 |
| `rupture` | C 高、A 尚可 | 先认情绪，不讲理 |
| `cold_tool` | A/B/C 都低 | 先可靠办事，不硬亲密 |
| `fragile` | A 低且 C 高 | 只稳住，不玩笑 |
| `steady` | 其余 | 平稳接住本轮 |

沉默规则（当前实现）：

- `cling_risk` 且用户是 `short_ack` / `fatigue`
- 上一轮是 `depart`（失陪、先去忙），本轮是短「嗯」

状态落 `data/memory/relationship.json`，重启不重置。关闭：`proactive.relationship.enabled: false`。

## 上线欢迎

WebSocket 连接并发送 `connected` 后，若 `proactive.welcome.enabled` 为真，后端占用当前 `chat_task` 主动生成一句问候（普通 `chat_response`）。欢迎不检索记忆。

时段（本地时）：

| 时段 | 区间 | 同槽首次 |
|------|------|----------|
| 凌晨 | `[0:00, 5:00)` | 提醒休息，不说「早上好」 |
| 早上 | `[5:00, 9:00)` | 早上好 |
| 上午 | `[9:00, 12:00)` | 上午好 |
| 中午 | `[12:00, 14:00)` | 中午好，可提醒吃饭 |
| 下午 | `[14:00, 18:00)` | 下午好 |
| 晚上 | `[18:00, 23:00)` | 晚上好 |
| 深夜 | `[23:00, 24:00)` | 提醒休息 |

同一时段再次上线改为「老师好 / 欢迎回来」，不再重复时段问候。时段状态在内存中，进程重启后会再问候一次。失败不标记时段。历史写入短标记 `【上线】`，不把系统指令写进对话。欢迎允许一句轻问开场，但禁止「想聊什么」这类抛回。

节日当天**第一次上线**会把欢迎换成节日祝福（见下），同日再连仍走普通欢迎。

## 空闲搭话、时刻照料与节日

进程级 tick（约 30 秒）查看已连接且未在生成中的会话，每 tick 最多选 1 条动机（节日 > 照料 > goal 回访 > 空闲），先过 `decide_proactive` 再生成。推普通 `chat_response`。忙时跳过，不排队。

| 触发 | 默认 | 要点 |
|------|------|------|
| 节日问候 | 公历节假日 / 农历年表 / 老师生日 | 当天第一次上线欢迎直接换成祝福，整天只说一次；凌晨/深夜先祝福再跟一句休息提醒；tick 仅在欢迎没说过时兜底；`depart` 时 tick 不说、欢迎仍可换；历史 `【节日】`；回写 `greeted` |
| 空闲轻搭话 | 老师安静 15 分钟；两次搭话间隔默认 30 分钟；每天最多 3 次 | 欢迎/照料之后只需再等 `after_sec`，不占用搭话冷却；深夜/凌晨不闲聊；上一轮是 `depart` 不闲聊；仅 `secure_play` / `steady` 可开口；历史 `【搭话】`；不检索记忆 |
| goal 回访 | 老师安静 5 分钟后；每条 goal 冷却 6 小时；每天最多 1 次 | 扫记忆 `category=goal`，轻轻提起最久未回访的一条；不催、不盘问、不编造进展；老师说「先别提」等则 mute 上一条 7 天；休息时段 / `depart` 不回访；气候闸与空闲相同；历史 `【回访】`；直接注入该条记忆 |
| 午饭照料 | 12:00–12:30，每天一次 | 短提醒吃饭，不催；`cling_risk` 更短；可检索作息记忆 |
| 睡觉照料 | 23:00–23:20，每天一次 | 提醒休息；允许在休息时段触发；历史 `【提醒】` |
| 同轮补充 | Planner `followup_ok`（按「能否扩展」） | 仅用户 chat 双模型路径、首句成功后最多再扩 1 句；本地回落 / 缓存 / 欢迎 / idle / care / goal / festival 不续说；历史 `【补充】` |

调度状态落 `data/memory/proactive.json`（含 `festival_done`）。跨日清当日节日标记。节日成功才标记；失败可下次再试。关闭：`proactive.idle.enabled` / `proactive.care.enabled` / `proactive.goal.enabled` / `proactive.continue.enabled` / `proactive.festival.enabled`。

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
| `model` | GGUF 路径（默认 Renderer v2.4）、上下文长度、采样参数、本地回落用 system prompt |
| `conversation` | 多轮历史保留轮数 |
| `knowledge` | 世界观 RAG（语料目录、Chroma、嵌入模型、检索阈值） |
| `memory` | SQLite + Chroma 路径、混合检索、DeepSeek 抽取器（`every_n_turns` / `extract_buffer_turns`）与正则降级 |
| `planner` | 默认开启的双模型 Planner（DeepSeek 意图卡；无 Key / `enabled: false` 则回落本地） |
| `proactive` | 上线欢迎；关系气候；空闲搭话；照料窗口；goal 回访；节日问候；同轮 `continue` |
| `token_budget` | memory / knowledge / history 注入预算 |
| `logging` | 日志目录、文件名、级别与滚动策略 |

关键项速查：
- 模型：`model.gguf_path`（示例默认 AronaLM-Renderer-V2.4；回落见注释中的 AronaLM-Generator-V2.0）
- 模板：`config.example.yaml` → 本地：`config.yaml`

本地数据路径（均已 gitignore）：
- 记忆库：`data/memory/memory.db`
- 记忆向量索引：`data/memory/chroma/`
- 关系气候：`data/memory/relationship.json`
- 主动调度：`data/memory/proactive.json`
- 知识向量库：`data/knowledge/chroma/`（由 ingest 生成）
- 运行日志：`logs/arona-backend.log`

## 协议摘要

连接后服务端发送 `{"type":"connected","session_id":"..."}`。

客户端 `chat`：

```json
{"type":"chat","content":"你好","options":{"use_rag":true,"use_memory":true}}
```

正常回复：`{"type":"chat_response","content":"...","emotion":"...","from_cache":false,"context_used":"...","latency":...}`。

连接后若欢迎开启，服务端会再推一条 `chat_response`（`context_used` 含 `welcome`，节日当天首次则为 `festival`；凌晨/深夜节日可能再跟一条 `sleep`）。空闲搭话 / 照料 / goal 回访同样推 `chat_response`（`context_used` 含 `idle` / `lunch` / `sleep` / `goal`）。Planner 标 `followup_ok` 时，同一轮用户消息后可能再跟一条 `chat_response`（`context_used` 含 `continue`）。关系层决定沉默时**不**发 `chat_response`，前端保持安静。

若 `content` 被判定为 ASR 脏文本，仍返回 `chat_response`，但 `context_used` 为 `"asr_filter"`，且不会进入双模型链路。
