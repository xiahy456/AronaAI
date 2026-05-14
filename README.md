# 阿罗娜AI / AronaAI

<p align="center">
  <img src="assets/logo.png" alt="AronaAI Logo" width="200"/>
</p>

<p align="center">
  <em>基于《蔚蓝档案》角色"阿罗娜"的人工智能助手</em>
</p>

<p align="center">
  <em>An AI assistant based on "Arona" from "Blue Archive"</em>
</p>

---

## 📖 项目简介 / Introduction

**阿罗娜AI** 是一个以游戏《蔚蓝档案》（Blue Archive）中角色"阿罗娜"为原型打造的桌面AI助手项目。在设定上，她是“什亭之匣”的操作系统管理员，性格开朗、热情，乐于帮助老师解决问题。

本项目集成了Arona语言模型（AronaLM）、语音合成（TTS）、语音识别（ASR）、Spine 2D 角色动画等技术，旨在提供一个可爱、有趣且功能完整的桌面交互体验。

**AronaAI** is a desktop AI assistant project based on the character "Arona" from the mobile game "Blue Archive". She comes from Kivotos, serves as the operating system administrator of the Shittim Chest, and has a cheerful, warm personality who loves helping Sensei solve problems.

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
├── llm/                        # 大语言模型训练
│   └── aronaLM/                # Arona 专属语言模型
│       ├── model/              # 模型定义（Transformer 架构）
│       ├── training/           # 训练脚本（预训练 + LoRA 微调）
│       ├── inference/          # 推理模块
│       ├── configs/            # 训练配置
│       ├── scripts/            # 数据处理与测试脚本
│       ├── documents/          # 角色设定文档
│       └── data/               # 训练数据
│
├── gpt-sovits/                 # GPT-SoVITS 语音合成（需用户手动添加）
│   ├── GPT_SoVITS/             # 核心模型
│   ├── GPT_weights/            # 模型权重
│   ├── api_v2.py               # API 服务
│   ├── webui.py                # Web 界面
│   └── ref_audio/              # 参考音频
│
├── models/                     # 预训练模型存放目录
├── vosk/                       # Vosk 离线语音识别
├── scripts/                    # 环境测试脚本
├── docs/                       # 文档
├── font/                       # 字体文件
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
- **语音合成（TTS）**：基于 GPT-SoVITS 的高质量语音合成，还原阿罗娜的声音
- **语音识别（ASR）**：支持在线（腾讯云）和离线（Vosk）两种识别方式
- **语音唤醒**：支持语音输入触发对话

### 🖥️ 桌面客户端
- **Spine 2D 动画**：使用 Spine 实现阿罗娜的 Live2D 角色动画
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
| Node.js | (可选) 用于部分工具脚本 |
| CUDA | 11.8+ (GPU 加速，可选) |
| 操作系统 | Windows 10/11 (客户端) / Linux 及其衍生系统 |

### 后端启动 / Backend Setup

```bash
# 1. 安装 Python 依赖
pip install -r scripts/requirements.txt

# 2. 启动 WebSocket 服务
python -m backend.ai_service.py --host 0.0.0.0 --port 20456

# 3. (可选) 运行测试
python backend/test_engine.py
```

### 客户端构建 / Client Build

Windows 客户端使用 Visual Studio 2022（后改为Visual Studio 2026） 和 Qt 构建：

1. 安装 [Qt 6.x](https://www.qt.io/download) 和 [Visual Studio 2026](https://visualstudio.microsoft.com/)
2. 打开 `frontend/AronaAI_Spine_WindowsClient/AronaAI_Spine_WindowsClient.sln`
3. 配置 Qt 版本和编译选项
4. 编译运行

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

## 🗺️ 开发路线图 / Roadmap

- [x] 基础对话引擎
- [x] RAG 知识检索
- [x] 长期记忆系统
- [x] 语义缓存优化
- [x] Windows 桌面客户端
- [x] Spine 2D 角色动画
- [x] GPT-SoVITS 语音合成
- [ ] 语音唤醒功能完善
- [ ] macOS/Linux 客户端支持
- [ ] 多语言支持
- [ ] 插件系统
- [ ] 知识库可视化编辑

---

## 📄 许可证 / License

本项目基于 Apache License 2.0 开源协议。

```
Copyright 2026 xia_hy456

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

---

<p align="center">
  <sub>/ **  就像草莓牛奶一样的，甜蜜的奇迹  ** /</sub>
</p>
