# AronaAI

<p align="center">
  <img src="assets/logo.png" alt="AronaAI Logo" width="200"/>
</p>

<p align="center">
  <strong>A non-interactive desktop AI based on Arona from <em>Blue Archive</em></strong>
</p>

<p align="center">
  <em>The cloud handles planning and extraction; the local model handles persona and the immersive scene. Relationship tensors and proactive events form a rule-based control plane — this is not just another chatting LLM.</em>
</p>

<p align="center">
  <a href="README.md">中文</a> · <strong>English</strong>
</p>

<p align="center">
  <em>Repository: https://github.com/xiahy456/AronaAI</em>
</p>

<p align="center">
  <em>Version: 2.1.0</em>
</p>

---

## 📖 Introduction

**AronaAI** is a non-interactive desktop AI modeled after Arona from the game *Blue Archive*. In lore she is the OS administrator of the Shittim Chest: cheerful, enthusiastic, and always ready to help Sensei (the user).

The project combines AronaLM, a non-interactive design, intent-driven dialogue, text-to-speech (TTS), automatic speech recognition (ASR), and Spine 2D character animation, aiming for a cute, engaging, and complete desktop experience.

<p align="center">
  <img src="assets/running_example_2.png" alt="Running Example" width="600"/>
</p>

<p align="center">
  <em>Desktop client screenshot — Arona & settings UI</em>
</p>

---

## 🏗️ Project Architecture

```
arona-ai/
├── backend/                              # Python backend (FastAPI + WebSocket)
│   ├── app/main.py                       # Service entry
│   ├── config.example.yaml               # Config template
│   └── README.md
├── frontend/                             # Windows desktop client (Qt/C++ + Spine)
│   └── AronaAI_Spine_WindowsClient/
│       ├── AronaAI_Spine_WindowsClient.sln  # Solution entry
│       ├── Config/config.example.json    # Client config template
│       ├── dist/                         # Executables (generated after packing)
│       └── README.md
├── gpt-sovits/                           # GPT-SoVITS TTS
│   ├── go-apiv2.bat                      # Windows start entry
│   └── go-apiv2.sh                       # Linux start entry
├── llm/aronaLM/finetune/                 # AronaLM fine-tune (not actually a "large" model… we wrote that earlier and haven't fixed it yet)
│   ├── start.bat                         # One-click training on Windows
│   └── README.md
├── models/                               # Local model weights (download yourself)
│   └── README.md                         # Download and placement notes
├── docs/
│   └── architecture.md                   # Full directory tree
├── assets/                               # Project assets
├── pack-client.ps1                       # Pack the desktop client
└── start-all.ps1                         # Windows one-click start for all services
```

See [`docs/architecture.md`](docs/architecture.md) for the full directory tree.

---

## ✨ Core Features

### 🤖 AI Dialogue Engine
- **Dual-model pipeline**: **Planner (DeepSeek) → structured intent card → Renderer (AronaLM-Renderer-V2.x)**; simple turns can be routed to the local single model. If Planner is disabled or fails, the system falls back to the local path
- **Relationship climate**: three scalars — trust / dependence / tension — form a tensor. User actions are classified by rules, then a lookup table updates the climate; climate zones decide whether Arona speaks, how she speaks, or stays silent
- **Login greeting, idle chat, care, and follow-up**: after a WebSocket connect, Arona greets by time of day; after a stretch of silence she checks in lightly; she reminds you to eat or rest by time of day; sparse follow-ups on unfinished plans in memory; when Planner allows it, she may add a line in the same turn
- **AronaLM-Renderer-V2.x (GGUF)**: `llama-cpp-python` loads a Qwen3-1.7B fine-tuned GGUF (default Q4_K_M) and strips `<think>` reasoning blocks; the default dual-model path is non-streaming; the local fallback path can stream
- **Memory and knowledge are separate**: long-term user facts go to SQLite + FTS5 + Chroma (jieba / BGE); world-lore goes Markdown corpus → local BGE + Chroma RAG; they are never mixed, and each is injected into the prompt on demand
- **Async memory extraction**: the main dialogue path is not blocked; DeepSeek JSON extraction (with a daily quota and buffered batches) falls back to regex if the call fails or no API key is set
- **ASR dirty-text filter**: empty strings and Tencent Cloud ASR error templates are dropped at the entry point so Planner is not triggered by accident
- **Bounded context**: multi-turn history truncation + memory / knowledge / history token budgets + an exact-match response cache keep latency and repeated inference in check

### 🖥️ Desktop Client & Voice Services
- **Spine 2D animation**: Arona character animation via Spine
- **Qt UI**: Windows desktop app in Qt/C++, talking to the backend over WebSocket
- **Voice interaction**: voice synthesis through GPT-SoVITS and voice recognition through Tencent Cloud ASR
- **Global hotkeys**: customizable shortcuts

---

## 🚀 Quick Start

### Prerequisites

| Component | Requirement |
|------|------|
| Python | 3.10+ |
| CUDA | 11.8 (optional; llama.cpp GPU layers / fine-tuning) |
| OS | Windows 10/11 (client / server) / Linux and derivatives (server) |
| Backend deps | `backend/requirements.txt` |

### Start All Local Services

```bash
.\start-all.ps1
```

| Parameter | Description |
|------|------|
| -CondaEnv | Conda env name for the backend; default `shittim-chest` |
| -TimeoutSec | Wait timeout per service; default `600` seconds |
| -FrontendExe | Optional path to the desktop client executable; auto-detected if omitted |

> **Note**: If you have not configured every service yet, or you want to split services across hosts, follow the sections below first.

After startup the console stays open. You can stop / start / restart a single service by following the console output:

### Backend Setup

**1. Place backend model files**

```
models/
├── AronaLM-Renderer-V2.x/        # Renderer GGUF (dual-model pipeline)
│   └── AronaLM-Renderer-V2.x.Q4_K_M.gguf
├── AronaLM-Generator-V2.x/          # Optional: local single-model / Planner fallback
│   └── AronaLM-Generator-V2.x.Q4_K_M.gguf
└── bge-small-zh-v1.5/            # Embeddings for knowledge / memory (needed when knowledge or vector memory search is on)
```

> **AronaLM-Renderer-V2.x**: use [xiahy456/AronaLM-Renderer-V2.4](https://www.modelscope.cn/models/xiahy456/AronaLM-Renderer-V2.4).

> **AronaLM-Generator-V2.x**: optional; see [xiahy456/AronaLM-Generator-V2.0](https://www.modelscope.cn/models/xiahy456/AronaLM-Generator-V2.0). Needed only when Planner is off or you want the single-model fallback.

**2. Configure `config.yaml`**

```bash
# From backend/
copy config.example.yaml config.yaml   # Windows
cp config.example.yaml config.yaml   # Linux / macOS
```

Fill in as needed:
- `model.gguf_path`: default `AronaLM-Renderer-V2.4`; for single-model only, switch to the Generator path in the comments
- `planner.enabled` / `planner.api_key`: dual-model is on by default; set a DeepSeek API key. With no key or `enabled` off, the backend falls back to the local single model
- `memory.extractor.api_key`: DeepSeek API key (optional; without it, memory extraction uses the regex fallback)
- `knowledge.enabled`: world-lore RAG (default `false`; ingest the corpus before turning this on)

**3. Start the service**

```bash
conda activate shittim-chest   # env setup: see the backend README
cd backend
pip install -r requirements.txt
python -m app.main
```

To enable the knowledge base, set `knowledge.enabled: true` in `config.yaml` and restart the backend. Remember to ingest the corpus first; see [`backend/README.md`](backend/README.md).

### Client (using a Release)

The recommended path is to download a packaged Windows client from GitHub [Releases](https://github.com/xiahy456/AronaAI/releases) — no need to build it yourself.

1. Open the Releases page and download the latest **installer** (`AronaAI_WindowsClient_v*_x64_Setup.exe`) or **portable zip** (`AronaAI_WindowsClient_v*_x64.zip`)
2. After installing or extracting, edit `Config/config.json` in the program directory and fill in at least these keys:

```json
{
  "aronalm": {
    "websocket_url": "ws://your.aronalm.ip:20456/ws" // your AronaLM backend WebSocket URL
  },
  "tts": {
    "host": "your.gpt.sovits.ip" // your GPT-SoVITS host
  },
  "tencent_speech_recognizer": {
    "secret_id": "${TENCENT_SECRET_ID}", // Tencent Cloud ASR SecretId (env-var placeholders allowed)
    "secret_key": "${TENCENT_SECRET_KEY}" // Tencent Cloud ASR SecretKey (env-var placeholders allowed)
  }
}
```

Full field docs: [`frontend/AronaAI_Spine_WindowsClient/README.md`](frontend/AronaAI_Spine_WindowsClient/README.md). Building the client from source is also covered there.

### TTS Service

#### Place GPT-SoVITS model files and reference audio

```
gpt-sovits/
├── GPT_weights_v2/            # GPT weights
│   └── ALuoNa_cn-e15.ckpt
├── SoVITS_weights_v2/         # SoVITS weights
│   └── ALuoNa_cn_e16_s256.pth
└── ref_audio/Arona/              # Reference audio
   └── arona_academy_in_2.ogg   # Recommended reference audio
```

#### Start the GPT-SoVITS API

```bash
cd gpt-sovits
# Windows: go-apiv2.bat
# Linux:   chmod +x go-apiv2.sh && ./go-apiv2.sh
```

`go-apiv2` auto-restarts the API if inference stalls. For debugging without auto-restart, you can run `python api_v2.py` directly.

### Fine-tune (for developers)

See [`llm/aronaLM/finetune/README.md`](llm/aronaLM/finetune/README.md).

---

## 📚 Modules & Configuration

| Module | Docs |
|------|------|
| **Backend** (including `config.yaml`) | [`backend/README.md`](backend/README.md) |
| **Desktop client** (including `config.json`) | [`frontend/AronaAI_Spine_WindowsClient/README.md`](frontend/AronaAI_Spine_WindowsClient/README.md) |
| **Model weights** (`models/`) | [`models/README.md`](models/README.md) |
| **LLM fine-tune** (`llm/aronaLM/finetune`) | [`llm/aronaLM/finetune/README.md`](llm/aronaLM/finetune/README.md) |

---

## 📄 License

This project is licensed under [Apache License 2.0](LICENSE).

---

## 🙏 Acknowledgements

- **Blue Archive (ブルーアーカイブ)** — where all miracles begin (https://bluearchive-cn.com/)
- **Spine** — 2D animation engine (https://esotericsoftware.com/)
- **Kivo Wiki** — Spine animation assets and Blueaka font (https://kivo.wiki/)
- **Qt** — cross-platform GUI framework (https://www.qt.io/)
- **llama.cpp / llama-cpp-python** — local GGUF inference (https://github.com/ggml-org/llama.cpp)
- **Qwen3-1.7B** — fine-tune base model (https://huggingface.co/Qwen/Qwen3-1.7B)
- **Unsloth** — efficient QLoRA fine-tuning (https://unsloth.ai/)
- **ChromaDB** — vector database (https://www.trychroma.com/products/chromadb)
- **DeepSeek** — Planner intent planning and memory extraction API (https://www.deepseek.com/)
- **GPT-SoVITS** — speech synthesis (https://github.com/RVC-Boss/GPT-SoVITS)
- **Tencent Cloud ASR** — online speech recognition (https://cloud.tencent.com/product/asr)
- **bge-small-zh-v1.5** — text embedding model (https://huggingface.co/BAAI/bge-small-zh-v1.5)

<p align="center">
  <strong>Thanks to everyone who helped with development, and to all the creators in the Blue Archive community</strong>
</p>
<p align="center">
  <strong>Thank you for the amazing works and energy you bring to this community</strong>
</p>

---

## ⚖️ Copyright & Intellectual Property

This project is an **unofficial fan work** inspired by Arona from *Blue Archive*, and has **no affiliation, partnership, or authorization** with NEXON, NEXON Games, Yostar, or other related rights holders. All characters, settings, trademarks, and other intellectual property in the game remain with the original rights holders; references in this project do not imply a license or any claim of ownership.

[Apache License 2.0](LICENSE) **applies only to this project's original source code and documentation**. This project is **not for commercial profit**. If a rights holder wishes related material removed, please contact us using the details below; we will cooperate promptly.

---

## ⭐ About the Developer

- **Project lead**: xia_hy456
- **Blog**: https://xia-hy456.top/
- **Feedback**: 2066961858@qq.com

---

<p align="center">
  <sub>/* イチゴミルクのような 甘い甘い奇跡 */</sub>
</p>
