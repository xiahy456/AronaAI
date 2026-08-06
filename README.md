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

---

## 🏗️ 项目架构 / Project Architecture

```
arona-ai/
├── backend/                    # Python 后端服务
│   ├── ai_service.py           # WebSocket 服务主程序（FastAPI）
│   ├── arona_engine.py         # 核心引擎 - 集成所有模块
│   ├── chain_compressor.py     # RAG 链路压缩模块
│   ├── config.py               # 全局配置文件
│   ├── conversation_manager.py # 对话历史管理
│   ├── embeddings.py           # 文本嵌入模块（TF-IDF / Sentence-Transformers）
│   ├── knowledge_base.py       # RAG 知识库管理
│   ├── memory_manager.py       # 长期记忆管理
│   ├── model_loader.py         # 模型加载器（基础模型 + LoRA）
│   ├── semantic_cache.py       # 语义缓存系统
│   ├── vector_store.py         # 向量数据库（ChromaDB）
│   ├── test_arona.py           # 快速测试脚本
│   └── test_engine.py          # 完整测试脚本
│
├── frontend/                   # 桌面客户端
│   └── AronaAI_Spine_WindowsClient/  # Windows 桌面客户端（Qt/C++）
│       ├── QtMainFile/         # 主界面、控制器、WebSocket 通信
│       ├── QtUtils/            # 工具类（录音、语音识别、动画等）
│       ├── QHotkey/            # 全局快捷键支持
│       ├── spine-cpp/          # Spine 2D 动画运行时
│       ├── Assets/             # 资源文件（Spine 动画、UI 图片）
│       ├── Config/             # 配置文件
│       └── Dict/               # 词典文件
│
├── llm/                        # 语言模型训练
│   └── aronaLM/                # Arona 专属语言模型
│       ├── model/              # 模型定义（Transformer 架构）
│       ├── training/           # 训练脚本（预训练 + LoRA 微调）
│       ├── inference/          # 推理模块
│       ├── configs/            # 训练配置
│       ├── scripts/            # 数据处理与测试脚本
│       ├── documents/          # 角色设定文档
│       └── data/               # 训练数据
│
├── gpt-sovits/                 # GPT-SoVITS 语音合成（需用户手动部署，或使用外部服务）
│   ├── GPT_SoVITS/             # 核心模型
│   ├── GPT_weights_v2/         # GPT权重
│       └── ALuoNa_cn-e15.ckpt  # 阿洛娜GPT权重
│   ├── SoVITS_weights_v2/      # SoVITS权重
│       └── ALuoNa_cn_e16_s256.pth    # 阿洛娜SoVITS权重
│   ├── api_v2.py               # API 服务
│   └── ref_audio/              # 参考音频
│       └── Arona/              # 阿洛娜参考音频目录
│            └── arona_academy_in_2.ogg   # 参考音频
│
├── docs/                       # 相关文档
│   └── requirements.txt        # 依赖项文件
├── models/                     # 相关模型存放目录
│   └── bge-small-zh-v1.5/      # BGE模型
│   └── paraphrase-multilingual-MiniLM-L12-v2/  # 向量嵌入模型
├── vosk/                       # Vosk 离线语音识别（（可选）需用户手动部署，推荐直接使用腾讯云语音识别服务）
└── assets/                     # 项目资源
```

---

## ✨ 核心功能 / Core Features

### 🤖 AI 对话引擎
- **Arona语言模型**：使用 LoRA 微调构建的语言模型
- **RAG 知识检索**：通过向量数据库检索相关知识，增强回答准确性
- **长期记忆**：自动识别并存储用户信息，在对话中回忆相关记忆
- **语义缓存**：基于语义相似度的缓存系统，提升响应速度
- **对话管理**：多轮对话历史管理，支持会话过期和截断

### 🎤 语音交互
- **语音合成（TTS）**：基于 GPT-SoVITS 的高质量语音合成，还原阿洛娜的声音
- **语音识别（ASR）**：支持在线（腾讯云）和离线（Vosk）两种识别方式
- **语音唤醒**：支持语音输入触发对话

### 🖥️ 桌面客户端
- **Spine 2D 动画**：使用 Spine 实现阿洛娜的 Live2D 角色动画
- **Qt 界面**：基于 Qt/C++ 的 Windows 桌面应用
- **WebSocket 通信**：与后端服务实时通信，支持流式输出
- **全局快捷键**：支持自定义快捷键操作
- **系统托盘**：最小化到系统托盘运行

### 🎯 技术亮点
- **语义缓存**：改进的语义相似度匹配算法，防止短文本误匹配
- **链路压缩**：对 RAG 检索结果进行去重、排序、摘要提取
- **记忆管理**：自动识别用户个人信息并长期存储
- **双模式嵌入**：支持本地 TF-IDF 和外部 Sentence-Transformers 两种嵌入方式

---

## 🚀 快速开始 / Quick Start

### 环境要求 / Prerequisites

| 组件 | 要求 |
|------|------|
| Python | 3.10+ |
| CUDA | 11.8+ (GPU 加速，可选) |
| 操作系统 | Windows 10/11 (客户端) / Linux 及其衍生系统 (服务端) |
| 相关环境 | 请按照docs/requirement.txt配置 |

### 后端启动 / Backend Setup

#### 启动前准备 / Pre-startup Preparation

在启动后端服务之前，请完成以下准备工作：

**1. 放置模型文件**

根据项目目录结构，将所需模型文件放置在 `models/` 目录下：

```
models/
├── bge-small-zh-v1.5/                # BGE 中文嵌入模型（用于链路压缩句子打分）
├── paraphrase-multilingual-MiniLM-L12-v2/  # 多语言嵌入模型（用于向量检索）
└── aronalm-v2.0-normal-gguf/  # AronaLM语言模型
```

> **提示**：如果使用本地 TF-IDF 嵌入模式（`embedding.use_external: false`），则无需放置 `paraphrase-multilingual-MiniLM-L12-v2` 模型。

**2. 配置 `config.yaml`**

复制并重命名配置文件，然后根据实际模型路径修改配置：

```bash
# 复制配置文件
cp backend/config.example.yaml backend/config.yaml
```

> **注意**：`config.yaml` 已在 `.gitignore` 中，不会被提交到版本控制，请放心修改。

**3. 启动服务**

```bash
# 1. 安装 Python 依赖
pip install -r docs/requirements.txt

# 2. 启动 WebSocket 服务
python -m backend.ai_service.py --host 0.0.0.0 --port 20456

# 3. (可选) 运行测试
python backend/test_model_backend.py
```

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

找到 `frontend/AronaAI_Spine_WindowsClient/Config/config.example.json`，复制并重命名配置文件，然后根据实际模型路径修改配置：

```bash
# 复制并重命名配置文件
cp frontend/AronaAI_Spine_WindowsClient/Config/config.example.json frontend/AronaAI_Spine_WindowsClient/Config/config.json
```

```json
{
  "settings": {
    "dict_path": "D:/arona-ai/frontend/AronaAI_Spine_WindowsClient/Dict/dict_zh.json",
    "icon_path": "D:/arona-ai/frontend/AronaAI_Spine_WindowsClient/Assets/ProgramAssets/Icon.png",
    "qhotkey_path": "D:/arona-ai/frontend/AronaAI_Spine_WindowsClient/QHotkey",
    "text_box_path": "D:/arona-ai/frontend/AronaAI_Spine_WindowsClient/Assets/ProgramAssets/TextBox.png",
    "push_button_path": "D:/arona-ai/frontend/AronaAI_Spine_WindowsClient/Assets/ProgramAssets/PushButton.png",
    "settings_bg_path": "D:/arona-ai/frontend/AronaAI_Spine_WindowsClient/Assets/ProgramAssets/SettingsMainBGWidget.png",
    "close_button_path": "D:/arona-ai/frontend/AronaAI_Spine_WindowsClient/Assets/ProgramAssets/CloseButton.png",
    "top_information_path": "D:/arona-ai/frontend/AronaAI_Spine_WindowsClient/Assets/ProgramAssets/TopInformationWidget.png",
    "font_path": "D:/arona-ai/assets/font/Blueaka/BlueakaBeta2GBKDemiBold-Regular.ttf",
    "arona_ai_mode_switch_button_0": "D:/arona-ai/frontend/AronaAI_Spine_WindowsClient/Assets/ProgramAssets/AronaAIModeSwitchButton_0.png",
    "arona_ai_mode_switch_button_1": "D:/arona-ai/frontend/AronaAI_Spine_WindowsClient/Assets/ProgramAssets/AronaAIModeSwitchButton_1.png",
    "origin_logo_path": "D:/arona-ai/frontend/AronaAI_Spine_WindowsClient/Assets/ProgramAssets/BALogo.png",
    ...
  },
  "aronalm": {
    "websocket_url": "ws://your.aronalm.ip:20456/ws",
    ...
  },
  "spine": {
    "skelOrJson_path": "D:/arona-ai/frontend/AronaAI_Spine_WindowsClient/Assets/AronaSpineAssets/arona_spr.json",
    "atlas_path": "D:/arona-ai/frontend/AronaAI_Spine_WindowsClient/Assets/AronaSpineAssets/Arona01.atlas",
    ...
  },
  "tts": {
    "host": "your.gpt.sovits.ip",
    "port": 9880,
    "gpt_path": "GPT_weights_v2/ALuoNa_cn-e15.ckpt",
    "sovits_path": "SoVITS_weights_v2/ALuoNa_cn_e16_s256.pth",
    "ref_audio_path": "ref_audio/Arona/arona_academy_in_2.ogg",
    "prompt_text": "这里为您准备了各种课程和活动，请按您喜欢的方式安排日程吧！",
    ...
  },
  "vosk": {
    "model_path": "path/to/vosk-model-small-cn-0.22"
  },
  ...
}
```

> **注意**：
 - 请将上述路径中的 `D:/arona-ai` 替换为你本地的项目实际**绝对路径**。
 - 请将AronaLM后端服务、GPT-SoVITS服务地址的地址、端口按照你的实际情况进行填写。

**2. 配置腾讯云语音识别（可选）**

如果使用腾讯云语音识别服务，需要在 `tencent_speech_recognizer` 中填写自己的 `secret_id` 和 `secret_key`，或者通过环境变量配置：

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

---

## 🔧 配置说明 / Configuration

### 后端配置 (`backend/config.py`)

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `MODEL_CONFIG` | 模型路径、生成参数 | - |
| `EMBEDDING_CONFIG` | 嵌入模型选择（本地/外部） | 外部模型 |
| `VECTOR_DB_CONFIG` | ChromaDB 向量数据库配置 | - |
| `CACHE_CONFIG` | 语义缓存参数 | 阈值 0.92 |
| `CONVERSATION_CONFIG` | 对话历史管理 | 保留 10 轮 |
| `MEMORY_CONFIG` | 长期记忆配置 | - |
| `COMPRESSOR_CONFIG` | 链路压缩参数 | - |

### 客户端配置

客户端配置文件位于 `frontend/AronaAI_Spine_WindowsClient/Config/`，可配置：
- WebSocket 服务器地址和端口
- TTS 服务地址
- 语音识别参数
- 快捷键绑定

---

## 📚 模块详解 / Module Details

### Backend 模块

| 模块 | 文件 | 功能描述 |
|------|------|----------|
| **WebSocket 服务** | `ai_service.py` | FastAPI WebSocket 服务，处理客户端连接和消息路由 |
| **核心引擎** | `arona_engine.py` | 集成所有模块的统一调用接口，实现完整对话流程 |
| **模型加载** | `model_loader.py` | 加载基础模型和 LoRA 权重，支持聊天模板 |
| **对话管理** | `conversation_manager.py` | 多轮对话历史管理，支持会话过期和截断 |
| **知识库** | `knowledge_base.py` | RAG 知识检索增强生成 |
| **记忆管理** | `memory_manager.py` | 长期记忆的提取、存储和检索 |
| **语义缓存** | `semantic_cache.py` | 基于语义相似度的缓存系统 |
| **向量存储** | `vector_store.py` | ChromaDB 向量数据库封装 |
| **链路压缩** | `chain_compressor.py` | RAG 检索结果压缩优化 |
| **嵌入模型** | `embeddings.py` | 文本向量化（TF-IDF / Sentence-Transformers） |

### LLM 训练模块

| 模块 | 功能描述 |
|------|----------|
| **模型定义** | 基于 Transformer 的因果语言模型 |
| **预训练** | 从零开始的预训练流程 |
| **LoRA 微调** | 高效参数微调（亲密/普通两种风格） |
| **推理引擎** | 支持流式输出的对话推理 |

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
- **ChromaDB** - 向量数据库
- **GPT-SoVITS** - 语音合成模型
- **Vosk** - 离线语音识别
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
