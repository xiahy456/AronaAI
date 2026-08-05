# Qwen3-1.7B QLoRA 微调（阿洛娜）

基于 [Unsloth](https://github.com/unslothai/unsloth) 对本地 `Qwen3-1.7B-unsloth-bnb-4bit` 做 QLoRA 微调，训练数据为 ShareGPT 格式 JSONL，训练结束后可导出 GGUF 供 llama.cpp / Ollama 使用。

面向硬件：**RTX 4060 笔记本（约 6–8GB 显存）**。

---

## 项目结构

```
finetune/
├── config/
│   └── config.yaml          # 统一配置（模型 / 数据 / LoRA / 训练 / 导出 / 推理）
├── training/
│   └── train.py             # 微调主脚本
├── inference/
│   └── inference.py         # 交互式推理测试
├── data/
│   └── finetune_training/
│       └── normal_finetune.jsonl
├── data-process/            # 数据合并等预处理脚本
├── outputs/                 # 训练产物（自动创建）
├── logs/                    # 训练日志（自动创建）
├── requirements.txt
├── start.bat                # Windows 一键训练
└── README.md
```

本地基座模型默认路径（相对本目录）：

`../../../models/Qwen3-1.7B-unsloth-bnb-4bit`

即仓库根目录下的 `models/Qwen3-1.7B-unsloth-bnb-4bit`。

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

当前默认数据：

`data/finetune_training/normal_finetune.jsonl`（约 1265 条）

若从 `data/raw/normal/expand/*.json` 重新合并，可运行：

```bat
python data-process\merge_expand_to_jsonl.py
```

训练启动时会自动校验格式，并打印：总条数、角色计数、轮次分布、字符长度统计。

---

## 训练启动

### 方式 A：一键脚本（推荐）

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

### 方式 B：直接调用 Python

```bat
cd llm\aronaLM\finetune
python training\train.py --config config\config.yaml
```

常用参数：

| 参数 | 说明 |
|------|------|
| `--config` | YAML 配置路径 |
| `--data` | 覆盖训练 JSONL |
| `--model` | 覆盖基座模型路径 |
| `--output-dir` | 覆盖输出目录 |
| `--epochs` | 覆盖训练轮数 |
| `--resume` | 从最新 checkpoint 恢复；也可 `--resume path\to\checkpoint-xxx` |
| `--no-gguf` | 跳过 GGUF 导出 |

日志写入：`logs/train.log`。

### 产物说明

| 路径 | 内容 |
|------|------|
| `outputs/arona-qwen3-lora/` | Trainer checkpoint |
| `outputs/arona-qwen3-lora-adapter/` | LoRA 适配器（推理用） |
| `outputs/arona-qwen3-gguf/` | GGUF（默认 `q4_k_m`） |

---

## 推理测试

```bat
cd llm\aronaLM\finetune
python inference\inference.py --config config\config.yaml
```

单条非交互测试：

```bat
python inference\inference.py --prompt "阿洛娜，早上好！"
```

指定适配器：

```bat
python inference\inference.py --adapter outputs\arona-qwen3-lora-adapter
```

对话中输入 `quit` / `exit` / `q` 退出，`clear` 清空历史。

默认生成参数（可在 `config.yaml` 的 `inference` 段修改）：

- `max_new_tokens: 256`
- `temperature: 0.7`
- `top_p: 0.9`
- `do_sample: true`

---

## GGUF / Ollama 使用摘要

训练成功且 `export.save_gguf: true` 时，会在 `outputs/arona-qwen3-gguf/` 生成 `.gguf` 文件。

**llama.cpp 示例：**

```bat
llama-cli -m outputs\arona-qwen3-gguf\*.gguf -p "老师：阿洛娜你好" -n 256
```

**Ollama：** 新建 `Modelfile` 指向该 GGUF，再 `ollama create arona -f Modelfile`。

若自动导出失败，可先保留 LoRA，再在 Python 中手动：

```python
from unsloth import FastLanguageModel
model, tokenizer = FastLanguageModel.from_pretrained("outputs/arona-qwen3-lora-adapter", load_in_4bit=True)
model.save_pretrained_gguf("outputs/arona-qwen3-gguf", tokenizer, quantization_method="q4_k_m")
```

或先 `save_pretrained_merged(..., save_method="merged_16bit")`，再用 llama.cpp 的 `convert_hf_to_gguf.py` 转换。

---

## 参数调优建议（6GB 显存）

| 现象 | 建议 |
|------|------|
| CUDA OOM | `per_device_train_batch_size: 1`；或 `max_seq_length: 1024`；确认 `load_in_4bit: true`、`use_gradient_checkpointing: "unsloth"` |
| 显存仍紧张 | `gradient_accumulation_steps` 提到 8，保持有效 batch≈8 |
| 欠拟合 / 不像阿洛娜 | `num_train_epochs: 4~5`，或 `lora.r / lora_alpha: 32` |
| 过拟合 / 复读 | 降到 2 epoch，或略降 `learning_rate` 到 `1e-4` |
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

或在 `config.yaml` 设置：

```yaml
training:
  resume_from_checkpoint: true   # 或具体 checkpoint 路径
```

**5. Unsloth 在 Windows 安装困难**  
优先 WSL2 + Linux 环境训练；或使用官方 Colab/Docker 镜像，再把适配器拷回本机。

**6. 推理仍像基座、不像微调结果**  
确认 `--adapter` 指向 `outputs/arona-qwen3-lora-adapter`，且该目录含 `adapter_config.json` / `adapter_model.safetensors`。

---

## 配置速查

核心默认值见 `config/config.yaml`：

- LoRA：`r=16`, `lora_alpha=16`, `dropout=0`，目标模块含 q/k/v/o/gate/up/down
- 训练：`batch=2`, `grad_accum=4`, `epochs=3`, `lr=2e-4`, `optim=adamw_8bit`
- 导出：`q4_k_m` GGUF + LoRA 适配器

修改后无需改代码，直接重新运行 `start.bat` 即可。
