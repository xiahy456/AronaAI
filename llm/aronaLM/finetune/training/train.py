#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qwen3-1.7B QLoRA 微调脚本（Unsloth + TRL SFTTrainer）

功能：
  - 4bit 量化加载本地/HF 模型
  - ShareGPT JSONL 数据校验与统计
  - LoRA 微调，支持 checkpoint 恢复
  - 训练结束后保存 LoRA 适配器，并可选导出 GGUF
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import traceback
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

# ---------------------------------------------------------------------------
# 路径常量：以 finetune/ 为项目根
# ---------------------------------------------------------------------------
FINETUNE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = FINETUNE_ROOT / "config" / "config.yaml"


def setup_logging(log_dir: Path, log_file: str) -> logging.Logger:
    """配置控制台 + 文件双通道日志。"""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / log_file

    logger = logging.getLogger("arona_finetune")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    fmt = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    logger.info("日志文件: %s", log_path)
    return logger


def load_config(config_path: Path) -> Dict[str, Any]:
    """加载 YAML 配置。"""
    if not config_path.is_file():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    with config_path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg, dict):
        raise ValueError("配置文件根节点必须是映射（dict）")
    return cfg


def resolve_path(path_str: str, base: Path = FINETUNE_ROOT) -> Path:
    """相对路径基于 finetune/ 解析；已是绝对路径则原样返回。"""
    p = Path(path_str)
    if not p.is_absolute():
        p = (base / p).resolve()
    return p


def validate_and_stats_jsonl(
    data_path: Path,
    conversations_field: str = "conversations",
    preview_samples: int = 2,
    logger: Optional[logging.Logger] = None,
) -> Dict[str, Any]:
    """
    校验 ShareGPT JSONL，并输出统计信息。

    期望格式：
      {"conversations": [{"from": "human"|"gpt"|"system", "value": "..."}, ...]}
    """
    log = logger or logging.getLogger("arona_finetune")

    if not data_path.is_file():
        raise FileNotFoundError(f"训练数据不存在: {data_path}")

    log.info("正在校验数据格式: %s", data_path)

    total = 0
    errors: List[str] = []
    turn_counter: Counter = Counter()
    role_counter: Counter = Counter()
    char_lens: List[int] = []
    previews: List[Dict[str, Any]] = []

    allowed_from = {"human", "gpt", "system", "user", "assistant"}

    with data_path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                errors.append(f"第 {line_no} 行 JSON 解析失败: {e}")
                continue

            if not isinstance(obj, dict):
                errors.append(f"第 {line_no} 行: 根对象必须是 JSON object")
                continue

            if conversations_field not in obj:
                errors.append(
                    f"第 {line_no} 行: 缺少字段 '{conversations_field}'"
                )
                continue

            convs = obj[conversations_field]
            if not isinstance(convs, list) or len(convs) == 0:
                errors.append(f"第 {line_no} 行: conversations 必须是非空数组")
                continue

            ok = True
            for i, msg in enumerate(convs):
                if not isinstance(msg, dict):
                    errors.append(f"第 {line_no} 行消息[{i}]: 必须是 object")
                    ok = False
                    break
                if "from" not in msg or "value" not in msg:
                    errors.append(
                        f"第 {line_no} 行消息[{i}]: 需要 'from' 与 'value' 字段"
                    )
                    ok = False
                    break
                if msg["from"] not in allowed_from:
                    errors.append(
                        f"第 {line_no} 行消息[{i}]: from='{msg['from']}' "
                        f"不在 {sorted(allowed_from)}"
                    )
                    ok = False
                    break
                if not isinstance(msg["value"], str) or not msg["value"].strip():
                    errors.append(
                        f"第 {line_no} 行消息[{i}]: value 必须是非空字符串"
                    )
                    ok = False
                    break
                role_counter[msg["from"]] += 1

            if not ok:
                continue

            # 轮次：按 human/gpt 成对近似统计
            n_human = sum(1 for m in convs if m["from"] in ("human", "user"))
            turn_counter[n_human] += 1
            char_lens.append(sum(len(m["value"]) for m in convs))
            total += 1

            if len(previews) < preview_samples:
                previews.append(obj)

    if errors:
        log.error("发现 %d 条格式错误（最多显示 20 条）:", len(errors))
        for err in errors[:20]:
            log.error("  - %s", err)
        raise ValueError(
            f"数据校验失败：共 {len(errors)} 处错误，请修复后重试。"
        )

    if total == 0:
        raise ValueError("数据文件为空或没有有效样本")

    avg_chars = sum(char_lens) / len(char_lens)
    stats = {
        "total_samples": total,
        "role_counts": dict(role_counter),
        "turn_distribution": dict(sorted(turn_counter.items())),
        "avg_chars": round(avg_chars, 2),
        "max_chars": max(char_lens),
        "min_chars": min(char_lens),
    }

    log.info("=" * 50)
    log.info("数据统计")
    log.info("  总样本数       : %d", stats["total_samples"])
    log.info("  角色消息计数   : %s", stats["role_counts"])
    log.info("  对话轮次分布   : %s  (key=用户轮数)", stats["turn_distribution"])
    log.info(
        "  字符长度       : avg=%.1f, min=%d, max=%d",
        stats["avg_chars"],
        stats["min_chars"],
        stats["max_chars"],
    )
    log.info("=" * 50)

    for i, sample in enumerate(previews):
        log.info("样本预览 [%d]: %s", i, json.dumps(sample, ensure_ascii=False)[:300])

    return stats


def detect_precision(cfg_bf16: Any, cfg_fp16: Any) -> Tuple[bool, bool]:
    """根据配置与硬件自动选择 bf16 / fp16。"""
    try:
        from unsloth import is_bfloat16_supported

        bf16_ok = is_bfloat16_supported()
    except Exception:
        import torch

        bf16_ok = torch.cuda.is_available() and torch.cuda.is_bf16_supported()

    if cfg_bf16 is None and cfg_fp16 is None:
        return bf16_ok, (not bf16_ok)
    bf16 = bool(cfg_bf16) if cfg_bf16 is not None else False
    fp16 = bool(cfg_fp16) if cfg_fp16 is not None else False
    if not bf16 and not fp16:
        # 两者都关则回退到自动
        return bf16_ok, (not bf16_ok)
    return bf16, fp16


def formatting_prompts_func(
    examples: Dict[str, List],
    tokenizer,
    enable_thinking: bool = False,
) -> Dict[str, List[str]]:
    """将 conversations 转为 chat template 文本。"""
    texts: List[str] = []
    for convo in examples["conversations"]:
        # standardize_sharegpt 后为 role/content
        try:
            text = tokenizer.apply_chat_template(
                convo,
                tokenize=False,
                add_generation_prompt=False,
                enable_thinking=enable_thinking,
            )
        except TypeError:
            # 旧版 tokenizer 可能不支持 enable_thinking
            text = tokenizer.apply_chat_template(
                convo,
                tokenize=False,
                add_generation_prompt=False,
            )
        texts.append(text)
    return {"text": texts}


def find_latest_checkpoint(output_dir: Path) -> Optional[str]:
    """在 output_dir 下查找最新 checkpoint-* 目录。"""
    if not output_dir.is_dir():
        return None
    ckpts = sorted(
        [p for p in output_dir.glob("checkpoint-*") if p.is_dir()],
        key=lambda p: int(p.name.split("-")[-1]) if p.name.split("-")[-1].isdigit() else -1,
    )
    return str(ckpts[-1]) if ckpts else None


def resolve_resume(resume_cfg: Any, output_dir: Path, logger: logging.Logger) -> Optional[str]:
    """解析 resume_from_checkpoint 配置。"""
    if resume_cfg is None or resume_cfg is False:
        return None
    if resume_cfg is True:
        path = find_latest_checkpoint(output_dir)
        if path:
            logger.info("自动恢复训练: %s", path)
        else:
            logger.warning("未找到可恢复的 checkpoint，将从头训练")
        return path
    path = resolve_path(str(resume_cfg))
    if not path.exists():
        raise FileNotFoundError(f"指定的 checkpoint 不存在: {path}")
    return str(path)


def train(config_path: Path, overrides: Dict[str, Any]) -> None:
    cfg = load_config(config_path)

    # CLI 覆盖
    if overrides.get("data_file"):
        cfg["data"]["train_file"] = overrides["data_file"]
    if overrides.get("model_path"):
        cfg["model"]["name_or_path"] = overrides["model_path"]
    if overrides.get("output_dir"):
        cfg["training"]["output_dir"] = overrides["output_dir"]
    if overrides.get("resume") is not None:
        cfg["training"]["resume_from_checkpoint"] = overrides["resume"]
    if overrides.get("epochs") is not None:
        cfg["training"]["num_train_epochs"] = overrides["epochs"]
    if overrides.get("no_gguf"):
        cfg["export"]["save_gguf"] = False

    log_cfg = cfg.get("logging", {})
    logger = setup_logging(
        resolve_path(log_cfg.get("log_dir", "logs")),
        log_cfg.get("log_file", "train.log"),
    )
    logger.info("配置文件: %s", config_path)
    logger.info("开始时间: %s", datetime.now().isoformat(timespec="seconds"))

    # ---- 数据校验 ----
    data_path = resolve_path(cfg["data"]["train_file"])
    validate_and_stats_jsonl(
        data_path,
        conversations_field=cfg["data"].get("conversations_field", "conversations"),
        preview_samples=int(cfg["data"].get("preview_samples", 2)),
        logger=logger,
    )

    # ---- 延迟导入（unsloth 需尽早 patch，放在校验之后减少无效启动成本）----
    logger.info("正在导入 Unsloth / TRL ...")
    from unsloth import FastLanguageModel
    from unsloth.chat_templates import standardize_sharegpt, train_on_responses_only
    from datasets import load_dataset
    from trl import SFTTrainer, SFTConfig

    model_cfg = cfg["model"]
    lora_cfg = cfg["lora"]
    train_cfg = cfg["training"]
    export_cfg = cfg["export"]

    model_path = resolve_path(model_cfg["name_or_path"])
    # 若本地目录不存在，回退为原始字符串（HF hub id）
    model_name = str(model_path) if model_path.exists() else model_cfg["name_or_path"]
    max_seq_length = int(model_cfg.get("max_seq_length", 2048))
    enable_thinking = bool(model_cfg.get("enable_thinking", False))

    # ---- 加载模型 ----
    logger.info("正在加载模型: %s", model_name)
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=model_name,
        max_seq_length=max_seq_length,
        dtype=None,  # 自动
        load_in_4bit=bool(model_cfg.get("load_in_4bit", True)),
    )
    logger.info("模型加载完成！")

    # ---- LoRA ----
    logger.info("正在配置 LoRA (r=%s, alpha=%s) ...", lora_cfg["r"], lora_cfg["lora_alpha"])
    model = FastLanguageModel.get_peft_model(
        model,
        r=int(lora_cfg["r"]),
        target_modules=list(lora_cfg["target_modules"]),
        lora_alpha=int(lora_cfg["lora_alpha"]),
        lora_dropout=float(lora_cfg.get("lora_dropout", 0)),
        bias=lora_cfg.get("bias", "none"),
        use_gradient_checkpointing=lora_cfg.get("use_gradient_checkpointing", "unsloth"),
        random_state=int(lora_cfg.get("random_state", 3407)),
        use_rslora=bool(lora_cfg.get("use_rslora", False)),
        loftq_config=None,
    )
    logger.info("LoRA 配置完成！")

    # ---- 数据集 ----
    logger.info("正在加载数据集 ...")
    dataset = load_dataset("json", data_files=str(data_path), split="train")
    logger.info("原始样本数: %d", len(dataset))

    # ShareGPT from/value -> role/content
    dataset = standardize_sharegpt(dataset)

    def _format(examples):
        return formatting_prompts_func(
            examples, tokenizer, enable_thinking=enable_thinking
        )

    dataset = dataset.map(_format, batched=True, desc="应用 chat template")
    logger.info("数据集处理完成！示例 text 前 200 字:\n%s", dataset[0]["text"][:200])

    # ---- 精度 ----
    use_bf16, use_fp16 = detect_precision(
        train_cfg.get("bf16"), train_cfg.get("fp16")
    )
    logger.info("精度设置: bf16=%s, fp16=%s", use_bf16, use_fp16)

    output_dir = resolve_path(train_cfg["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    resume_path = resolve_resume(
        train_cfg.get("resume_from_checkpoint"), output_dir, logger
    )

    # ---- SFTTrainer ----
    logger.info("正在初始化 SFTTrainer ...")
    sft_kwargs = dict(
        output_dir=str(output_dir),
        per_device_train_batch_size=int(train_cfg["per_device_train_batch_size"]),
        gradient_accumulation_steps=int(train_cfg["gradient_accumulation_steps"]),
        num_train_epochs=float(train_cfg["num_train_epochs"]),
        learning_rate=float(train_cfg["learning_rate"]),
        warmup_steps=int(train_cfg["warmup_steps"]),
        optim=train_cfg.get("optim", "adamw_8bit"),
        weight_decay=float(train_cfg.get("weight_decay", 0.01)),
        lr_scheduler_type=train_cfg.get("lr_scheduler_type", "linear"),
        logging_steps=int(train_cfg.get("logging_steps", 1)),
        save_steps=int(train_cfg.get("save_steps", 100)),
        save_total_limit=int(train_cfg.get("save_total_limit", 3)),
        seed=int(train_cfg.get("seed", 3407)),
        bf16=use_bf16,
        fp16=use_fp16,
        report_to=train_cfg.get("report_to", "none"),
        dataloader_num_workers=int(train_cfg.get("dataloader_num_workers", 0)),
        dataset_text_field="text",
        max_seq_length=max_seq_length,
        packing=False,
    )
    # 兼容不同 trl 版本的参数名
    try:
        sft_args = SFTConfig(**sft_kwargs)
    except TypeError:
        sft_kwargs.pop("max_seq_length", None)
        sft_kwargs.pop("dataset_text_field", None)
        sft_kwargs.pop("packing", None)
        sft_kwargs["max_length"] = max_seq_length
        sft_args = SFTConfig(**sft_kwargs)

    try:
        trainer = SFTTrainer(
            model=model,
            tokenizer=tokenizer,
            train_dataset=dataset,
            args=sft_args,
        )
    except TypeError:
        # 新版 trl 将 tokenizer 重命名为 processing_class
        trainer = SFTTrainer(
            model=model,
            processing_class=tokenizer,
            train_dataset=dataset,
            args=sft_args,
            dataset_text_field="text",
        )

    if train_cfg.get("train_on_responses_only", True):
        logger.info("启用 train_on_responses_only（仅对 assistant 计算 loss）")
        trainer = train_on_responses_only(
            trainer,
            instruction_part="<|im_start|>user\n",
            response_part="<|im_start|>assistant\n",
        )

    # ---- 训练 ----
    logger.info("训练开始...")
    try:
        train_result = trainer.train(resume_from_checkpoint=resume_path)
    except Exception:
        logger.error("训练失败:\n%s", traceback.format_exc())
        raise

    logger.info("训练完成！metrics: %s", train_result.metrics)

    # ---- 保存 LoRA ----
    if export_cfg.get("save_lora", True):
        lora_dir = resolve_path(export_cfg.get("lora_dir", "outputs/arona-qwen3-lora-adapter"))
        lora_dir.mkdir(parents=True, exist_ok=True)
        logger.info("正在保存 LoRA 适配器 -> %s", lora_dir)
        model.save_pretrained(str(lora_dir))
        tokenizer.save_pretrained(str(lora_dir))
        # 同步写一份训练配置便于复现
        with (lora_dir / "finetune_config_snapshot.yaml").open("w", encoding="utf-8") as f:
            yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)
        logger.info("模型保存成功！LoRA 适配器已写入 %s", lora_dir)

    # Trainer 默认也会在 output_dir 留 checkpoint；再存一份最终状态
    trainer.save_model(str(output_dir / "final"))
    tokenizer.save_pretrained(str(output_dir / "final"))

    # ---- 导出 GGUF ----
    if export_cfg.get("save_gguf", True):
        gguf_dir = resolve_path(export_cfg.get("gguf_dir", "outputs/arona-qwen3-gguf"))
        gguf_dir.mkdir(parents=True, exist_ok=True)
        quant = export_cfg.get("quantization_method", "q4_k_m")
        mem = float(export_cfg.get("maximum_memory_usage", 0.5))
        logger.info(
            "正在导出 GGUF (quant=%s, max_mem=%.2f) -> %s ...",
            quant,
            mem,
            gguf_dir,
        )
        try:
            model.save_pretrained_gguf(
                str(gguf_dir),
                tokenizer,
                quantization_method=quant,
                maximum_memory_usage=mem,
            )
            logger.info("GGUF 导出成功！目录: %s", gguf_dir)
        except TypeError:
            # 兼容旧版参数名
            logger.warning("maximum_memory_usage 不被当前 Unsloth 支持，尝试无该参数导出")
            try:
                model.save_pretrained_gguf(
                    str(gguf_dir),
                    tokenizer,
                    quantization_method=quant,
                )
                logger.info("GGUF 导出成功！目录: %s", gguf_dir)
            except Exception:
                logger.error("GGUF 导出失败:\n%s", traceback.format_exc())
                logger.error(
                    "可稍后手动: model.save_pretrained_merged(...) 再用 llama.cpp 转换"
                )
        except Exception:
            logger.error("GGUF 导出失败:\n%s", traceback.format_exc())
            logger.error(
                "LoRA 已保存，可稍后单独导出 GGUF。"
                "参见 README「常见问题」。"
            )

    logger.info("全部流程结束: %s", datetime.now().isoformat(timespec="seconds"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Qwen3-1.7B QLoRA 微调（阿洛娜）",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=str(DEFAULT_CONFIG),
        help="YAML 配置文件路径",
    )
    parser.add_argument("--data", type=str, default=None, help="覆盖训练 JSONL 路径")
    parser.add_argument("--model", type=str, default=None, help="覆盖模型路径/HF id")
    parser.add_argument("--output-dir", type=str, default=None, help="覆盖输出目录")
    parser.add_argument("--epochs", type=float, default=None, help="覆盖训练轮数")
    parser.add_argument(
        "--resume",
        nargs="?",
        const=True,
        default=None,
        help="从 checkpoint 恢复；不带参数则自动找最新",
    )
    parser.add_argument(
        "--no-gguf",
        action="store_true",
        help="训练结束后不导出 GGUF",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    overrides = {
        "data_file": args.data,
        "model_path": args.model,
        "output_dir": args.output_dir,
        "epochs": args.epochs,
        "resume": args.resume,
        "no_gguf": args.no_gguf,
    }
    # Windows 控制台尽量使用 UTF-8
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    train(Path(args.config).resolve(), overrides)


if __name__ == "__main__":
    main()
