#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从已训练的 LoRA 适配器导出 GGUF。

训练阶段使用的是 4bit（bnb nf4）基座时，Unsloth 无法直接
save_pretrained_gguf；本脚本会加载 16bit 基座 + LoRA 再导出。

用法（在 finetune/ 目录下）:
  python export\\export_gguf.py
  python export\\export_gguf.py --adapter outputs\\aronalm-v2.0-normal-lora-adapter
  python export\\export_gguf.py --base ..\\..\\..\\models\\Qwen3-1.7B --quant q4_k_m
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

FINETUNE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = FINETUNE_ROOT / "config" / "config.yaml"
# QLoRA 训练用 4bit 基座；导出 GGUF 必须换用本地 16bit 权重（相对 finetune/）
DEFAULT_GGUF_BASE = "../../../models/Qwen3-1.7B"


def setup_logger(log_dir: Optional[Path] = None) -> logging.Logger:
    logger = logging.getLogger("arona_export_gguf")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.handlers.clear()

    fmt = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_dir / "export_gguf.log", encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    return logger


def resolve_path(path_str: str, base: Path = FINETUNE_ROOT) -> Path:
    p = Path(path_str)
    if not p.is_absolute():
        p = (base / p).resolve()
    return p


def load_config(config_path: Path) -> Dict[str, Any]:
    with config_path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg, dict):
        raise ValueError("配置文件根节点必须是映射（dict）")
    return cfg


def infer_16bit_base(name_or_path: str) -> Optional[str]:
    """若配置指向 *-bnb-4bit，尝试推断本地同级 16bit 目录。"""
    name = name_or_path.replace("\\", "/").rstrip("/")
    leaf = name.split("/")[-1]
    if "bnb-4bit" in leaf.lower() or leaf.endswith("-4bit"):
        # .../Qwen3-1.7B-unsloth-bnb-4bit -> .../Qwen3-1.7B（优先本地默认路径）
        if "qwen3-1.7b" in leaf.lower():
            local = resolve_path(DEFAULT_GGUF_BASE)
            if local.is_dir() and (local / "config.json").is_file():
                return str(local)
            sibling = Path(name).parent / "Qwen3-1.7B"
            if sibling.is_dir() and (sibling / "config.json").is_file():
                return str(sibling.resolve())
            return DEFAULT_GGUF_BASE
    return None


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        description="从 LoRA 适配器导出 GGUF（需 16bit 基座）"
    )
    parser.add_argument("--config", type=str, default=str(DEFAULT_CONFIG))
    parser.add_argument(
        "--adapter",
        type=str,
        default=None,
        help="LoRA 适配器目录（默认读 config export.lora_dir / inference.adapter_path）",
    )
    parser.add_argument(
        "--gguf-dir",
        type=str,
        default=None,
        help="GGUF 输出目录（默认读 config export.gguf_dir）",
    )
    parser.add_argument(
        "--base",
        type=str,
        default=None,
        help=f"本地 16bit 基座路径（默认 {DEFAULT_GGUF_BASE}）",
    )
    parser.add_argument(
        "--quant",
        type=str,
        default=None,
        help="量化方式，如 q4_k_m / q5_k_m / q8_0（默认读 config）",
    )
    parser.add_argument(
        "--max-mem",
        type=float,
        default=None,
        help="GGUF 转换 maximum_memory_usage（默认读 config，OOM 可降到 0.3）",
    )
    parser.add_argument(
        "--max-seq-length",
        type=int,
        default=None,
        help="加载时 max_seq_length（默认读 config）",
    )
    args = parser.parse_args()

    cfg = load_config(Path(args.config).resolve())
    export_cfg = dict(cfg.get("export", {}))
    model_cfg = dict(cfg.get("model", {}))
    infer_cfg = dict(cfg.get("inference", {}))
    log_cfg = dict(cfg.get("logging", {}))

    log_dir = resolve_path(log_cfg.get("log_dir", "logs"))
    logger = setup_logger(log_dir)

    adapter_str = (
        args.adapter
        or export_cfg.get("lora_dir")
        or infer_cfg.get("adapter_path")
        or "outputs/aronalm-v2.0-normal-lora-adapter"
    )
    if not adapter_str:
        logger.error("未指定 LoRA 适配器路径（--adapter 或 config export.lora_dir）")
        sys.exit(1)

    adapter_path = resolve_path(str(adapter_str))
    adapter_config = adapter_path / "adapter_config.json"
    if not adapter_path.is_dir() or not adapter_config.is_file():
        logger.error(
            "适配器无效: %s（需要目录内含 adapter_config.json）",
            adapter_path,
        )
        sys.exit(1)

    gguf_str = (
        args.gguf_dir
        or export_cfg.get("gguf_dir")
        or "outputs/aronalm-v2.0-normal-gguf"
    )
    gguf_dir = resolve_path(str(gguf_str))
    gguf_dir.mkdir(parents=True, exist_ok=True)

    base_model = args.base or export_cfg.get("gguf_base_model")
    if not base_model:
        trained_base = str(model_cfg.get("name_or_path", ""))
        base_model = infer_16bit_base(trained_base) or DEFAULT_GGUF_BASE

    # 相对路径基于 finetune/ 解析；要求本地目录存在，避免误走 HuggingFace 下载
    base_candidate = Path(str(base_model))
    if base_candidate.is_absolute() and base_candidate.exists():
        base_name = str(base_candidate.resolve())
    else:
        base_name = str(resolve_path(str(base_model)))

    base_dir = Path(base_name)
    if not base_dir.is_dir() or not (base_dir / "config.json").is_file():
        logger.error(
            "本地 16bit 基座不存在或无效: %s\n"
            "请确认 models/Qwen3-1.7B 已就绪，或用 --base 指定正确路径。",
            base_name,
        )
        sys.exit(1)

    if "bnb-4bit" in base_name.lower() or base_name.rstrip("/\\").endswith("-4bit"):
        logger.error(
            "基座看起来仍是 4bit（%s）。请用 --base 指定 16bit 权重，"
            "例如: --base ..\\..\\..\\models\\Qwen3-1.7B",
            base_name,
        )
        sys.exit(1)

    quant = args.quant or export_cfg.get("quantization_method", "q4_k_m")
    max_mem = (
        float(args.max_mem)
        if args.max_mem is not None
        else float(export_cfg.get("maximum_memory_usage", 0.7))
    )
    max_seq_length = int(
        args.max_seq_length
        if args.max_seq_length is not None
        else model_cfg.get("max_seq_length", 2048)
    )

    logger.info("适配器: %s", adapter_path)
    logger.info("16bit 基座: %s", base_name)
    logger.info("输出目录: %s", gguf_dir)
    logger.info("量化: %s | max_mem=%.2f | max_seq_length=%d", quant, max_mem, max_seq_length)

    from peft import PeftModel
    from unsloth import FastLanguageModel
    from unsloth.save import patch_saving_functions

    logger.info("正在加载 16bit 基座（load_in_4bit=False）...")
    try:
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=base_name,
            max_seq_length=max_seq_length,
            dtype=None,
            load_in_4bit=False,
        )
    except Exception:
        logger.error("加载 16bit 基座失败:\n%s", traceback.format_exc())
        logger.error(
            "请确认本地 16bit 基座路径正确，或用 --base 指定，例如:\n"
            "  --base ..\\..\\..\\models\\Qwen3-1.7B"
        )
        sys.exit(1)

    logger.info("正在挂载 LoRA 适配器...")
    try:
        model = PeftModel.from_pretrained(model, str(adapter_path))
    except Exception:
        logger.error("加载 LoRA 失败:\n%s", traceback.format_exc())
        sys.exit(1)

    # 关键：PeftModel 会通过 __getattr__ 找到基座上的 save_pretrained_gguf，
    # 导致 self 不是 PeftModel、跳过 LoRA 合并。必须重新绑定保存方法。
    model = patch_saving_functions(model)
    if not isinstance(model, PeftModel):
        logger.error(
            "挂载后模型仍不是 PeftModel（type=%s），中止以免导出未合并的基座。",
            type(model).__name__,
        )
        sys.exit(1)
    logger.info("已确认 PeftModel，导出时将合并 LoRA")

    logger.info("正在导出 GGUF（合并 LoRA → 16bit → 量化）...")
    try:
        try:
            result = model.save_pretrained_gguf(
                str(gguf_dir),
                tokenizer,
                quantization_method=quant,
                maximum_memory_usage=max_mem,
            )
        except TypeError:
            logger.warning("当前 Unsloth 不支持 maximum_memory_usage，改用无该参数导出")
            result = model.save_pretrained_gguf(
                str(gguf_dir),
                tokenizer,
                quantization_method=quant,
            )
    except Exception:
        logger.error("GGUF 导出失败:\n%s", traceback.format_exc())
        logger.error(
            "若显存不足：可加 --max-mem 0.3，或先 "
            'model.save_pretrained_merged(..., save_method="merged_16bit") '
            "再用 llama.cpp convert_hf_to_gguf.py"
        )
        sys.exit(1)

    gguf_files = _collect_gguf_outputs(gguf_dir, result, logger)
    if not gguf_files:
        logger.error("导出流程结束，但未找到 .gguf 文件（目录: %s）", gguf_dir)
        sys.exit(1)

    logger.info("GGUF 导出成功！（已合并 LoRA）")
    for f in gguf_files:
        size_mb = f.stat().st_size / (1024 * 1024)
        logger.info("  %s (%.1f MB)", f, size_mb)

    # 提醒：此前若未合并 LoRA，可能在 models/ 下生成了仅基座的假 GGUF
    stale = resolve_path("../../../models/Qwen3-1.7B.Q4_K_M.gguf")
    if stale.is_file() and stale.resolve() not in {f.resolve() for f in gguf_files}:
        logger.warning(
            "检测到可能未合并 LoRA 的旧文件（仅基座）: %s\n"
            "请勿用于推理；确认新导出可用后可手动删除。",
            stale,
        )


def _collect_gguf_outputs(
    gguf_dir: Path,
    result: Any,
    logger: logging.Logger,
) -> list[Path]:
    """收集 Unsloth 写出的 .gguf，并尽量挪到目标 gguf_dir。"""
    found: list[Path] = []

    if isinstance(result, dict):
        for item in result.get("gguf_files") or []:
            p = Path(item)
            if p.is_file() and p.suffix.lower() == ".gguf":
                found.append(p)
        gguf_subdir = result.get("gguf_directory")
        if gguf_subdir:
            sub = Path(gguf_subdir)
            if sub.is_dir():
                found.extend(p for p in sub.glob("*.gguf") if p.is_file())

    found.extend(p for p in gguf_dir.glob("*.gguf") if p.is_file())
    sibling = Path(str(gguf_dir) + "_gguf")
    if sibling.is_dir():
        found.extend(p for p in sibling.glob("*.gguf") if p.is_file())

    uniq: dict[Path, Path] = {}
    for p in found:
        uniq[p.resolve()] = p

    moved: list[Path] = []
    for src in uniq.values():
        if src.parent.resolve() == gguf_dir.resolve():
            moved.append(src)
            continue
        dest = gguf_dir / src.name
        try:
            if dest.resolve() != src.resolve():
                if dest.exists():
                    dest.unlink()
                shutil.move(str(src), str(dest))
                logger.info("已移动 GGUF: %s -> %s", src, dest)
            moved.append(dest)
        except Exception as e:
            logger.warning("无法移动 %s -> %s (%s)，保留原路径", src, dest, e)
            moved.append(src)

    return sorted({p.resolve() for p in moved if p.is_file()})


if __name__ == "__main__":
    main()
