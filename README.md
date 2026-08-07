# 阿洛娜AI / AronaAI

<p align="center">
  <img src="assets/logo.png" alt="AronaAI Logo" width="200"/>
</p>

<p align="center">
  <em>基于《蔚蓝档案》角色"阿洛娜"的人工智能助手</em>
</p>

<p align="center">
  <em>An AI assistant based on "Arona" from "Blue Archive"</em>
</p>

<p align="center">
  <em>项目地址：https://github.com/xiahy456/AronaAI</em>
</p>

---

## 📖 项目简介 / Introduction

**阿洛娜AI** 是一个以游戏《蔚蓝档案》（Blue Archive）中角色"阿洛娜"为原型打造的桌面AI助手项目。在设定上，她是“什亭之匣”的操作系统管理员，性格开朗、热情，乐于帮助老师（用户）解决问题。

本项目集成了Arona语言模型（AronaLM）、语音合成（TTS）、语音识别（ASR）、Spine 2D 角色动画等技术，旨在提供一个可爱、有趣且功能完整的桌面交互体验。

**AronaAI** is a desktop AI assistant project based on the character "Arona" from the game "Blue Archive". She serves as the operating system administrator of the Shittim Chest, and has a cheerful, warm personality who loves helping Sensei (user) solve problems.

This project integrates Arona Language Models (AronaLM), Text-to-Speech (TTS), Automatic Speech Recognition (ASR), Spine 2D character animation, and other technologies to provide a cute, lively, and fully-featured desktop interaction experience.

<p align="center">
  <img src="assets/running_example.png" alt="Running Example" width="600"/>
</p>

<p align="center">
  <em>前端运行时截图</em>
</p>

<p align="center">
  <em>Frontend running screenshot</em>
</p>

---

## 🏗️ 项目架构 / Project Architecture

```
arona-ai/
├── backend/                    # Python 后端服务（FastAPI + WebSocket）
│   ├── app/                    # 应用核心
│   │   ├── main.py             # 服务入口
│   │   ├── orchestrator.py     # 对话编排（检索 → Prompt → 生成 → 记忆抽取）
│   │   ├── model_loader.py     # GGUF 模型加载（llama-cpp-python）
│   │   ├── knowledge.py        # 世界观知识 RAG
│   │   ├── conversation.py     # 多轮对话历史
│   │   ├── cache.py            # 响应缓存
│   │   ├── prompt.py           # Prompt 组装
│   │   ├── protocol.py         # WebSocket 协议消息
│   │   ├── ws_handler.py       # WebSocket 处理
│   │   ├── config.py           # 配置加载
│   │   └── memory/             # 长期记忆（SQLite + DeepSeek 抽取）
│   ├── scripts/                # 联调 / 灌库 / 测试脚本
│   ├── data/                   # 记忆库、知识语料与向量库
│   ├── config.example.yaml     # 配置模板
│   └── requirements.txt
│
├── frontend/                   # 桌面客户端
│   └── AronaAI_Spine_WindowsClient/  # Windows 桌面客户端（Qt/C++）
│       ├── QtMainFile/         # 主界面、控制器、WebSocket 通信
│       ├── QtUtils/            # 工具类（录音、语音识别、动画等）
│       ├── QHotkey/            # 全局快捷键支持
│       ├── spine-cpp/          # Spine 2D 动画运行时
│       ├── Assets/             # 资源文件（Spine 动画、UI 图片、字体）
│       ├── Config/             # 配置文件（资源路径为相对路径）
│       └── Dict/               # 词典文件
│
├── llm/                        # 语言模型
│   └── aronaLM/
│       └── finetune/           # Qwen3-1.7B QLoRA 微调（Unsloth）
│           ├── config/         # 训练 / 导出 / 推理配置
│           ├── training/       # 微调主脚本
│           ├── inference/      # 交互式推理测试
│           ├── export/         # GGUF 导出
│           ├── data-process/   # 数据预处理
│           └── start.bat       # Windows 一键训练
│
├── gpt-sovits/                 # GPT-SoVITS 语音合成（需用户手动部署，或使用外部服务）
│   ├── GPT_SoVITS/             # 核心模型
│   ├── GPT_weights_v2/         # GPT权重
│   │   └── ALuoNa_cn-e15.ckpt  # 阿洛娜GPT权重
│   ├── SoVITS_weights_v2/      # SoVITS权重
│   │   └── ALuoNa_cn_e16_s256.pth    # 阿洛娜SoVITS权重
│   ├── api_v2.py               # API 服务
│   └── ref_audio/              # 参考音频
│       └── Arona/              # 阿洛娜参考音频目录
│            └── arona_academy_in_2.ogg   # 参考音频
│
├── docs/                       # 相关文档
├── models/                     # 相关模型存放目录
│   ├── aronalm-v2.0-normal/    # AronaLM GGUF 语言模型
│   ├── bge-small-zh-v1.5/      # 知识 RAG 嵌入模型
│   └── Qwen3-1.7B-unsloth-bnb-4bit/  # 微调基座（仅训练时需要）
└── assets/                     # 项目资源
```

---

## ✨ 核心功能 / Core Features

### 🤖 AI 对话引擎
- **AronaLM（GGUF）**：通过 `llama-cpp-python` 加载微调后的 GGUF 模型，支持同步与流式生成
- **世界观知识 RAG**：Markdown 语料入库 ChromaDB，按需检索并注入 Prompt
- **长期记忆**：SQLite 持久化用户信息；DeepSeek 异步抽取（可降级为正则）
- **响应缓存**：相同问题快速命中，降低重复推理开销
- **对话管理**：多轮历史截断，配合 token budget 控制上下文长度

### 🎤 语音交互
- **语音合成（TTS）**：基于 GPT-SoVITS 的高质量语音合成，还原阿洛娜的声音
- **语音识别（ASR）**：基于腾讯云语音识别（SentenceRecognition）提供在线 ASR
- **语音唤醒**：支持语音输入触发对话

### 🖥️ 桌面客户端
- **Spine 2D 动画**：使用 Spine 实现阿洛娜的 Live2D 角色动画
- **Qt 界面**：基于 Qt/C++ 的 Windows 桌面应用
- **WebSocket 通信**：与后端服务实时通信，支持流式输出
- **全局快捷键**：支持自定义快捷键操作
- **系统托盘**：最小化到系统托盘运行

### 🎯 技术亮点
- **本地推理优先**：桌面端以 GGUF + llama.cpp 为主路径，降低在线 LLM 依赖
- **记忆与知识分离**：用户隐私进 memory，世界观设定进 knowledge corpus
- **异步记忆抽取**：对话主路径不阻塞；DeepSeek 失败时自动正则降级
- **QLoRA 微调链路**：Unsloth 微调 → 导出 GGUF → 后端直接加载

---

## 🚀 快速开始 / Quick Start

### 环境要求 / Prerequisites

| 组件 | 要求 |
|------|------|
| Python | 3.10+ |
| CUDA | 11.8（可选，llama.cpp GPU 层 / 微调训练） |
| 操作系统 | Windows 10/11 (客户端) / Linux 及其衍生系统 (服务端) |
| 后端依赖 | `backend/requirements.txt` |
| 微调依赖 | `llm/aronaLM/finetune/requirements.txt`（仅训练时需要） |

### 后端启动 / Backend Setup

#### 启动前准备 / Pre-startup Preparation

**1. 放置模型文件**

```
models/
├── aronalm-v2.0-normal/          # AronaLM GGUF（后端推理）
│   └── aronalm-v2.0-normal.Q4_K_M.gguf
└── bge-small-zh-v1.5/            # 知识 RAG 嵌入模型（启用 knowledge 时需要）
```

> **AronaLM**：请使用模型 [xiahy456/aronalm-v2.0-normal](https://www.modelscope.cn/models/xiahy456/aronalm-v2.0-normal)

**2. 配置 `config.yaml`**

```bash
# 在 backend/ 目录下
copy config.example.yaml config.yaml   # Windows
cp config.example.yaml config.yaml   # Linux / macOS
```

按需填写：
- `model.gguf_path`：GGUF 模型路径
- `memory.extractor.api_key`：DeepSeek API Key（可选；不填则记忆抽取走正则降级）
- `knowledge.enabled`：是否启用世界观 RAG（默认 `false`，启用前请先灌库）

> **注意**：`config.yaml` 已在 `.gitignore` 中，不会被提交到版本控制。

**3. 启动服务**

工作目录必须是 `backend/`：

```bash
conda activate shittim-chest   # 若使用已有 conda 环境
cd backend
pip install -r requirements.txt

python -m app.main
# 或
uvicorn app.main:app --host 127.0.0.1 --port 20456
```

默认 WebSocket：`ws://127.0.0.1:20456/ws`（与 Qt 客户端一致）。

健康检查：`GET http://127.0.0.1:20456/health`

**4. （可选）联调与知识库**

```bash
# WebSocket 冒烟测试（服务需已启动）
python scripts/smoke_ws.py

# 按 data/knowledge/WRITING.md 编写语料后灌库
python scripts/ingest_knowledge.py
# 大幅改标题/结构后建议：
python scripts/ingest_knowledge.py --rebuild

# 检索冒烟
python scripts/test_knowledge_rag.py
```

启用知识库：在 `config.yaml` 中设 `knowledge.enabled: true` 后重启后端。

### 客户端构建 / Client Build

Windows 客户端使用 Visual Studio 2022（后改为Visual Studio 2026） 和 Qt 构建：

1. 安装 [Qt 6.x](https://www.qt.io/download)（推荐6.5.3） 和 [Visual Studio 2026](https://visualstudio.microsoft.com/)，并在VS2026中安装`Qt VS Tools`扩展
2. 确保你拥有v143 (Visual Studio 2022)平台工具集，在该项目中需要使用此平台工具集
3. 确保你拥有Qt6.5.3的msvc2019_64，该项目中需要使用此Qt版本（Qt Version可在`Qt VS Tools`的设置中配置）
4. 打开 `frontend/AronaAI_Spine_WindowsClient/AronaAI_Spine_WindowsClient.sln`
5. 配置 Qt 版本和编译选项
6. 编译运行

#### 启动前准备 / Pre-startup Preparation

在启动客户端之前，请完成以下准备工作：

**1. 配置 `config.json`**

找到 `frontend/AronaAI_Spine_WindowsClient/Config/config.example.json`，复制并重命名配置文件，然后按需修改服务地址等配置：

```bash
# 复制并重命名配置文件
cp frontend/AronaAI_Spine_WindowsClient/Config/config.example.json frontend/AronaAI_Spine_WindowsClient/Config/config.json
```

```json
{
  "settings": {
    "dict_path": "Dict/dict_zh.json", // 词典文件路径
    "icon_path": "Assets/ProgramAssets/Icon.png",
    "qhotkey_path": "QHotkey",
    "text_box_path": "Assets/ProgramAssets/TextBox.png",
    "push_button_path": "Assets/ProgramAssets/PushButton.png",
    "settings_bg_path": "Assets/ProgramAssets/SettingsMainBGWidget.png",
    "close_button_path": "Assets/ProgramAssets/CloseButton.png",
    "top_information_path": "Assets/ProgramAssets/TopInformationWidget.png",
    "font_path": "Assets/ProgramAssets/font/Blueaka",
    "arona_ai_mode_switch_button_0": "Assets/ProgramAssets/AronaAIModeSwitchButton_0.png",
    "arona_ai_mode_switch_button_1": "Assets/ProgramAssets/AronaAIModeSwitchButton_1.png",
    "origin_logo_path": "Assets/ProgramAssets/BALogo.png",
    ...
  },
  "aronalm": {
    "websocket_url": "ws://your.aronalm.ip:20456/ws", // AronaLM 后端服务地址
    ...
  },
  "spine": {
    "skelOrJson_path": "Assets/AronaSpineAssets/arona_spr.json",
    "atlas_path": "Assets/AronaSpineAssets/Arona01.atlas",
    ...
  },
  "tts": {
    "host": "your.gpt.sovits.ip", // GPT-SoVITS 服务地址
    "port": 9880,
    "gpt_path": "GPT_weights_v2/ALuoNa_cn-e15.ckpt",
    "sovits_path": "SoVITS_weights_v2/ALuoNa_cn_e16_s256.pth",
    "ref_audio_path": "ref_audio/Arona/arona_academy_in_2.ogg",
    "prompt_text": "这里为您准备了各种课程和活动，请按您喜欢的方式安排日程吧！",
    ...
  },
  ...
}
```

> **注意**：
 - 资源路径相对**程序工作目录**解析；在 Visual Studio 中调试时默认为项目根目录，请勿直接双击 `x64/Debug` 或 `x64/Release` 下的 exe（工作目录会不对）。
 - 请将 AronaLM 后端服务、GPT-SoVITS 服务的地址、端口按实际情况填写。
 - 使用 `pack.ps1` 打包便携版时，脚本会自动写入与包内布局一致的相对路径。

**2. 配置腾讯云语音识别（必需）**

桌面客户端语音输入依赖腾讯云 ASR，请在 `tencent_speech_recognizer` 中填写自己的 `secret_id` 和 `secret_key`，或者通过环境变量配置：

- **方式一（推荐）**：设置环境变量 `TENCENT_SECRET_ID` 和 `TENCENT_SECRET_KEY`，配置文件中的 `${TENCENT_SECRET_ID}` 和 `${TENCENT_SECRET_KEY}` 会自动读取环境变量。
- **方式二**：直接在配置文件中填写你的腾讯云 API 密钥：
  ```json
  "tencent_speech_recognizer": {
    "secret_id": "your_secret_id_here",
    "secret_key": "your_secret_key_here"
  }
  ```

> **注意**：`config.json` 已在 `.gitignore` 中，不会被提交到版本控制，请放心修改。

### 语音合成服务 / TTS Service

```bash
# 启动 GPT-SoVITS API 服务
cd gpt-sovits
python api_v2.py
```

### 模型微调 / Finetune（可选）

若需自行微调阿洛娜风格模型，使用 `llm/aronaLM/finetune`（基于 Unsloth 对 Qwen3-1.7B 做 QLoRA，面向约 6–8GB 显存）：

```bat
cd llm\aronaLM\finetune
python -m venv .venv
.venv\Scripts\activate
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
pip install -r requirements.txt

REM 放置基座模型到 models/Qwen3-1.7B-unsloth-bnb-4bit 后：
start.bat
```

训练结束后可导出 GGUF，供后端 `model.gguf_path` 加载。详细说明见 [`llm/aronaLM/finetune/README.md`](llm/aronaLM/finetune/README.md)。

---

## 🔧 配置说明 / Configuration

### 后端配置 (`backend/config.yaml`)

由 `config.example.yaml` 复制而来，主要段落：

| 配置段 | 说明 |
|--------|------|
| `server` | 监听地址、端口、WebSocket 路径（默认 `/ws`） |
| `model` | GGUF 路径、上下文长度、采样参数、system prompt |
| `conversation` | 多轮历史保留轮数 |
| `knowledge` | 世界观 RAG（语料目录、Chroma、嵌入模型、检索阈值） |
| `memory` | SQLite 路径、检索条数、DeepSeek 抽取器与正则降级 |
| `cache` | 响应缓存开关与容量 |
| `token_budget` | memory / knowledge / history 注入预算 |

本地数据路径（均已 gitignore）：
- 记忆库：`backend/data/memory.db`
- 知识向量库：`backend/data/knowledge/chroma/`

### 客户端配置

客户端配置文件位于 `frontend/AronaAI_Spine_WindowsClient/Config/`，可配置：
- 资源文件相对路径（Dict / Assets / 字体等，相对项目工作目录）
- WebSocket 服务器地址和端口
- TTS 服务地址
- 语音识别参数
- 快捷键绑定

---

## 📚 模块详解 / Module Details

### Backend 模块

| 模块 | 路径 | 功能描述 |
|------|------|----------|
| **服务入口** | `app/main.py` | FastAPI 应用、健康检查、WebSocket 路由 |
| **对话编排** | `app/orchestrator.py` | 缓存 → 记忆/知识检索 → Prompt → 生成 → 异步记忆抽取 |
| **模型加载** | `app/model_loader.py` | llama-cpp-python 加载 GGUF，支持流式与 `<think>` 过滤 |
| **WebSocket** | `app/ws_handler.py` | 会话连接、消息分发 |
| **协议** | `app/protocol.py` | 客户端/服务端消息类型定义 |
| **对话历史** | `app/conversation.py` | 多轮历史管理与截断 |
| **知识 RAG** | `app/knowledge.py` | ChromaDB 检索世界观知识 |
| **记忆存储** | `app/memory/store.py` | SQLite 长期记忆读写 |
| **记忆抽取** | `app/memory/extractor.py` | DeepSeek 异步抽取（失败走正则） |
| **响应缓存** | `app/cache.py` | 相同输入快速返回 |
| **Prompt** | `app/prompt.py` | 组装 system / memory / knowledge / history |

**WebSocket 协议摘要**：连接后服务端发送 `{"type":"connected","session_id":"..."}`。客户端发起对话示例：

```json
{"type":"chat","content":"你好","stream":false,"options":{"use_cache":true,"use_rag":true,"use_memory":true}}
```

更多细节见 [`backend/README.md`](backend/README.md)。

### LLM 微调模块（`llm/aronaLM/finetune`）

基于 Unsloth 对本地 `Qwen3-1.7B-unsloth-bnb-4bit` 做 QLoRA 微调，ShareGPT JSONL 数据，训练后可导出 GGUF 供 llama.cpp / 后端使用。

| 模块 | 功能描述 |
|------|----------|
| **配置** | `config/config.yaml` 统一管理模型、LoRA、训练、导出、推理参数 |
| **训练** | `training/train.py` / `start.bat` 一键 QLoRA 微调 |
| **推理** | `inference/inference.py` 加载 LoRA 适配器做交互测试 |
| **导出** | 训练结束导出 LoRA 适配器与 GGUF（默认 `q4_k_m`） |
| **数据** | ShareGPT 格式 JSONL；可用 `data-process/` 合并预处理 |

---

## 📄 许可证 / License

本项目基于 Apache License 2.0 开源协议。

```
Copyright 2026 xia_hy456. All rights reserved.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

---

## 🙏 致谢 / Acknowledgements

- **《蔚蓝档案》(Blue Archive)** - 角色原型
- **Spine** - 2D 动画引擎
- **Qt** - 跨平台 GUI 框架
- **llama.cpp / llama-cpp-python** - 本地 GGUF 推理
- **Qwen3-1.7B** - 微调训练基底模型
- **Unsloth** - QLoRA 高效微调
- **ChromaDB** - 向量数据库
- **DeepSeek** - 记忆抽取 API
- **GPT-SoVITS** - 语音合成模型
- **腾讯云语音识别** - 在线语音识别
- **Sentence-Transformers** - 文本嵌入模型
- **感谢所有协助开发的贡献者们**

---

## ⭐ 关于开发者 / About Developer

- **项目发起者**: xia_hy456
- **发起者个人博客**: https://xia-hy456.top/
- **反馈问题**: 2066961858@qq.com

---

<p align="center">
  <sub>/* 就像草莓牛奶一样的，甜蜜的奇迹 */</sub>
</p>
