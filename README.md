# 阿洛娜AI

<p align="center">
  <img src="assets/logo.png" alt="AronaAI Logo" width="200"/>
</p>

<p align="center">
  <strong>基于<em>《蔚蓝档案》角色「阿洛娜」</em>的非交互式桌面AI</strong>
</p>

<p align="center">
  云端负责规划与抽取，本地负责人设与沉浸场景，关系张量与主动事件构建规则控制面，让你与阿洛娜相处而非对话。
</p>

<p align="center">
  <em>版本：2.2.1</em>
</p>

<p align="center">
  <strong>中文</strong> · <a href="README_EN.md">English</a>
</p>

---

## 📖 项目简介

**阿洛娜AI** 是一个以游戏《蔚蓝档案》（Blue Archive）中角色"阿洛娜"为原型打造的非交互式桌面AI。在设定上，她是“什亭之匣”的操作系统管理员，性格开朗、热情，乐于帮助老师（用户）解决问题。

本项目集成了Arona语言模型（AronaLM）、非交互式设计、意图驱动、语音合成（TTS）、语音识别（ASR）、Spine 2D 角色动画等技术，旨在提供一个可爱、有趣且功能完整的桌面体验。

<p align="center">
  <img src="assets/running_example_2.png" alt="Running Example" width="600"/>
</p>

<p align="center">
  <em>前端运行截图 - 阿洛娜 & 设置界面</em>
</p>

---

## 🏗️ 项目架构

```
arona-ai/
├── backend/                              # Python 后端（FastAPI + WebSocket）
├── frontend/                             # 桌面客户端（Qt/C++ + Spine）
├── gpt-sovits/                           # GPT-SoVITS 语音合成
├── llm/aronaLM/finetune/                 # AronaLM 微调（其实不是大模型啦……之前写错了还没有改过来呢）
├── models/                               # 本地模型权重（需自行下载）
├── assets/                               # 项目资源
└── start-all.bat                         # Windows 一键本机启动所有服务
```

完整目录树见 [`docs/architecture.md`](docs/architecture.md)。

---

## ✨ 核心功能

### 🤖 AI 对话引擎
- **双模型链路**：**Planner（DeepSeek）→ 意图规划 → Renderer（AronaLM-Renderer-V2.x）**；Planner 关闭或失败时回落本地路径
- **关系气候**：信任 / 依赖 / 张力三标量构建张量；规则分类用户行动后查表更新，气候分区决定开口、姿态或沉默
- **主动行为**：WebSocket 连接后按时段主动问候、提醒，安静若干时间后轻在场；稀疏回访记忆里的未完成计划；Planner 允许时同轮补充
- **AronaLM**：AronaLM-Renderer 负责文字渲染；双模型链路不可用时回落本地单模型 AronaLM-Generator 完成推理全流程
- **记忆与知识分离**：用户长期事实进 SQLite + FTS5 + Chroma；世界观设定进 Markdown 语料 → 本地 BGE + Chroma RAG；互不混写、按需注入 Prompt
- **异步记忆抽取**：对话主路径不阻塞；DeepSeek JSON 抽取（含日配额与缓冲批量），失败或无 Key 时自动正则降级
- **上下文可控**：多轮历史截断 + memory/knowledge/history token budget，阻止上下文膨胀

### 🖥️ 桌面客户端与语音服务
- **Spine 2D 动画**：使用 Spine 实现阿洛娜的 2D 角色动画
- **Qt 界面**：基于 Qt/C++ 的 Windows 桌面应用，经 WebSocket 对接后端
- **语音交互**：通过 GPT-SoVITS 进行语音合成，通过腾讯云 ASR 进行语音识别
- **全局快捷键**：支持自定义快捷键操作

---

## 🚀 快速开始

### 环境要求

| 组件 | 要求 |
|------|------|
| Python | 3.10+ |
| CUDA | 11.8（可选，llama.cpp GPU 层 / 微调训练） |
| 操作系统 | Windows 10/11 (客户端/服务端) / Linux 及其衍生系统 (服务端) |
| 后端依赖 | `backend/requirements.txt` |

### 本地一键启动所有服务

```bash
.\start-all.bat # 或者直接双击打开 start-all.bat 文件
```

| 参数 | 说明 |
|------|------|
| -CondaEnv | 后端使用的 Conda 环境名称，默认为 `shittim-chest` |
| -TimeoutSec | 每个服务的等待超时时间，默认为 `600` 秒 |
| -FrontendExe | 可选的桌面客户端可执行文件路径，如果未提供，则自动检测 |

启动完成后，控制台窗口会保持运行，可依照控制台输出单独停止 / 启动 / 重启某一服务。

> **注意**：如果您还没有配置好所有服务，或希望分主机部署各个服务，请遵循下文的指示进行配置。

### 后端

**1. 放置AronaLM模型文件**

```
models/
├── AronaLM-Renderer-V2.x/        # Renderer GGUF（双模型链路）
│   └── AronaLM-Renderer-V2.x.Q4_K_M.gguf
├── AronaLM-Generator-V2.x/          # 可选：本地单模型 / Planner 回落
│   └── AronaLM-Generator-V2.x.Q4_K_M.gguf
└── bge-small-zh-v1.5/            # 知识 / 记忆嵌入模型（启用 knowledge 或记忆向量检索时需要）
```

> **AronaLM-Renderer-V2.x**：请使用 [xiahy456/AronaLM-Renderer-V2.4](https://www.modelscope.cn/models/xiahy456/AronaLM-Renderer-V2.4)。

> **AronaLM-Generator-V2.x**：可选，见 [xiahy456/AronaLM-Generator-V2.0](https://www.modelscope.cn/models/xiahy456/AronaLM-Generator-V2.0)。仅在关闭 Planner 或需要回落单模型时使用。

**2. 配置 `config.yaml`**

```bash
# 在 backend/ 目录下
copy config.example.yaml config.yaml   # Windows
cp config.example.yaml config.yaml   # Linux / macOS
```

按需填写：
- `model.gguf_path`：默认 `AronaLM-Renderer-V2.4`；仅使用单模型时改为注释中的 Generator 路径
- `planner.enabled` / `planner.api_key`：默认开启双模型；填写 DeepSeek API Key。不填 Key 或关闭 `enabled` 则回落本地单模型
- `memory.extractor.api_key`：DeepSeek API Key（可选；不填则记忆抽取走正则降级）
- `knowledge.enabled`：是否启用世界观 RAG 知识库（默认 `false`，启用前请先灌库，相关指导在 [`backend/README.md`](backend/README.md) 中）

**3. 启动服务**

```bash
conda activate shittim-chest   # 环境配置见 backend README
cd backend
pip install -r requirements.txt
python -m app.main
```

### 客户端

从 [Releases 页面](https://github.com/xiahy456/AronaAI/releases) 下载已打包的客户端。

1. 打开 Releases 页面，下载最新版 **安装包**（`AronaAI_WindowsClient_v*_x64_Setup.exe`）或 **便携 zip**（`AronaAI_WindowsClient_v*_x64.zip`）
2. 安装或解压后，编辑程序目录下的 `Config/config.json`，至少填写以下关键项：

```json
{
  "aronalm": {
    "websocket_url": "ws://your.aronalm.ip:20456/ws" // 你的 AronaLM 后端 WebSocket 地址
  },
  "tts": {
    "host": "your.gpt.sovits.ip" // 你的 GPT-SoVITS 服务地址
  },
  "tencent_speech_recognizer": {
    "secret_id": "${TENCENT_SECRET_ID}", // 腾讯云语音识别 SecretId（可用环境变量占位）
    "secret_key": "${TENCENT_SECRET_KEY}" // 腾讯云语音识别 SecretKey（可用环境变量占位）
  }
}
```

完整字段说明见 [`frontend/AronaAI_Spine_WindowsClient/README.md`](frontend/AronaAI_Spine_WindowsClient/README.md)。从源码构建客户端亦见该文档。

3. 启动客户端，直接运行客户端可执行文件即可。

### 语音合成服务

#### 放置 GPT-SoVITS 模型文件与参考音频

```
gpt-sovits/
├── GPT_weights_v2/            # GPT 模型权重
│   └── ALuoNa_cn-e15.ckpt
├── SoVITS_weights_v2/         # SoVITS 模型权重
│   └── ALuoNa_cn_e16_s256.pth
└── ref_audio/Arona/              # 参考音频
   └── arona_academy_in_2.ogg   # 推荐的参考音频
```

#### 启动 GPT-SoVITS API 服务

```bash
cd gpt-sovits
# Windows: go-apiv2.bat
# Linux:   chmod +x go-apiv2.sh && ./go-apiv2.sh
```

`go-apiv2` 会在推理卡住时自动重启 API。仅调试、不要自动重启时，可直接运行 `python api_v2.py`。

---

## 📚 模块与配置

| 模块 | 文档 |
|------|------|
| **后端** | [`backend/README.md`](backend/README.md) |
| **桌面客户端** | [`frontend/AronaAI_Spine_WindowsClient/README.md`](frontend/AronaAI_Spine_WindowsClient/README.md) |
| **模型** | [`models/README.md`](models/README.md) |
| **AronaLM 微调**（如果您是开发者，请参考该文档） | [`llm/aronaLM/finetune/README.md`](llm/aronaLM/finetune/README.md) |

---

## 🙏 致谢

- **《蔚蓝档案》(ブルーアーカイブ)** - 一切奇迹的起点 (https://bluearchive-cn.com/)
- **Spine** - 2D 动画引擎 (https://esotericsoftware.com/)
- **基沃托斯古书馆** - Spine 动画资源与 Blueaka 字体 (https://kivo.wiki/)
- **Qt** - 跨平台 GUI 框架 (https://www.qt.io/)
- **llama.cpp / llama-cpp-python** - 本地 GGUF 推理 (https://github.com/ggml-org/llama.cpp)
- **Qwen3-1.7B** - 微调训练基底模型 (https://huggingface.co/Qwen/Qwen3-1.7B)
- **Unsloth** - QLoRA 高效微调 (https://unsloth.ai/)
- **ChromaDB** - 向量数据库 (https://www.trychroma.com/products/chromadb)
- **DeepSeek** - Planner 意图规划与记忆抽取 API (https://www.deepseek.com/)
- **GPT-SoVITS** - 语音合成服务 (https://github.com/RVC-Boss/GPT-SoVITS)
- **腾讯云语音识别** - 在线语音识别 (https://cloud.tencent.com/product/asr)
- **bge-small-zh-v1.5** - 文本嵌入模型 (https://huggingface.co/BAAI/bge-small-zh-v1.5)

<p align="center">
  <strong>感谢所有协助开发的贡献者们，与所有「蔚蓝档案」社区内容的创作者们</strong>
</p>
<p align="center">
  <strong>感谢你们为这个社区带来精彩作品与活力</strong>
</p>

---

## ⚖️ 许可证与版权、产权声明

本项目基于 [Apache License 2.0](LICENSE) 开源。

本项目为以《蔚蓝档案》（Blue Archive）角色「阿洛娜」为原型的**非官方同人创作**，与 NEXON、NEXON Games、悠星（Yostar）及其他相关权利方**无从属、合作或授权关系**。游戏中的角色、设定、商标及其他知识产权均归原权利方所有；本项目对其引用不代表已获授权，亦不主张任何相关权利。

[Apache License 2.0](LICENSE) **仅适用于本项目原创的源代码与文档**。本项目**不以营利为目的**；若权利方希望移除相关内容，请通过下方联系方式告知，我们将尽快配合处理。

---

## ⭐ 关于开发者

- **项目发起者**: xia_hy456
- **发起者个人博客**: https://xia-hy456.top/
- **反馈问题**: 2066961858@qq.com

---

<p align="center">
  <sub>/* 就像草莓牛奶一样，甜蜜的奇迹 */</sub>
</p>
