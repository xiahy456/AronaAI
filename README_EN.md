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
  Repository: https://github.com/xiahy456/AronaAI
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
├── backend/                    # Python backend (FastAPI + WebSocket)
│   ├── app/                    # Application core
│   │   ├── main.py             # Service entry
│   │   ├── orchestrator.py     # Dialogue orchestration (relationship → retrieval → Planner/local → generation → memory extraction)
│   │   ├── model_loader.py     # GGUF loading (llama-cpp-python)
│   │   ├── planner/            # Dual-model Planner (DeepSeek intent card → Renderer)
│   │   ├── proactive/          # Proactive events (login greeting, idle chat, time-of-day care, goal follow-up, festivals)
│   │   ├── relationship/       # Relationship climate (trust / dependence / tension, decisions)
│   │   ├── knowledge.py        # World-lore knowledge RAG
│   │   ├── conversation.py     # Multi-turn conversation history
│   │   ├── cache.py            # Response cache
│   │   ├── prompt.py           # Prompt / Renderer message assembly
│   │   ├── input_filter.py     # ASR dirty-text filter (entry-point fallback)
│   │   ├── embeddings.py       # Local BGE embeddings (shared by memory and knowledge)
│   │   ├── protocol.py         # WebSocket protocol messages
│   │   ├── ws_handler.py       # WebSocket handler
│   │   ├── config.py           # Config loading
│   │   ├── logging_utils.py    # Logging helpers
│   │   └── memory/             # Long-term memory (SQLite + FTS5 + Chroma + DeepSeek extraction)
│   ├── scripts/                # Integration / ingest / test scripts
│   ├── data/                   # Memory store, knowledge corpus, and vector DBs
│   │   ├── memory/             # memory.db + chroma + relationship.json + proactive.json
│   │   └── knowledge/          # corpus + chroma
│   ├── logs/                   # Backend runtime logs
│   ├── config.example.yaml     # Config template
│   └── requirements.txt
│
├── frontend/                   # Desktop client
│   └── AronaAI_Spine_WindowsClient/  # Windows desktop client (Qt/C++)
│       ├── QtMainFile/         # Main UI, controllers, WebSocket
│       ├── QtUtils/            # Utilities (recording, ASR, animation, etc.)
│       ├── QHotkey/            # Global hotkey support
│       ├── spine-cpp/          # Spine 2D animation runtime
│       ├── Assets/             # Assets (Spine animations, UI images, fonts)
│       ├── Config/             # Config (resource paths are relative)
│       ├── dist/               # Built executables
│       │   └── AronaAI_Client/  # Client build (secrets left in place)
│       │   └── AronaAI_Client_Release/  # Release build (secrets stripped)
│       └── Dict/               # Dictionary files
│
├── llm/                        # Language model (not really an “LLM” — the folder name stuck from day one)
│   └── aronaLM/
│       └── finetune/           # Qwen3-1.7B QLoRA fine-tune (Unsloth)
│           ├── config/         # Train / export / inference configs
│           ├── training/       # Fine-tune entry scripts
│           ├── inference/      # Interactive inference tests
│           ├── export/         # GGUF export
│           ├── data-process/   # Data preprocessing
│           └── start.bat       # One-click training on Windows
│
├── gpt-sovits/                 # GPT-SoVITS TTS (deploy yourself, or use an external service)
│   ├── GPT_SoVITS/             # Core models
│   ├── GPT_weights_v2/         # GPT weights
│   │   └── ALuoNa_cn-e15.ckpt  # Arona GPT checkpoint
│   ├── SoVITS_weights_v2/      # SoVITS weights
│   │   └── ALuoNa_cn_e16_s256.pth    # Arona SoVITS checkpoint
│   ├── api_v2.py               # API server
│   ├── watch-apiv2.ps1         # Windows: auto-restart on stall / crash
│   ├── watch-apiv2.sh          # Linux: auto-restart on stall / crash
│   ├── go-apiv2.bat            # Windows one-click API start (via watchdog)
│   ├── go-apiv2.sh             # Linux one-click API start (via watchdog)
│   └── ref_audio/              # Reference audio
│       └── Arona/              # Arona reference clips
│            └── arona_academy_in_2.ogg   # Recommended reference audio
│
├── docs/                       # Documentation
├── models/                     # Model files
│   ├── AronaLM-Renderer-V2.1/  # Renderer GGUF (default dual-model path)
│   ├── AronaLM-Generator-V2.0/    # AronaLM GGUF (fallback / local single-model)
│   ├── bge-small-zh-v1.5/      # Embeddings for knowledge / memory
│   └── Qwen3-1.7B-unsloth-bnb-4bit/  # Fine-tune base (training only)
└── assets/                     # Project assets
```

---

## Core Features

### AI Dialogue Engine

- **Dual-model pipeline**: **Planner (DeepSeek) → structured intent card → Renderer (AronaLM-Renderer-V2.2)**. Simple turns can be routed to the local single model. If Planner is disabled or fails, the system falls back to the local path.
- **Relationship climate**: three scalars — trust / dependence / tension — form a tensor. User actions are classified by rules, then a lookup table updates the climate; climate zones decide whether Arona speaks, how she speaks, or stays silent.
- **Login greeting**: after a WebSocket connect, Arona greets by time of day. The first “good morning” (and similar) in a slot is used once; later logins become “welcome back”. Late night / early morning she reminds you to rest. On a festival, the first login that day is a holiday greeting (late at night, the rest reminder is appended).
- **Idle chat, care, and follow-up**: after a stretch of silence she checks in lightly (with a cooldown between two idle lines; no small talk during rest hours). She reminds you to eat or sleep by time of day. Sparse follow-ups on unfinished plans in memory (Sensei saying “don’t bring that up” starts a cooldown). When Planner allows it, at most one extra line in the same turn. Relationship policy is checked before she speaks.
- **AronaLM-Renderer-V2.2 (GGUF)**: `llama-cpp-python` loads a Qwen3-1.7B fine-tuned GGUF (default Q4_K_M) and strips `<think>` reasoning blocks. The default dual-model path is non-streaming; the local fallback path can stream.
- **Memory and knowledge are separate**: long-term user facts go to SQLite + FTS5 + Chroma (jieba / BGE). World-lore goes Markdown corpus → local BGE + Chroma RAG. They are never mixed; each is injected into the prompt on demand.
- **Async memory extraction**: the main dialogue path is not blocked. DeepSeek JSON extraction (with a daily quota and buffered batches) falls back to regex if the call fails or no API key is set.
- **ASR dirty-text filter**: empty strings and Tencent Cloud ASR error templates are dropped at the entry point so Planner is not triggered by accident.
- **Bounded context**: multi-turn history truncation, memory / knowledge / history token budgets, and an exact-match response cache keep latency and repeated inference in check.
- **Full fine-tune pipeline**: Unsloth QLoRA (aimed at ~6–8 GB VRAM) → LoRA adapter → merged GGUF, ready for the backend to load.

### Voice Interaction

- **Text-to-speech (TTS)**: high-quality speech via GPT-SoVITS, matching Arona’s voice.
- **Speech recognition (ASR)**: online ASR via Tencent Cloud SentenceRecognition.

### Desktop Client

- **Spine 2D animation**: Live2D-style Arona character animation via Spine.
- **Qt UI**: Windows desktop app in Qt/C++, talking to the backend over WebSocket, with GPT-SoVITS TTS and Tencent Cloud ASR.
- **WebSocket**: real-time communication with the backend, including streaming output.
- **Global hotkeys**: customizable shortcuts.
- **System tray**: minimize and keep running in the tray.

---

## Quick Start

### Prerequisites

| Component | Requirement |
|-----------|-------------|
| Python | 3.10+ |
| CUDA | 11.8 (optional; llama.cpp GPU layers / fine-tuning) |
| OS | Windows 10/11 (client) / Linux and derivatives (server) |
| Backend deps | `backend/requirements.txt` |
| Fine-tune deps | `llm/aronaLM/finetune/requirements.txt` (training only) |

### Start All Services

```bash
.\start-all.ps1
```

| Parameter | Description |
|-----------|-------------|
| `-CondaEnv` | Conda env name for the backend; default `shittim-chest` |
| `-TimeoutSec` | Wait timeout per service; default `600` seconds |
| `-FrontendExe` | Optional path to the desktop client executable; auto-detected if omitted |
| `-TtsStallSec` | Seconds of stall before GPT-SoVITS is considered hung (passed to the watchdog); default `60` |
| `-TtsRestartCooldownSec` | Cooldown between GPT-SoVITS auto-restarts; default `90` |

> **Note**: If you have not configured every service yet, follow the sections below first.

After startup the console stays open. You can stop / start / restart a single service:

```text
status                         Show status
stop backend|gpt|frontend      Stop one service
start backend|gpt|frontend     Start a stopped service
restart backend|gpt|frontend   Restart one service
stop all  /  0  /  q  /  exit  Stop everything and quit
```

Number shortcuts: `1/2/3` restart backend / GPT-SoVITS / frontend; `4/5/6` stop the matching service. `Ctrl+C` also stops every tracked process.

> `start-all.ps1` starts TTS through `gpt-sovits/watch-apiv2.ps1` (including auto-restart on stall). If GPT-SoVITS runs on **another machine**, start `go-apiv2.bat` / `go-apiv2.sh` there; you do not need `start-all` on that host.

### Backend Setup

#### Before You Start

**1. Place backend model files**

```
models/
├── AronaLM-Renderer-V2.1/        # Renderer GGUF (dual-model pipeline)
│   └── AronaLM-Renderer-V2.1.Q4_K_M.gguf
├── AronaLM-Generator-V2.0/          # Optional: local single-model / Planner fallback
│   └── AronaLM-Generator-V2.0.Q4_K_M.gguf
└── bge-small-zh-v1.5/            # Embeddings for knowledge / memory (needed when knowledge or vector memory search is on)
```

> **AronaLM-Renderer-V2.1**: use [xiahy456/AronaLM-Renderer-V2.1](https://www.modelscope.cn/models/xiahy456/AronaLM-Renderer-V2.1).

> **AronaLM-Generator-V2.0**: optional; see [xiahy456/AronaLM-Generator-V2.0](https://www.modelscope.cn/models/xiahy456/AronaLM-Generator-V2.1). Needed only when Planner is off or you want the single-model fallback.

**2. Configure `config.yaml`**

```bash
# From backend/
copy config.example.yaml config.yaml   # Windows
cp config.example.yaml config.yaml   # Linux / macOS
```

Fill in as needed:

- `model.gguf_path`: default `AronaLM-Renderer-V2.1`; for single-model only, switch to the v2.0 path in the comments
- `planner.enabled` / `planner.api_key`: dual-model is on by default; set a DeepSeek API key. With no key or `enabled: false`, the backend falls back to the local single model
- `memory.extractor.api_key`: DeepSeek API key (optional; without it, memory extraction uses the regex fallback)
- `knowledge.enabled`: world-lore RAG (default `false`; ingest the corpus before turning this on)
- `proactive.welcome.enabled` / `proactive.relationship.enabled`: login greeting and relationship climate (on by default; climate state lives in `data/memory/relationship.json`)
- `proactive.idle` / `proactive.care` / `proactive.goal` / `proactive.festival` / `proactive.continue`: idle chat, lunch/sleep care, goal follow-up, festival greetings, and same-turn extra lines (scheduler state lives in `data/memory/proactive.json`)

> **Note**: `config.yaml` is in `.gitignore` and will not be committed.

**3. Start the service**

The working directory must be `backend/`:

```bash
conda activate shittim-chest   # env setup: see the backend README
cd backend
pip install -r requirements.txt

python -m app.main
# or
uvicorn app.main:app --host 127.0.0.1 --port 20456
```

Default WebSocket: `ws://127.0.0.1:20456/ws` (same as the Qt client).

Health check: `GET http://127.0.0.1:20456/health`

**4. (Optional) Integration tests and knowledge base**

```bash
# WebSocket smoke test (service must already be running)
python scripts/smoke_ws.py

# Relationship climate / login greeting unit tests (no GGUF load)
python scripts/test_relationship_unit.py
python scripts/test_welcome_unit.py
python scripts/test_proactive_unit.py

# Write corpus per data/knowledge/WRITING.md, then ingest
python scripts/ingest_knowledge.py

# After large title/structure changes:
python scripts/ingest_knowledge.py --rebuild

# Retrieval smoke test
python scripts/test_knowledge_rag.py
```

To enable the knowledge base, set `knowledge.enabled: true` in `config.yaml` and restart the backend.

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
    "host": "your.gpt.sovits.ip" // GPT-SoVITS host
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
> - `pack_keep_secrects.ps1` (portable pack) rewrites relative paths to match the package layout and **keeps** Tencent Cloud SecretId / SecretKey.
> - `pack_sanitize_secrets.ps1` (portable pack) rewrites relative paths to match the package layout and **strips** Tencent Cloud SecretId / SecretKey.
> - This project uses **Tencent Cloud ASR**. SecretId and SecretKey are available under API key management in the Tencent Cloud console.

> **Note**: `config.json` is in `.gitignore` and will not be committed.

### TTS Service

#### Place GPT-SoVITS model files

```
models/
├── GPT_weights_v2/            # GPT weights
│   └── ALuoNa_cn-e15.ckpt
└── SoVITS_weights_v2/         # SoVITS weights
│   └── ALuoNa_cn_e16_s256.pth
```

#### Place reference audio

```
gpt-sovits/ref_audio/Arona/arona_academy_in_2.ogg
```

#### Start the GPT-SoVITS API

```bash
# On the machine that hosts GPT-SoVITS (recommended: watchdog with stall auto-restart)
cd gpt-sovits
# Windows: go-apiv2.bat
# Linux:   chmod +x go-apiv2.sh && ./go-apiv2.sh
```

`go-apiv2` calls `watch-apiv2`: if inference logs sit on “extracting text Bert features” or “predicting semantic tokens” for too long, the process is killed and the API is restarted.

Optional parameters (PowerShell):

```powershell
.\watch-apiv2.ps1 -StallSec 60 -RestartCooldownSec 90 -LogPath D:\logs\gpt-sovits.log
```

Linux:

```bash
./watch-apiv2.sh --stall-sec 60 --restart-cooldown 90 --log-path /var/log/gpt-sovits.log
```

**Split-host deploy**: when TTS and the client are on different machines — run `go-apiv2` on the TTS host; in the client `config.json` set `tts.host` to the TTS machine IP and set `request_timeout_ms` (recommended `45000`). Client timeout only keeps the UI from blocking; **auto-restart must run on the TTS host via the watchdog**.

> For debugging without auto-restart, you can still run `python api_v2.py` (or `runtime\python.exe -X utf8 -I api_v2.py`).

### Fine-tune (optional)

To fine-tune an Arona-style model yourself, use `llm/aronaLM/finetune` (Unsloth QLoRA on Qwen3-1.7B, aimed at ~6–8 GB VRAM):

```bat
cd llm\aronaLM\finetune
python -m venv .venv
.venv\Scripts\activate
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
pip install -r requirements.txt

REM After placing the base model at models/Qwen3-1.7B-unsloth-bnb-4bit:
start.bat
```

After training you can export a GGUF for `model.gguf_path` on the backend. Details: [`llm/aronaLM/finetune/README.md`](llm/aronaLM/finetune/README.md).

---

## Modules & Configuration

Module docs, protocols, and config live in the matching READMEs:

| Module | Docs |
|--------|------|
| **Backend** (including `config.yaml`) | [`backend/README.md`](backend/README.md) |
| **Desktop client** (including `config.json`) | [`frontend/AronaAI_Spine_WindowsClient/README.md`](frontend/AronaAI_Spine_WindowsClient/README.md) |
| **LLM fine-tune** (`llm/aronaLM/finetune`) | [`llm/aronaLM/finetune/README.md`](llm/aronaLM/finetune/README.md) |

---

## License

This project is licensed under Apache License 2.0.

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
