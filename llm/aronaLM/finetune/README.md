# Qwen3-1.7B QLoRA 微调（阿洛娜）

基于 [Unsloth](https://github.com/unslothai/unsloth) 对本地 `Qwen3-1.7B-unsloth-bnb-4bit` 做 QLoRA 微调，训练数据为 ShareGPT 格式 JSONL，训练结束后导出 LoRA / GGUF，供后端 `llama-cpp-python` 或 Ollama 使用。

面向硬件：**RTX 4060 笔记本（约 6–8GB 显存）**。

本目录支持两条产物线（**勿互相覆盖输出目录**）：

| 产物 | 配置 | 用途 |
|------|------|------|
| **AronaLM-Generator-V2.0** | `config/config.yaml` | 自由对话 / Planner 关闭或失败时的本地回落 |
| **AronaLM-Renderer-V2.1** | `config/config_renderer.yaml` | 双模型主路径：按 Planner **意图卡**渲染 1–2 句短回复 |

后端默认加载 Renderer GGUF，见仓库 [`models/README.md`](../../../models/README.md)。

---

## 项目结构

```
finetune/
├── config/
│   ├── config.yaml              # AronaLM-Generator-V2.0：模型 / 数据 / LoRA / 训练 / 导出 / 推理
│   └── config_renderer.yaml     # AronaLM-Renderer-V2.1（勿覆盖 v2.0 产物目录）
├── training/
│   └── train.py                 # 微调主脚本
├── inference/
│   └── inference.py             # LoRA 交互式推理
├── export/
│   ├── export_gguf.py           # 16bit 基座 + LoRA → GGUF（4bit 训练后推荐走此脚本）
│   └── deploy_renderer_v21.py   # 将 Renderer GGUF 拷到 models/AronaLM-Renderer-V2.1/
├── eval/
│   ├── eval.py                  # Normal：基座 vs LoRA 完整评测
│   ├── eval_renderer.py         # Renderer：意图卡硬例规则评测（GGUF）
│   ├── cases.json / multi_sessions.json / renderer_cases.json
│   └── ...
├── data-process/                # 语料构建与合并
├── data/
│   ├── raw/normal/chosen/       # 选用语料 JSON（persona + renderer）
│   ├── raw/normal/disabled/     # 禁用语料（不参与合并）
│   └── finetune_training/       # 合并后的 JSONL
├── prompts/
│   └── renderer_system.txt      # Renderer 系统提示（与生产对齐）
├── outputs/                     # 训练产物（自动创建）
├── logs/                        # 训练 / 导出日志（自动创建）
├── requirements.txt
├── start.bat                    # Windows：AronaLM-Generator-V2.0 一键训练
├── start_renderer.bat           # Windows：AronaLM-Renderer-V2.1 训练 → GGUF → 部署
└── README.md
```

本地模型默认路径（相对本目录，即仓库根 `models/`）：

| 用途 | 路径 |
|------|------|
| 训练 4bit 基座 | `../../../models/Qwen3-1.7B-unsloth-bnb-4bit` |
| 导出 GGUF 用 16bit 基座 | `../../../models/Qwen3-1.7B`（勿用 `*-bnb-4bit`） |

---

## 环境安装

### 1. 创建虚拟环境（推荐）

在 `finetune/` 目录下：

```bat
python -m venv .venv
.venv\Scripts\activate
```

### 2. 安装 PyTorch（CUDA）

请到 [PyTorch 官网](https://pytorch.org/get-started/locally/) 按本机 CUDA 版本安装，例如 CUDA 12.4：

```bat
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
```

### 3. 安装本项目依赖

```bat
pip install -r requirements.txt
```

若 `unsloth` 安装失败（Windows 较常见），可先试：

```bat
pip install --upgrade pip
pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"
pip install --no-deps trl peft accelerate bitsandbytes
```

确认 GPU 可用：

```bat
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

---

## 数据准备

训练数据需为 **JSONL**，每行一个样本，ShareGPT 多轮对话格式：

```json
{"conversations": [{"from": "human", "value": "阿洛娜，帮我整理一下桌面上的文件。"}, {"from": "gpt", "value": "好的老师！我马上把文件按类型归档好～"}]}
```

- 字段名：`conversations`
- 消息字段：`from`（`human` / `gpt`，可选 `system`）、`value`
- 支持多轮：`human` / `gpt` 交替出现
- **Renderer** 样本的 `human` 侧为「老师原话 + 意图卡」文本；格式由 `data-process/renderer_format.py` 生成，系统提示见 `prompts/renderer_system.txt`

训练启动时会自动校验格式，并打印：总条数、角色计数、轮次分布、字符长度统计。

### 当前默认 JSONL

| 文件 | 约条数 | 用途 |
|------|--------|------|
| `data/finetune_training/normal_finetune.jsonl` | ~500 | AronaLM-Generator-V2.0（`config.yaml`） |
| `data/finetune_training/mixed_renderer_finetune.jsonl` | ~476 | AronaLM-Renderer-V2.1（`config_renderer.yaml`，renderer + 少量 persona） |
| `data/finetune_training/renderer_finetune.jsonl` | ~326 | 仅 Renderer 样本（合并脚本副产物） |

### 重新合并

**Normal**（从 `data/raw/normal/chosen/*.json`，自动跳过 renderer 专用文件）：

```bat
python data-process\merge_expand_to_jsonl.py
```

**Renderer**（`renderer_curated` + `renderer_synth_v2` 等，并可混入 persona）：

```bat
python data-process\merge_renderer_finetune.py
python data-process\merge_renderer_finetune.py --persona-max 150
```

### Renderer 语料构建（可选）

| 脚本 | 说明 |
|------|------|
| `build_renderer_curated.py` | 手写金标 → `chosen/renderer_curated.json` |
| `build_renderer_synth_v2.py` | 模板 / LLM 合成（禁止虚卡 `must_say`）→ `chosen/renderer_synth_v2.json` |
| `build_renderer_pairs.py` | **已废弃**；弱虚卡不得进入 `chosen/` |

`data/raw/normal/disabled/` 中的文件不参与任何合并。

---

## 训练启动

### A. AronaLM-Generator-V2.0（自由对话）

```bat
cd llm\aronaLM\finetune
start.bat
```

附加参数会原样传给 `train.py`，例如：

```bat
start.bat --no-gguf
start.bat --resume
start.bat --epochs 2
```

或直接：

```bat
python training\train.py --config config\config.yaml
```

默认日志：`logs/train.log`。配置中 `export.save_gguf: true` 时，训练结束会尝试导出 GGUF；若因 4bit 基座失败，请改用下方 `export/export_gguf.py`。

### B. AronaLM-Renderer-V2.1（意图卡 → 短回复，推荐主路径）

```bat
cd llm\aronaLM\finetune
start_renderer.bat
```

流程：`train.py --config config_renderer.yaml --no-gguf` → `export/export_gguf.py` → `export/deploy_renderer_v21.py`。

也可分步：

```bat
python training\train.py --config config\config_renderer.yaml --no-gguf
python export\export_gguf.py --config config\config_renderer.yaml
python export\deploy_renderer_v21.py
```

默认日志：`logs/train_renderer.log`。Renderer 配置里 **`save_gguf: false`**（训练脚本内直接对 4bit 基座导出 GGUF 会失败），必须走 `export_gguf.py`。

### 常用 CLI 参数

| 参数 | 说明 |
|------|------|
| `--config` | YAML 配置路径 |
| `--data` | 覆盖训练 JSONL |
| `--model` | 覆盖基座模型路径 |
| `--output-dir` | 覆盖输出目录 |
| `--epochs` | 覆盖训练轮数 |
| `--resume` | 从最新 checkpoint 恢复；也可 `--resume path\to\checkpoint-xxx` |
| `--no-gguf` | 跳过训练脚本内的 GGUF 导出 |

### 产物目录

| 路径 | 内容 |
|------|------|
| `outputs/AronaLM-Generator-V2.0-lora/` | Generator Trainer checkpoint |
| `outputs/AronaLM-Generator-V2.0-lora-adapter/` | Generator LoRA 适配器 |
| `outputs/AronaLM-Generator-V2.0-gguf/` | Generator GGUF（默认 `q4_k_m`） |
| `outputs/AronaLM-Renderer-V2.1-lora/` | Renderer Trainer checkpoint |
| `outputs/AronaLM-Renderer-V2.1-lora-adapter/` | Renderer LoRA 适配器 |
| `outputs/AronaLM-Renderer-V2.1-gguf/` | Renderer GGUF |
| `../../../models/AronaLM-Renderer-V2.1/` | `deploy_renderer_v21.py` 部署目标 |

部署后手动改 `backend/config.yaml` 的 `model.gguf_path`（脚本不会改配置，便于回滚到 v2.0）。

---

## 推理测试（LoRA）

```bat
cd llm\aronaLM\finetune
python inference\inference.py --config config\config.yaml
python inference\inference.py --config config\config_renderer.yaml
```

单条非交互：

```bat
python inference\inference.py --config config\config.yaml --prompt "阿洛娜，早上好！"
```

指定适配器：

```bat
python inference\inference.py --adapter outputs\AronaLM-Generator-V2.0-lora-adapter
```

对话中输入 `quit` / `exit` / `q` 退出，`clear` 清空历史。

默认生成参数（见对应 YAML 的 `inference` 段）：

- `max_new_tokens: 128`
- `temperature: 0.7`
- `top_p: 0.85`
- `do_sample: true`

---

## GGUF 导出与使用

**推荐方式**（16bit 基座 + LoRA）：

```bat
python export\export_gguf.py --config config\config.yaml
python export\export_gguf.py --config config\config_renderer.yaml
python export\export_gguf.py --adapter outputs\AronaLM-Generator-V2.0-lora-adapter --quant q4_k_m
```

需先放置 `models/Qwen3-1.7B`（完整 16bit 权重，含 `config.json`）。

**llama.cpp 示例：**

```bat
llama-cli -m outputs\AronaLM-Renderer-V2.1-gguf\*.gguf -p "老师：阿洛娜你好" -n 128
```

**Ollama：** 新建 `Modelfile` 指向该 GGUF，再 `ollama create arona -f Modelfile`。

**后端：** 将 GGUF 放到 `models/AronaLM-Renderer-V2.1/`（或 v2.0），并设置 `model.gguf_path`。

---

## 评测

### Normal（基座 vs LoRA）

```bat
python eval\eval.py --config config\config.yaml
python eval\eval.py --adapter outputs\AronaLM-Generator-V2.0-lora-adapter
python eval\eval.py --no-judge --no-multi
```

默认开启基座对比、规则/Judge、多轮会话与训练集探针；DeepSeek Judge 配置读自 `backend/config.yaml` 的 `memory.extractor`。报告写入 `eval/reports/`。

### Renderer（意图卡硬例，生产向 GGUF）

```bat
python eval\eval_renderer.py --gguf ..\..\..\models\AronaLM-Generator-V2.0\AronaLM-Generator-V2.0.Q4_K_M.gguf --tag v20
python eval\eval_renderer.py --gguf ..\..\..\models\AronaLM-Renderer-V2.1\AronaLM-Renderer-V2.1.Q4_K_M.gguf --tag v21
```

用例见 `eval/renderer_cases.json`（问候时段、must_say / must_not、禁止话题反弹等）。

---

## 参数调优建议（6GB 显存）

| 现象 | 建议 |
|------|------|
| CUDA OOM | `per_device_train_batch_size: 1`；或 `max_seq_length: 1024`；确认 `load_in_4bit: true`、`use_gradient_checkpointing: "unsloth"` |
| 显存仍紧张 | `gradient_accumulation_steps` 提到 8，保持有效 batch≈8 |
| Normal 欠拟合 / 不像阿洛娜 | `num_train_epochs: 4~5`，或 `lora.r / lora_alpha: 32` |
| Renderer 不听话 / 漏 must_say | 检查语料卡质量；略增 epoch 或 curated 占比；勿用虚卡合成 |
| 过拟合 / 复读 | 降 epoch，或略降 `learning_rate`（Normal 默认 `2e-4`，Renderer 默认 `1.5e-4`） |
| 回复太短/太长 | 调推理 `max_new_tokens`、`temperature`（0.6~0.9） |
| GGUF 转换 OOM | `export.maximum_memory_usage: 0.3`，或改 `q8_0` / 先 merged_16bit 再 CPU 量化 |
| 想要更高质量 GGUF | `quantization_method: q5_k_m`（体积更大） |

有效 batch size ≈ `per_device_train_batch_size × gradient_accumulation_steps`（默认 2×4=8）。

---

## 常见问题排查

**1. `bitsandbytes` / CUDA 报错**  
确认 PyTorch CUDA 版与驱动匹配；Windows 上尽量用较新的 `bitsandbytes`。

**2. 数据校验失败**  
检查 JSONL 是否 UTF-8、每行合法 JSON、是否使用 `conversations` + `from`/`value`。

**3. Chat 格式怪异 / 出现 `<think>`**  
配置里保持 `model.enable_thinking: false`；本项目训练与推理均按关闭思考模式处理。

**4. 从中断处继续训练**  

```bat
start.bat --resume
```

或在 YAML 中设置：

```yaml
training:
  resume_from_checkpoint: true   # 或具体 checkpoint 路径
```

Renderer 请对 `start_renderer.bat` / `config_renderer.yaml` 使用同样方式；**不要**把旧 free-chat LoRA resume 到 Renderer 训练。

**5. Unsloth 在 Windows 安装困难**  
优先 WSL2 + Linux 环境训练；或使用官方 Colab/Docker 镜像，再把适配器拷回本机。

**6. 训练内 GGUF 导出失败**  
属预期（4bit 基座）。改用 `python export\export_gguf.py --config ...`，并确认已下载 `models/Qwen3-1.7B`。

**7. 推理仍像基座、不像微调结果**  
确认 `--adapter` 指向正确的 `*-lora-adapter` 目录，且含 `adapter_config.json` / `adapter_model.safetensors`。后端路径则检查 `model.gguf_path` 是否指向新导出的 GGUF。

**8. Renderer 回滚**  
将 `backend/config.yaml` 的 `model.gguf_path` 改回 `../models/AronaLM-Generator-V2.0/AronaLM-Generator-V2.0.Q4_K_M.gguf`。

---

## 配置速查

### AronaLM-Generator-V2.0（`config/config.yaml`）

- 数据：`normal_finetune.jsonl`
- LoRA：`r=16`, `lora_alpha=16`, `dropout=0`
- 训练：`batch=2`, `grad_accum=4`, `epochs=4`, `lr=2e-4`, `optim=adamw_8bit`
- 导出：`save_gguf: true`，目录 `outputs/AronaLM-Generator-V2.0-*`

### AronaLM-Renderer-V2.1（`config/config_renderer.yaml`）

- 数据：`mixed_renderer_finetune.jsonl`
- LoRA：`r=16`, `lora_alpha=16`, `dropout=0.05`
- 训练：`batch=2`, `grad_accum=4`, `epochs=3`, `lr=1.5e-4`
- 导出：`save_gguf: false`（训练后用 `export_gguf.py`），目录 `outputs/AronaLM-Renderer-V2.1-*`
- 系统提示与 `prompts/renderer_system.txt` / 生产 Renderer 对齐

修改 YAML 后无需改代码，重新运行对应 `start*.bat` 即可。
