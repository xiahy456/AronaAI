# AronaAI

<p align="center">
  <img src="assets/logo.png" alt="AronaAI Logo" width="200"/>
</p>

<p align="center">
  <strong>A non-interactive desktop AI based on Arona from <em>Blue Archive</em></strong>
</p>

<p align="center">
  The cloud handles planning and extraction; the local model handles persona and the immersive scene. Relationship tensors and proactive events form a rule-based control plane, so you live with Arona rather than chat with her.
</p>

<p align="center">
  <em>Version: 2.4.1</em>
</p>

<p align="center">
  <a href="README.md">中文</a> · <strong>English</strong>
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
├── frontend/                             # Desktop client (Qt/C++ + Spine)
├── gpt-sovits/                           # GPT-SoVITS TTS
├── llm/aronaLM/finetune/                 # AronaLM fine-tune (not actually a large model… I wrote that wrong earlier and still haven't changed it)
├── models/                               # Local model weights (download yourself)
├── assets/                               # Project assets
├── start-all.bat                         # Windows one-click local start for all services
├── pack-client.ps1                       # pack the desktop client
└── pack-backend.ps1                      # pack the Windows portable backend
```

See [`docs/architecture.md`](docs/architecture.md) for the full directory tree.

---

## ✨ Core Features

### 🤖 AI Dialogue Engine
- **Dual-model pipeline**: **Planner (DeepSeek) → intent planning → Renderer (AronaLM-Renderer-V2.x)**; if Planner is disabled or fails, the system falls back to the local path
- **Relationship climate**: three scalars — trust / dependence / tension — form a tensor. User actions are classified by rules, then a lookup table updates the climate; climate zones decide whether Arona speaks, how she holds herself, or stays silent
- **Proactive behavior**: after a WebSocket connect, Arona greets and reminds by time of day; after a stretch of silence she checks in lightly; sparse follow-ups on unfinished plans in memory; when Planner allows it, she may add a line in the same turn
- **AronaLM**: AronaLM-Renderer handles text rendering; when the dual-model pipeline is unavailable, the local single-model AronaLM-Generator takes over the full inference path
- **Memory and knowledge are separate**: long-term user facts go to SQLite + FTS5 + Chroma; world-lore goes Markdown corpus → local BGE + Chroma RAG; they are never mixed, and each is injected into the prompt on demand
- **Intermediate result cache**: world-lore near-synonym retrieval can reuse lore hits; the Renderer reuses a fixed system-prefix KV cache
- **Async memory extraction**: the main dialogue path is not blocked; DeepSeek JSON extraction (with a daily quota and buffered batches) falls back to regex if the call fails or no API key is set
- **Bounded context**: multi-turn history truncation + memory / knowledge / history token budgets keep the context from ballooning

### 🖥️ Desktop Client & Voice Services
- **Spine 2D animation**: Arona character animation via Spine
- **Qt UI**: Windows desktop app in Qt/C++, talking to the backend over WebSocket
- **Voice interaction**: voice synthesis through GPT-SoVITS and voice recognition through Tencent Cloud ASR
- **Global hotkeys**: customizable shortcuts

---

## 🚀 Quick Start

### Backend

Download the packaged portable backend from the [Releases](https://github.com/xiahy456/AronaAI/releases) page. The bundle includes a Python runtime; you do **not** need conda or Python installed on the machine.

1. Open the Releases page and download the latest **portable zip** (`AronaAI_Backend_v*_x64.zip`)

2. After extracting, edit `config.yaml` in the directory and fill in at least these keys:

   - `planner.api_key` / `memory.extractor.api_key`: replace `YOUR_DEEPSEEK_API_KEY` with your DeepSeek API Key (**required**). Without a key, or with `planner.enabled` off, the backend falls back to the local single model; memory extraction without a key uses the regex fallback
   - `model.enabled`: whether to enable Arona-Renderer rendering correction; `true` enables it, `false` disables it (Planner draft only). Place the GGUF only when this is enabled. **Disabled by default**
   - `knowledge.enabled`: whether to enable world-lore RAG. The zip already has the corpus ingested, and this is **enabled by default**

3. Place models under `models/` in the extracted directory as needed (paths are already set in the bundled `config.yaml`; see the bundled `models/README.txt` or [`models/README.md`](models/README.md)):
   - When Renderer is enabled: `models/AronaLM-Renderer-V2.4/AronaLM-Renderer-V2.4.Q4_K_M.gguf`

4. Double-click `AronaAI_Backend.bat` to start. Set the desktop client's `websocket_url` to `ws://127.0.0.1:20456/ws` (this is already the default).

> **System requirements**: Windows 10 / 11 x64. If it fails to start, run the bundled `vc_redist.x64.exe` first. Renderer GPU layers need an NVIDIA GPU and a reasonably recent driver. Do not extract a new version over a directory you are already using (unless you do not need to keep memory); runtime data lives in `data/memory/` and `logs/`.

Full field docs and running from source (conda / `python -m app.main`) are in [`backend/README.md`](backend/README.md).

### Client

Download the packaged client from the [Releases](https://github.com/xiahy456/AronaAI/releases) page.

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
    "secret_id": "${TENCENT_SECRET_ID}", // Tencent Cloud real-time ASR SecretId (env-var placeholders allowed)
    "secret_key": "${TENCENT_SECRET_KEY}",  // Tencent Cloud real-time ASR SecretKey (env-var placeholders allowed)
    "app_id": "${TENCENT_APP_ID}" // Tencent Cloud real-time ASR AppId
  }
}
```

Full field docs: [`frontend/AronaAI_Spine_WindowsClient/README.md`](frontend/AronaAI_Spine_WindowsClient/README.md). Building the client from source is also covered there.

> **Note**: Upload [`docs/hot_word.txt`](docs/hot_word.txt) as a hot-word list in Tencent Cloud ASR and set it as the default hot-word list.

3. Start the client by running the client executable.

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

---

## 📚 Modules & Configuration

| Module | Docs |
|------|------|
| **Backend** | [`backend/README.md`](backend/README.md) |
| **Desktop client** | [`frontend/AronaAI_Spine_WindowsClient/README.md`](frontend/AronaAI_Spine_WindowsClient/README.md) |
| **Models** | [`models/README.md`](models/README.md) |
| **AronaLM fine-tune** (for developers) | [`llm/aronaLM/finetune/README.md`](llm/aronaLM/finetune/README.md) |

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

## ⚖️ License, Copyright & Intellectual Property

This project is licensed under [Apache License 2.0](LICENSE).

This project is an **unofficial fan work** inspired by Arona from *Blue Archive*, and has **no affiliation, partnership, or authorization** with NEXON, NEXON Games, Yostar, or other related rights holders. All characters, settings, trademarks, and other intellectual property in the game remain with the original rights holders; references in this project do not imply a license or any claim of ownership.

[Apache License 2.0](LICENSE) **applies only to this project's original source code and documentation**. This project is **not for commercial profit**. If a rights holder wishes related material removed, please contact us using the details in **[About the Developer](#-about-the-developer)** below; we will cooperate promptly.

---

## ⭐ About the Developer

- **Project lead**: xia_hy456
- **Blog**: https://xia-hy456.top/
- **Feedback**: 2066961858@qq.com

---

<p align="center">
  <sub>/* イチゴミルクのような 甘い甘い奇跡 */</sub>
</p>
