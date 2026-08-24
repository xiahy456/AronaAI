# AronaAI Backend

非交互式桌面AI 的本地后端：FastAPI WebSocket + AronaLM（llama-cpp）+ 关系气候决策 + SQLite 记忆 + DeepSeek 异步抽取 + 向量知识 RAG。

对话默认走 **关系决策 → Planner（DeepSeek）→ 意图卡 → Renderer（AronaLM）**；Planner 关闭或失败时回落本地单模型路径。决策层可以选择沉默，不调用 LLM。

## 模块详解


| 模块            | 路径                                       | 功能描述                                                      |
| ------------- | ---------------------------------------- | --------------------------------------------------------- |
| **服务入口**      | `app/main.py`                            | FastAPI 应用、健康检查、WebSocket 路由；启动时加载关系引擎                    |
| **对话编排**      | `app/orchestrator.py`                    | 分类/更新关系 → 决策 →（可选）检索 → Planner 或本地 → 生成 → 回写自身行动 → 异步记忆抽取 |
| **关系气候**      | `app/relationship/`                      | 信任/依赖/张力状态、事件 Δ 表、规则分类、气候分区与行动策略、JSON 落盘                  |
| **主动事件**      | `app/proactive/`                         | 上线欢迎、空闲轻搭话、午饭/睡觉照料、goal 回访、节日问候、同轮补充；连接表 + 调度落盘           |
| **Planner**   | `app/planner/`                           | DeepSeek 意图卡、情感白名单；只读气候档位与姿态，不见 A/B/C 数字                  |
| **模型加载**      | `app/model_loader.py`                    | llama-cpp-python 加载 GGUF；启动时用 Renderer prompt 预热并复用前缀 KV  |
| **WebSocket** | `app/ws_handler.py`                      | 会话连接、上线欢迎、消息分发、ASR 过滤接入                                   |
| **输入过滤**      | `app/input_filter.py`                    | 丢弃空串 / 腾讯云 ASR 错误模板，避免误触发对话                               |
| **协议**        | `app/protocol.py`                        | 客户端/服务端消息类型定义                                             |
| **对话历史**      | `app/conversation.py`                    | 多轮历史管理与截断                                                 |
| **知识 RAG**    | `app/knowledge.py`                       | ChromaDB 检索世界观知识                                          |
| **嵌入**        | `app/embeddings.py`                      | 本地 BGE 编码器（记忆 / 知识共用）                                     |
| **记忆存储**      | `app/memory/store.py`                    | SQLite + FTS5 + Chroma 混合长期记忆                             |
| **记忆抽取**      | `app/memory/extractor.py`                | DeepSeek 异步抽取（失败走正则）                                      |
| **Prompt**    | `app/prompt.py`、`app/planner/prompts.py` | Renderer / 本地回落消息组装；Planner system + user 模板。部件清单见下节      |




## 快速开始

Windows 便携包：从 [Releases](https://github.com/xiahy456/AronaAI/releases) 下载 `AronaAI_Backend_v*_x64.zip`，解压后按包内 `README.txt` 配置即可，无需 conda。维护者打包见下文「便携发布包」。

从源码启动时，创建并激活 conda 环境 `shittim-chest`：

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

## 便携发布包（Windows x64）

给 GitHub Release 打的是解压即用的目录，**不是** PyInstaller 单文件。相对路径仍相对包根解析（`ARONA_BACKEND_DIR` 可覆盖）。

维护者在一台已能跑后端的 Windows 机器上：

```powershell
# 1) 最小运行时 conda 环境（CPU torch + CUDA llama-cpp；不要用含 Unsloth 的训练环境）
.\setup-backend-pack-env.ps1

# 2) 打目录 + zip（可选带上本机 BGE，并预灌知识库）
.\pack-backend.ps1
.\pack-backend.ps1 -IncludeBge -IngestKnowledge
```

产物：

- 目录：`backend/dist/AronaAI_Backend/`（已 gitignore）
- zip：`release/AronaAI_Backend_v<version>_x64.zip`

zip **不含** GGUF、**不含** 本机 `config.yaml` 里的真实 Key。用户解压后编辑包内 `config.yaml`，按 `models/README.txt` 放置 BGE / Renderer。启动：`AronaAI_Backend.bat`。

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

```
后端
├── planner可用
|   ├── 本地 AronaLM-Renderer-V2.x 模型可用
│   │   └── 使用双模型链路 Planner（DeepSeek）→ Renderer（AronaLM-Renderer-V2.x）
│   └── 本地 AronaLM-Renderer-V2.x 模型不可用
│       └── 使用 Planner 直接生成回复（默认）
└── planner不可用
    └── 使用本地单模型 AronaLM-Generator-V2.x 或 AronaLM-Renderer-V2.x，若无则无法回复
```

每条用户 `chat` 先过关系层，再决定是否生成：

```text
用户文本
  → 规则分类 user_act
  → 查表 Δ 更新信任 / 依赖 / 张力
  → 气候分区 + 姿态（action / stance / must_not）
  → silence / refuse：写入历史，不调用 LLM，不发 chat_response
  → speak：本轮 query embedding 只算一次 → 记忆/知识检索（知识近义命中可复用）
       → Planner 或本地 → Renderer（复用 system 前缀 KV）→ chat_response
  → 回写阿洛娜自身行动（followed_up / gave_space / teased / greeted）
```

Planner 只看见【关系气候】档位与【建议姿态】，禁止下发 A/B/C 浮点或「提升信任度」。

`action` 目前实际用到的是 `speak`（开口）、`silence`（沉默）、`initiate`（欢迎 / 空闲 / 照料 / goal 回访 / 节日）与 `continue`（同轮补一句）。欢迎与节日回写 `greeted`，空闲与 goal 回写 `checked_in`，照料回写 `cared`（均不抬依赖）；同轮补充回写 `followed_up`。

## Prompt 部件

双模型路径最终拼出两条 prompt：Planner（DeepSeek）与 Renderer（AronaLM）。组装入口：


| 最终产物            | 组装函数                        | 文件                                               |
| --------------- | --------------------------- | ------------------------------------------------ |
| Planner prompt  | `PlannerClient.plan()`      | `[app/planner/client.py](app/planner/client.py)` |
| Renderer prompt | `build_renderer_messages()` | `[app/prompt.py](app/prompt.py)`                 |


调用方是 `[app/orchestrator.py](app/orchestrator.py)`：客户端用户输入走 `handle_chat()`；后端系统消息走 `handle_initiate()` / `handle_welcome()` / `_maybe_continue()`。Planner 关闭或失败时走 `build_messages()`（本地单模型），不拼 Renderer prompt。

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

结构固定为两条 message：`system = PLANNER_SYSTEM`，`user = climate +【当前时间】+ 记忆 + 知识 + 历史 +「老师本轮消息」+ 收尾句`。


| 部件                                     | 位置                                                   |
| -------------------------------------- | ---------------------------------------------------- |
| `PLANNER_SYSTEM`（人设、边界、JSON schema）    | `[app/planner/prompts.py](app/planner/prompts.py)`   |
| `{EMOTION_WHITELIST_CSV}` 插值           | `[app/planner/emotions.py](app/planner/emotions.py)` |
| user 模板 `build_planner_user_message()` | `[app/planner/prompts.py](app/planner/prompts.py)`   |


`FIXED_MUST_NOT` 仍在 `prompts.py`，V2.4 **不再注入**。

`build_planner_user_message()` 按顺序拼：可选 `climate_block` → `【当前时间】`（与记忆抽取同一格式，如 `2026年8月24日 星期一 10:14`）→ `【长期记忆】` → `【相关知识】` → `【近期对话】` → `【老师本轮消息】` → 收尾「若有【关系气候】，按建议姿态写草稿」。写入 Planner 的记忆按 key 冷却，默认 1 小时内不重复注入（`memory.inject_cooldown_sec`）；抽取侧检索不受影响。

`【老师本轮消息】` **按来源分套：**


| 场景        | 构建函数                                         | 文件                                                       |
| --------- | -------------------------------------------- | -------------------------------------------------------- |
| 客户端用户输入   | 原样写入，无额外 instruction                         | `Orchestrator.handle_chat()`                             |
| 上线欢迎      | `build_welcome_instruction()`                | `[app/proactive/welcome.py](app/proactive/welcome.py)`   |
| 空闲搭话      | `build_idle_instruction()`                   | `[app/proactive/idle.py](app/proactive/idle.py)`         |
| 午饭 / 睡觉提醒 | `build_care_instruction()` + `_CARE_INTENTS` | `[app/proactive/care.py](app/proactive/care.py)`         |
| 节日 / 生日   | `build_festival_instruction()`               | `[app/proactive/festival.py](app/proactive/festival.py)` |
| goal 回访   | `build_goal_instruction()`                   | `[app/proactive/goal.py](app/proactive/goal.py)`         |
| 同轮补充      | `build_continue_instruction()`               | `[app/proactive/followup.py](app/proactive/followup.py)` |


欢迎时段文案还会用到 `[app/proactive/slots.py](app/proactive/slots.py)` 的 `SLOT_LABELS`。调度入口：`[app/proactive/scheduler.py](app/proactive/scheduler.py)`（idle / care / goal / festival）、`[app/proactive/loop.py](app/proactive/loop.py)`（festival / sleep 补发）。

`【关系气候】` **块：**


| 场景                            | 函数                         | 文件                                                         |
| ----------------------------- | -------------------------- | ---------------------------------------------------------- |
| 普通对话 / 主动事件（有 Decision）       | `planner_climate_block()`  | `[app/relationship/policy.py](app/relationship/policy.py)` |
| 欢迎（peek climate，无完整 Decision） | `_welcome_climate_block()` | `[app/orchestrator.py](app/orchestrator.py)`               |


`planner_climate_block` 的文案来自同文件：`CLIMATE_LABELS`（气候中文名）、`_POLICY`（对话姿态 / 禁区 / 语气）、`decide_proactive()`（idle / care / festival / goal 另一套姿态与禁区）。

### Renderer prompt

结构也是两条 message，**不拼接 yaml 人设、不带历史**：`system = RENDERER_SYSTEM`，`user = 【意图草稿】 + draft + RENDERER_USER_TAIL`。


| 部件                               | 加载 / 组装                             | 源                                                |
| -------------------------------- | ----------------------------------- | ------------------------------------------------ |
| `RENDERER_SYSTEM`                | `[app/prompt.py](app/prompt.py)` 常量 | 代码内编码                                            |
| `RENDERER_USER_TAIL`             | `[app/prompt.py](app/prompt.py)` 常量 | 代码内编码                                            |
| user 包装 `format_renderer_user()` | `[app/prompt.py](app/prompt.py)`    | `【意图草稿】` + tail                                  |
| draft 内容                         | `IntentCard.to_renderer_draft()`    | `[app/planner/schema.py](app/planner/schema.py)` |


后端不读取 `llm/aronaLM/finetune/prompts/`；该目录只给微调数据管线使用。

### 本地回落（非 dual）

`build_messages()`（`[app/prompt.py](app/prompt.py)`）：


| 部件                       | 位置                                                                                             |
| ------------------------ | ---------------------------------------------------------------------------------------------- |
| 本地人设                     | `config.yaml` 的 `prompt.local_system_prompt`（模板见 `[config.example.yaml](config.example.yaml)`） |
| 关系 hint                  | `local_system_hint()` → `[app/relationship/policy.py](app/relationship/policy.py)`             |
| 记忆 / 知识 / 历史 / user_text | 运行时拼进 system / user                                                                            |


`handle_initiate` 在 planner 失败时，系统 instruction 会直接当 `user_text` 送给本地模型。

### 不进这条链路

- 记忆抽取：`EXTRACT_SYSTEM` 在 `[app/memory/extractor.py](app/memory/extractor.py)`（另一路 DeepSeek）

改话术时：用户对话改 `PLANNER_SYSTEM`；欢迎/空闲/照料等改对应 `build_*_instruction`；关系口吻改 `policy.py`；阿洛娜最终台词风格改 `app/prompt.py` 的 `RENDERER_SYSTEM`。

## 关系气候

三个慢变量，值域 `[-1, 1]`，默认 baseline 约 `(信任 0.55, 依赖 0.30, 张力 0.25)`：


| 维度   | 含义         |
| ---- | ---------- |
| 信任 A | 防备 ↔ 安心托付  |
| 依赖 B | 当工具 ↔ 过度黏着 |
| 张力 C | 死气 ↔ 对立/过激 |


更新公式（惯性 + 微弱回归 + 日封顶；张力高时正向信任修正放大）：

```text
new = clamp(old + α * Δ - β * (old - baseline), -1, 1)
```

Δ 由事件表给出，不让 LLM 发明浮点。用户侧事件包括 `fatigue` / `seek_validation` / `self_disclose` / `play_tease` / `reject` / `gratitude` / `affection` / `worry_bond` / `depart` / `instrumental` / `short_ack` / `other`。未识别为 `other`（Δ 为 0）。

气候分区（连续若干轮保持同一姿态，紧急档可立即切换）：


| 气候            | 条件（概要）      | 姿态             |
| ------------- | ----------- | -------------- |
| `secure_play` | A 高、B 中、C 中 | 可轻松、可轻玩笑       |
| `cling_risk`  | B 高、C 低     | 短回应；短「嗯」或疲惫可沉默 |
| `rupture`     | C 高、A 尚可    | 先认情绪，不讲理       |
| `cold_tool`   | A/B/C 都低    | 先可靠办事，不硬亲密     |
| `fragile`     | A 低且 C 高    | 只稳住，不玩笑        |
| `steady`      | 其余          | 平稳接住本轮         |


沉默规则（当前实现）：

- `cling_risk` 且用户是 `short_ack` / `fatigue`
- 上一轮是 `depart`（失陪、先去忙），本轮是短「嗯」

状态落 `data/memory/relationship.json`，重启不重置。关闭：`proactive.relationship.enabled: false`。

## 上线欢迎

WebSocket 连接并发送 `connected` 后，若 `proactive.welcome.enabled` 为真，后端占用当前 `chat_task` 主动生成一句问候（普通 `chat_response`）。欢迎不检索记忆。

时段（本地时）：


| 时段  | 区间               | 同槽首次         |
| --- | ---------------- | ------------ |
| 凌晨  | `[0:00, 5:00)`   | 提醒休息，不说「早上好」 |
| 早上  | `[5:00, 9:00)`   | 早上好          |
| 上午  | `[9:00, 12:00)`  | 上午好          |
| 中午  | `[12:00, 14:00)` | 中午好，可提醒吃饭    |
| 下午  | `[14:00, 18:00)` | 下午好          |
| 晚上  | `[18:00, 23:00)` | 晚上好          |
| 深夜  | `[23:00, 24:00)` | 提醒休息         |


同一时段再次上线改为「老师好 / 欢迎回来」，不再重复时段问候。时段状态在内存中，进程重启后会再问候一次。失败不标记时段。历史写入短标记 `【上线】`，不把系统指令写进对话。欢迎允许一句轻问开场，但禁止「想聊什么」这类抛回。

节日当天**第一次上线**会把欢迎换成节日祝福（见下），同日再连仍走普通欢迎。

## 空闲搭话、时刻照料与节日

进程级 tick（约 30 秒）查看已连接且未在生成中的会话，每 tick 最多选 1 条动机（节日 > 照料 > goal 回访 > 空闲），先过 `decide_proactive` 再生成。推普通 `chat_response`。忙时跳过，不排队。


| 触发      | 默认                                  | 要点                                                                                                                    |
| ------- | ----------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| 节日问候    | 公历节假日 / 农历年表 / 老师生日                 | 当天第一次上线欢迎直接换成祝福，整天只说一次；凌晨/深夜先祝福再跟一句休息提醒；tick 仅在欢迎没说过时兜底；`depart` 时 tick 不说、欢迎仍可换；历史 `【节日】`；回写 `greeted`               |
| 空闲轻搭话   | 老师安静 15 分钟；两次搭话间隔默认 30 分钟；每天最多 3 次  | 欢迎/照料之后只需再等 `after_sec`，不占用搭话冷却；深夜/凌晨不闲聊；上一轮是 `depart` 不闲聊；仅 `secure_play` / `steady` 可开口；历史 `【搭话】`；不检索记忆             |
| goal 回访 | 老师安静 5 分钟后；每条 goal 冷却 6 小时；每天最多 1 次 | 扫记忆 `category=goal`，轻轻提起最久未回访的一条；不催、不盘问、不编造进展；老师说「先别提」等则 mute 上一条 7 天；休息时段 / `depart` 不回访；气候闸与空闲相同；历史 `【回访】`；直接注入该条记忆 |
| 午饭照料    | 12:00–12:30，每天一次                    | 短提醒吃饭，不催；`cling_risk` 更短；可检索作息记忆；欢迎（及任何已写入 `last_proactive_at` 的主动开口）之后再等 `idle.after_sec`；窗口内等待时不改发搭话或回访             |
| 睡觉照料    | 23:00–23:20，每天一次                    | 提醒休息；允许在休息时段触发；历史 `【提醒】`；与午饭相同，相对欢迎再等 `idle.after_sec`；节日欢迎里的休息补发仍同一轮发出、不等间隔                                          |
| 同轮补充    | Planner `followup_ok`（按「能否扩展」）      | 仅用户 chat 双模型路径、首句成功后最多再扩 1 句；本地回落 / 欢迎 / idle / care / goal / festival 不续说；历史 `【补充】`                                  |


调度状态落 `data/memory/proactive.json`（含 `festival_done`）。跨日清当日节日标记。节日成功才标记；失败可下次再试。关闭：`proactive.idle.enabled` / `proactive.care.enabled` / `proactive.goal.enabled` / `proactive.continue.enabled` / `proactive.festival.enabled`。

## ASR 脏文本过滤

腾讯云 ASR 空结果曾被前端误当成识别成功，把  
`[Tencent Speech Recognizer]Didnt recognize vailable content!` 整段发进 `chat`，从而误触发 Planner。

**后端兜底**（`[app/input_filter.py](app/input_filter.py)` + `[app/ws_handler.py](app/ws_handler.py)`）：

- 空串、仅空白，或匹配腾讯云 ASR / SDK 错误模板的 `content` 在 WS 入口直接丢弃
- **不**调用 Orchestrator / Planner / 记忆抽取，**不**写入 session history
- 回一条轻量 `chat_response`：`刚才没听清，请再说一次～`，`emotion=curious`，`context_used=asr_filter`

**前端根因修复**（需重编客户端）：`[TencentSpeechRecognizer.cpp](../frontend/AronaAI_Spine_WindowsClient/QtUtils/TencentSpeechRecognizer.cpp)` 空结果改走 `errorOccurred`；`[MainController.cpp](../frontend/AronaAI_Spine_WindowsClient/QtMainFile/MainController.cpp)` 对同类脏串不再 `sendChatMessage`。

## 世界观知识 RAG

1. 按 `[data/knowledge/WRITING.md](data/knowledge/WRITING.md)` 在 `data/knowledge/corpus/` 编写 Markdown（`##` 切块）
2. 嵌入模型默认使用本地目录 `../models/bge-small-zh-v1.5`（配置项 `knowledge.embedding_model_path`）
3. 灌库：

```bash
python scripts/ingest_knowledge.py
# 大幅改标题/结构后建议：
python scripts/ingest_knowledge.py --rebuild
```

1. 冒烟检索：`python scripts/test_knowledge_rag.py`；时间感知查询单测（不加载 BGE）：`python scripts/test_query_time.py`
2. 在 `config.yaml` 设 `knowledge.enabled: true` 后重启后端

对话主路径里记忆与知识检索共用一轮 BGE：同时编码老师原文和带当前时间的附带查询（相对日期会先展开成与记忆写入相同的绝对日期）。两路召回按 key / 标题合并后截断 `top_k`。写入 Planner 的记忆命中按 key 冷却，默认 `memory.inject_cooldown_sec: 3600` 内不重复注入，空缺由下一名候选补上；抽取器看已有记忆时不走该冷却。知识命中（过滤后的 lore 文本）可按 query 向量近义复用，默认 `query_cache_min_cosine: 0.92`，缓存按自然日区分以免跨日复用带日期的命中；`ingest` / `--rebuild` 会清空该缓存。不缓存 Planner 草稿或最终台词。当前时间同时用于检索附带查询，并以 `【当前时间】` 写入 Planner user 消息（不写入 Renderer）。

## 配置

由 `config.example.yaml` 复制为 `config.yaml`（已 gitignore）。相对路径均相对后端根目录解析（源码为 `backend/`；便携包为解压目录；可用环境变量 `ARONA_BACKEND_DIR` 覆盖）。下表默认值与示例文件一致。


| 配置段            | 说明                                              |
| -------------- | ----------------------------------------------- |
| `server`       | 监听地址、端口、WebSocket 路径                            |
| `model`        | 是否加载 Arona-Renderer GGUF、模型路径、上下文长度与采样参数        |
| `prompt`       | 本地单模型回落用 system prompt（双模型 Renderer 不读此项）       |
| `conversation` | 多轮历史保留轮数                                        |
| `knowledge`    | 世界观 RAG（语料、Chroma、嵌入模型、检索阈值、近义 query 缓存）        |
| `memory`       | SQLite + Chroma 记忆、混合检索、注入冷却、去重/调和、DeepSeek 抽取器 |
| `planner`      | 双模型 Planner（DeepSeek 意图卡）与轮次路由器                 |
| `listen`       | 连续听写的静音提交与接话窗口                                  |
| `proactive`    | 上线欢迎、关系气候、空闲搭话、照料、goal 回访、节日、同轮补充               |
| `token_budget` | 注入 prompt 的 memory / knowledge / history 预算     |
| `logging`      | 日志目录、文件名、级别与滚动                                  |




### `server`


| 配置项       | 默认          | 说明                       |
| --------- | ----------- | ------------------------ |
| `host`    | `127.0.0.1` | HTTP / WebSocket 监听地址    |
| `port`    | `20456`     | 监听端口                     |
| `ws_path` | `/ws`       | WebSocket 路径，需与 Qt 客户端一致 |




### `model`


| 配置项              | 默认                   | 说明                                                                                                                |
| ---------------- | -------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `enabled`        | `false`              | 是否加载 Arona-Renderer GGUF。`true`：Planner + Renderer 双模型，Planner 失败时回落本地 GGUF 推理；`false`：不加载 GGUF，直接把 Planner 草稿当台词 |
| `gguf_path`      | Renderer V2.4 Q4_K_M | GGUF 路径。单模型回落可改成注释里的 AronaLM-Generator-V2.0                                                                       |
| `n_ctx`          | `2048`               | llama.cpp 上下文长度                                                                                                   |
| `n_gpu_layers`   | `-1`                 | 放到 GPU 的层数；`-1` 表示全部上 GPU                                                                                         |
| `max_new_tokens` | `72`                 | 单次生成的最大新 token 数                                                                                                  |
| `temperature`    | `0.7`                | 采样温度                                                                                                              |
| `top_p`          | `0.85`               | nucleus 采样                                                                                                        |
| `repeat_penalty` | `1.1`                | 重复惩罚                                                                                                              |




### `prompt`


| 配置项                   | 默认     | 说明                                                      |
| --------------------- | ------ | ------------------------------------------------------- |
| `local_system_prompt` | 示例人设长文 | 仅本地单模型路径（`build_messages()`）使用。Planner / Renderer 不拼接此项 |




### `conversation`


| 配置项                 | 默认   | 说明                            |
| ------------------- | ---- | ----------------------------- |
| `max_history_turns` | `12` | 会话保留的用户–助手轮数（消息条数约为 `2 ×` 该值） |




### `knowledge`


| 配置项                      | 默认                            | 说明                                      |
| ------------------------ | ----------------------------- | --------------------------------------- |
| `enabled`                | `false`                       | 是否启用世界观 RAG                             |
| `corpus_dir`             | `data/knowledge/corpus`       | Markdown 语料目录                           |
| `chroma_path`            | `data/knowledge/chroma`       | Chroma 向量库路径                            |
| `collection`             | `arona_lore`                  | Chroma collection 名                     |
| `embedding_model_path`   | `../models/bge-small-zh-v1.5` | 本地 BGE 嵌入模型（与记忆共用）                      |
| `retrieve_top_k`         | `3`                           | 最终注入的知识条数上限                             |
| `candidate_top_k`        | `8`                           | 过滤前召回的候选数                               |
| `max_inject_chars`       | `400`                         | 注入字符硬上限；与 `token_budget.knowledge` 取较小值 |
| `min_score`              | `0.45`                        | 与查询有词汇重叠时的相似度下限                         |
| `min_score_no_overlap`   | `0.62`                        | 无词汇重叠时的更高相似度下限                          |
| `score_margin`           | `0.08`                        | 只保留与最高分差距不超过该值的命中                       |
| `query_cache_enabled`    | `true`                        | 是否按 query 向量近义复用知识命中                    |
| `query_cache_size`       | `64`                          | 近义缓存条数                                  |
| `query_cache_min_cosine` | `0.92`                        | 复用缓存所需的 query 余弦相似度                     |




### `memory`


| 配置项                     | 默认                      | 说明                                       |
| ----------------------- | ----------------------- | ---------------------------------------- |
| `db_path`               | `data/memory/memory.db` | SQLite（含 FTS5）路径                         |
| `chroma_path`           | `data/memory/chroma`    | 记忆向量索引路径                                 |
| `collection`            | `arona_memory`          | Chroma collection 名                      |
| `retrieve_top_k`        | `3`                     | 对话注入的记忆条数上限                              |
| `candidate_top_k`       | `10`                    | 混合检索（FTS + 向量）的候选数                       |
| `min_score`             | `0.35`                  | 记忆召回相似度下限                                |
| `max_inject_chars`      | `400`                   | 本地回落注入字符硬上限；与 `token_budget.memory` 取较小值 |
| `inject_cooldown_sec`   | `3600`                  | 同一 key 写入 Planner 的冷却秒数；`0` 关闭。抽取侧检索不受影响 |
| `extract_context_top_k` | `8`                     | 抽取时检索已有记忆的条数，供模型对照更新                     |
| `reconcile_enabled`     | `true`                  | 写入后删除同类别、高相似的旧条目（`goal` 除外）              |
| `reconcile_min_score`   | `0.82`                  | 调和删除的相似度下限                               |
| `reconcile_top_k`       | `5`                     | 调和 / 去重时的相似检索条数                          |
| `dedup_enabled`         | `true`                  | 写入前合并同类别近重复条目（`goal` 除外）                 |
| `dedup_min_score`       | `0.88`                  | 去重合并的相似度下限                               |


`memory.extractor`：


| 配置项                    | 默认                         | 说明                          |
| ---------------------- | -------------------------- | --------------------------- |
| `enabled`              | `true`                     | 是否启用异步记忆抽取                  |
| `base_url`             | `https://api.deepseek.com` | OpenAI 兼容 API 根地址           |
| `api_key`              | `YOUR_DEEPSEEK_API_KEY`    | 未填写或仍为占位符时走 `fallback`      |
| `model`                | `deepseek-v4-flash`        | 抽取模型名                       |
| `timeout_sec`          | `15`                       | 单次 HTTP 超时（秒）               |
| `max_calls_per_day`    | `512`                      | 每日抽取调用上限                    |
| `every_n_turns`        | `6`                        | 每 N 轮强制抽一次（另有「请记住」等启发式立即触发） |
| `extract_buffer_turns` | `6`                        | 抽取缓冲攒满该轮数也触发                |
| `fallback`             | `regex`                    | DeepSeek 失败或无 Key 时的降级方式    |




### `planner`


| 配置项                  | 默认                         | 说明                                                            |
| -------------------- | -------------------------- | ------------------------------------------------------------- |
| `enabled`            | `true`                     | 是否走 DeepSeek 意图卡。关闭、无 Key 或失败时回落本地 GGUF（若 `model.enabled`）或草稿 |
| `base_url`           | `https://api.deepseek.com` | OpenAI 兼容 API 根地址                                             |
| `api_key`            | `YOUR_DEEPSEEK_API_KEY`    | Planner 与轮次路由器共用                                              |
| `model`              | `deepseek-v4-flash`        | Planner / 路由器模型名                                              |
| `timeout_sec`        | `20`                       | Planner 请求超时（秒）                                               |
| `temperature`        | `0.3`                      | Planner 采样温度                                                  |
| `max_tokens`         | `512`                      | Planner 输出上限                                                  |
| `router_enabled`     | `true`                     | 连续听写时，规则拿不准再调短超时 LLM 判断 ignore / wait / reply                 |
| `router_timeout_sec` | `3`                        | 路由器超时（秒）；不复用 Planner 的 20s 超时                                 |
| `router_max_tokens`  | `64`                       | 路由器输出上限                                                       |




### `listen`

连续听写的轮次切分（ASR 片段先入缓冲，静音后再提交）：


| 配置项                       | 默认     | 说明                         |
| ------------------------- | ------ | -------------------------- |
| `silence_commit_ms`       | `1000` | 完整句的静音提交等待（毫秒）             |
| `incomplete_commit_ms`    | `1800` | 半句（停在「然后 / 就是 / 那个」等）时加长等待 |
| `continuation_window_sec` | `8`    | 阿洛娜刚说完后的接话窗口；窗口内未点名也视为对她说  |




### `proactive`



#### `welcome`


| 配置项       | 默认     | 说明                            |
| --------- | ------ | ----------------------------- |
| `enabled` | `true` | WebSocket `connected` 后是否主动问候 |




#### `relationship`


| 配置项                   | 默认                              | 说明                                                              |
| --------------------- | ------------------------------- | --------------------------------------------------------------- |
| `enabled`             | `true`                          | 是否启用关系气候。关闭后不分类、不更新、不按气候沉默                                      |
| `persist_path`        | `data/memory/relationship.json` | 状态落盘路径，重启不重置                                                    |
| `alpha`               | `0.3`                           | 事件 Δ 的惯性系数：`new = clamp(old + α·Δ − β·(old − baseline), −1, 1)` |
| `beta`                | `0.02`                          | 向 baseline 回归的系数                                                |
| `daily_abs_cap`       | `0.35`                          | 每个维度每日绝对变化上限                                                    |
| `makeup_tension`      | `0.7`                           | 张力高于该值时，正向信任修正放大                                                |
| `makeup_trust_scale`  | `1.5`                           | 上述放大倍数                                                          |
| `cling_dependence`    | `0.55`                          | 依赖高于该值且张力低 → `cling_risk`                                       |
| `high_dependence`     | `0.7`                           | 依赖高于该值时额外禁「增加依赖 / 追问还在不在」                                       |
| `climate_stick_turns` | `3`                             | 非紧急档需连续若干轮才切换气候                                                 |
| `baseline_trust`      | `0.55`                          | 信任回归中心                                                          |
| `baseline_dependence` | `0.30`                          | 依赖回归中心                                                          |
| `baseline_tension`    | `0.25`                          | 张力回归中心                                                          |




#### `idle`


| 配置项            | 默认     | 说明                                          |
| -------------- | ------ | ------------------------------------------- |
| `enabled`      | `true` | 是否启用空闲轻搭话                                   |
| `after_sec`    | `900`  | 老师安静多久后可搭话（秒，默认 15 分钟）。欢迎/照料之后也按此间隔，不占用搭话冷却 |
| `cooldown_sec` | `1800` | 两次搭话最短间隔（秒，默认 30 分钟）                        |
| `max_per_day`  | `3`    | 每天最多搭话次数                                    |




#### `care`


| 配置项                         | 默认                           | 说明                                      |
| --------------------------- | ---------------------------- | --------------------------------------- |
| `enabled`                   | `true`                       | 是否启用午饭 / 睡觉提醒                           |
| `persist_path`              | `data/memory/proactive.json` | 主动调度落盘（含节日标记），idle / goal / festival 共用 |
| `lunch_start` / `lunch_end` | `12:00` / `12:30`            | 午饭窗口                                    |
| `sleep_start` / `sleep_end` | `23:00` / `23:20`            | 睡觉提醒窗口                                  |




#### `goal`


| 配置项                  | 默认       | 说明                        |
| -------------------- | -------- | ------------------------- |
| `enabled`            | `true`   | 是否回访记忆里的 `category=goal`  |
| `min_after_user_sec` | `300`    | 老师安静多久后才可回访（秒）            |
| `cooldown_sec`       | `21600`  | 同一条 goal 的回访冷却（秒，默认 6 小时） |
| `mute_sec`           | `604800` | 老师说「先别提」后静音该条的秒数（默认 7 天）  |
| `max_per_day`        | `1`      | 每天最多回访次数                  |




#### `continue`


| 配置项         | 默认     | 说明                              |
| ----------- | ------ | ------------------------------- |
| `enabled`   | `true` | Planner 标 `followup_ok` 时是否再补一句 |
| `delay_sec` | `2`    | 首句发出后再补一句的延迟（秒）                 |




#### `festival`


| 配置项       | 默认     | 说明                       |
| --------- | ------ | ------------------------ |
| `enabled` | `true` | 是否在公历节假日 / 农历年表 / 老师生日问候 |




### `token_budget`

按约 `1.6` 字/token 换成字符后，与对应 `max_inject_chars` 取较小值再截断。


| 配置项         | 默认    | 说明                        |
| ----------- | ----- | ------------------------- |
| `memory`    | `250` | 本地回落注入长期记忆的 token 预算      |
| `knowledge` | `250` | 知识注入预算（Planner 与本地回落都会截断） |
| `history`   | `700` | 本地回落拼进 prompt 的历史字符预算     |




### `logging`


| 配置项            | 默认                  | 说明              |
| -------------- | ------------------- | --------------- |
| `dir`          | `logs`              | 日志目录            |
| `filename`     | `arona-backend.log` | 日志文件名           |
| `level`        | `INFO`              | 日志级别            |
| `max_bytes`    | `10485760`          | 单文件滚动大小（10 MiB） |
| `backup_count` | `5`                 | 保留的旧日志份数        |


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

正常回复：`{"type":"chat_response","content":"...","emotion":"...","context_used":"...","latency":...}`。

连接后若欢迎开启，服务端会再推一条 `chat_response`（`context_used` 含 `welcome`，节日当天首次则为 `festival`；凌晨/深夜节日可能再跟一条 `sleep`）。空闲搭话 / 照料 / goal 回访同样推 `chat_response`（`context_used` 含 `idle` / `lunch` / `sleep` / `goal`）。Planner 标 `followup_ok` 时，同一轮用户消息后可能再跟一条 `chat_response`（`context_used` 含 `continue`）。关系层决定沉默时**不**发 `chat_response`，前端保持安静。

若 `content` 被判定为 ASR 脏文本，仍返回 `chat_response`，但 `context_used` 为 `"asr_filter"`，且不会进入双模型链路。