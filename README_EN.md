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
  <em>Version: 2.0.0</em>
</p>

---

## Introduction

**AronaAI** is a non-interactive desktop AI modeled after Arona from the game *Blue Archive*. In lore she is the OS administrator of the Shittim Chest: cheerful, enthusiastic, and always ready to help Sensei (the user).

The project combines AronaLM, a non-interactive design, intent-driven dialogue, text-to-speech (TTS), automatic speech recognition (ASR), and Spine 2D character animation, aiming for a cute, engaging, and complete desktop experience.

<p align="center">
  <img src="assets/running_example_2.png" alt="Running Example" width="600"/>
</p>

<p align="center">
  <em>Desktop client screenshot — Arona & Setting Widget</em>
</p>

---

## Project Architecture

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
├── llm/                                  # AronaLM fine-tune
│   └── aronaLM/finetune/
│       ├── start.bat                     # One-click training on Windows
│       └── README.md
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

## Core Features

### AI Dialogue Engine

- **Dual-model pipeline**: **Planner (DeepSeek) → structured intent card → Renderer (AronaLM-Renderer-V2.2)**. Simple turns can be routed to the local single model. If Planner is disabled or fails, the system falls back to the local path.
- **Relationship climate**: three scalars — trust / dependence / tension — form a tensor. User actions are classified by rules, then a lookup table updates the climate; climate zones decide whether Arona speaks, how she speaks, or stays silent.
- **Login greeting, idle chat, care, and follow-up**: after a WebSocket connect, Arona greets by time of day; after a stretch of silence she checks in lightly; she reminds you to eat or rest by time of day; sparse follow-ups on unfinished plans in memory; when Planner allows it, she may add a line in the same turn.
- **AronaLM-Renderer-V2.2 (GGUF)**: `llama-cpp-python` loads a Qwen3-1.7B fine-tuned GGUF (default Q4_K_M) and strips `<think>` reasoning blocks. The default dual-model path is non-streaming; the local fallback path can stream.
- **Memory and knowledge are separate**: long-term user facts go to SQLite + FTS5 + Chroma (jieba / BGE). World-lore goes Markdown corpus → local BGE + Chroma RAG. They are never mixed; each is injected into the prompt on demand.
- **Async memory extraction**: the main dialogue path is not blocked. DeepSeek JSON extraction (with a daily quota and buffered batches) falls back to regex if the call fails or no API key is set.
- **ASR dirty-text filter**: empty strings and Tencent Cloud ASR error templates are dropped at the entry point so Planner is not triggered by accident.
- **Bounded context**: multi-turn history truncation, memory / knowledge / history token budgets, and an exact-match response cache keep latency and repeated inference in check.
- **Full fine-tune pipeline**: Unsloth QLoRA (aimed at ~6–8 GB VRAM) → LoRA adapter → merged GGUF, ready for the backend to load.

### Desktop Client & Voice Services

- **Spine 2D animation**: Arona character animation via Spine.
- **Qt UI**: Windows desktop app in Qt/C++, talking to the backend over WebSocket, with GPT-SoVITS TTS and Tencent Cloud ASR.
- **Global hotkeys**: customizable shortcuts.

---

## Quick Start

### Prerequisites

| Component | Requirement |
|-----------|-------------|
| Python | 3.10+ |
| CUDA | 11.8 (optional; llama.cpp GPU layers / fine-tuning) |
| OS | Windows 10/11 (client / server) / Linux and derivatives (server) |
| Backend deps | `backend/requirements.txt` |

### Start All Local Services

```bash
.\start-all.ps1
```

| Parameter | Description |
|-----------|-------------|
| `-CondaEnv` | Conda env name for the backend; default `shittim-chest` |
| `-TimeoutSec` | Wait timeout per service; default `600` seconds |
| `-FrontendExe` | Optional path to the desktop client executable; auto-detected if omitted |

> **Note**: If you have not configured every service yet, or you want to split services across hosts, follow the sections below first.

After startup the console stays open. You can stop / start / restart a single service:

```text
status                         Show status
stop backend|gpt|frontend      Stop one service
start backend|gpt|frontend     Start a stopped service
restart backend|gpt|frontend   Restart one service
stop all  /  0  /  q  /  exit  Stop everything and quit
```

Number shortcuts: `1/2/3` restart backend / GPT-SoVITS / frontend; `4/5/6` stop the matching service. `Ctrl+C` also stops every tracked process.

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

> **AronaLM-Renderer-V2.x**: use [xiahy456/AronaLM-Renderer-V2.2](https://www.modelscope.cn/models/xiahy456/AronaLM-Renderer-V2.2).

> **AronaLM-Generator-V2.x**: optional; see [xiahy456/AronaLM-Generator-V2.0](https://www.modelscope.cn/models/xiahy456/AronaLM-Generator-V2.0). Needed only when Planner is off or you want the single-model fallback.

**2. Configure `config.yaml`**

```bash
# From backend/
copy config.example.yaml config.yaml   # Windows
cp config.example.yaml config.yaml   # Linux / macOS
```

Fill in as needed:

- `model.gguf_path`: default `AronaLM-Renderer-V2.2`; for single-model only, switch to the Generator path in the comments
- `planner.enabled` / `planner.api_key`: dual-model is on by default; set a DeepSeek API key. With no key or `enabled: false`, the backend falls back to the local single model
- `memory.extractor.api_key`: DeepSeek API key (optional; without it, memory extraction uses the regex fallback)
- `knowledge.enabled`: world-lore RAG (default `false`; ingest the corpus before turning this on)
- `proactive.welcome.enabled` / `proactive.relationship.enabled`: login greeting and relationship climate (on by default; climate state lives in `data/memory/relationship.json`)
- `proactive.idle` / `proactive.care` / `proactive.goal` / `proactive.festival` / `proactive.continue`: idle chat, lunch/sleep care, goal follow-up, festival greetings, and same-turn extra lines (scheduler state lives in `data/memory/proactive.json`)

> **Note**: `config.yaml` is in `.gitignore` and will not be committed.

**3. Start the service**

```bash
conda activate shittim-chest   # env setup: see the backend README
cd backend
pip install -r requirements.txt
python -m app.main
```

Default WebSocket: `ws://127.0.0.1:20456/ws` (same as the Qt client).

Health check: `GET http://127.0.0.1:20456/health`

To enable the knowledge base, set `knowledge.enabled: true` in `config.yaml` and restart the backend. Remember to ingest the corpus first; see [`backend/README.md`](backend/README.md).

### Client Build

The Windows client is built with Visual Studio 2026 and Qt:

1. Install [Qt 6.x](https://www.qt.io/download) (6.5.3 recommended) and [Visual Studio 2026](https://visualstudio.microsoft.com/), then install the `Qt VS Tools` extension in VS 2026.
2. Make sure the v143 (Visual Studio 2022) platform toolset is installed; this project requires it.
3. Make sure you have Qt 6.5.3 `msvc2019_64`; this project requires that Qt build (Qt Version can be set in `Qt VS Tools` settings).
4. Open `frontend/AronaAI_Spine_WindowsClient/AronaAI_Spine_WindowsClient.sln`.
5. Configure the Qt version and build options.
6. Build and run.

#### Before You Start

Complete the following before launching the client.

**Configure `config.json`**

Copy `frontend/AronaAI_Spine_WindowsClient/Config/config.example.json` and rename it, then fill in at least these keys:

```bash
cp frontend/AronaAI_Spine_WindowsClient/Config/config.example.json frontend/AronaAI_Spine_WindowsClient/Config/config.json
```

```json
{
  "aronalm": {
    "websocket_url": "ws://your.aronalm.ip:20456/ws" // AronaLM backend WebSocket URL
  },
  "tts": {
    "host": "your.gpt.sovits.ip", // GPT-SoVITS host
  },
  "tencent_speech_recognizer": {
    "secret_id": "${TENCENT_SECRET_ID}", // Tencent Cloud ASR SecretId (env-var placeholders allowed)
    "secret_key": "${TENCENT_SECRET_KEY}" // Tencent Cloud ASR SecretKey (env-var placeholders allowed)
  }
}
```

Full field docs: [`frontend/AronaAI_Spine_WindowsClient/README.md`](frontend/AronaAI_Spine_WindowsClient/README.md).

> **Notes**:
> - Resource paths are resolved relative to the **process working directory**. When debugging in Visual Studio that is the project root by default — do not double-click the exe under `x64/Debug` or `x64/Release` (the working directory will be wrong).
> - Set AronaLM backend and GPT-SoVITS host/port to match your deployment.
> - Changing `tts.request_timeout_ms` in config takes effect immediately (including dist clients). Changes to `TTSManager` / `MainController` source need a client rebuild for timeout and subtitle fallback logic.
> - Packing with the root `pack-client.ps1` rewrites relative paths to match the package layout and outputs two copies: one that keeps Tencent Cloud SecretId / SecretKey, and one that strips them.
> - This project uses **Tencent Cloud ASR**. SecretId and SecretKey are available under API key management in the Tencent Cloud console.

> **Note**: `config.json` is in `.gitignore` and will not be committed.

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

`go-apiv2` auto-restarts the API if inference stalls. For split-host deploy, run the commands above on the TTS machine and set `tts.host` in the client `config.json` to that machine's IP.

> For debugging without auto-restart, you can run `python api_v2.py` directly.

### Fine-tune (optional)

See [`llm/aronaLM/finetune/README.md`](llm/aronaLM/finetune/README.md).

---

## Modules & Configuration

| Module | Docs |
|--------|------|
| **Backend** (including `config.yaml`) | [`backend/README.md`](backend/README.md) |
| **Desktop client** (including `config.json`) | [`frontend/AronaAI_Spine_WindowsClient/README.md`](frontend/AronaAI_Spine_WindowsClient/README.md) |
| **Model weights** (`models/`) | [`models/README.md`](models/README.md) |
| **LLM fine-tune** (`llm/aronaLM/finetune`) | [`llm/aronaLM/finetune/README.md`](llm/aronaLM/finetune/README.md) |

---

## License

This project is licensed under [Apache License 2.0](LICENSE).

---

## Acknowledgements

- **Blue Archive** — where all miracles begin (https://bluearchive-cn.com/)
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
- **Thanks to everyone who helped with development**

---

## About the Developer

- **Project lead**: xia_hy456
- **Blog**: https://xia-hy456.top/
- **Feedback**: 2066961858@qq.com

---

<p align="center">
  <sub>/* イチゴミルクのような 甘い甘い奇跡 */</sub>
</p>
