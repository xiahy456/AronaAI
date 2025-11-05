# 配置加载器，用于从yaml读取参数

import yaml
import os
from dataclasses import dataclass
from typing import Optional
from pathlib import Path

CONFIG_DIR = Path(__file__).parent

@dataclass
class ModelConfig:
    # 模型架构配置
    name: str = "AronaLM"
    vocab_size: int = 16384
    pad_token_id: int = 0
    eos_token_id: int = 1
    unk_token_id: int = 2
    max_seq_length: int = 128
    d_model: int = 256
    n_layers: int = 8
    n_heads: int = 4
    d_ff: int = 1024
    dropout: float = 0.1
    max_gen_length: int = 128
    temperature: int = 50
    top_k: int = 50
    do_sample: bool = True

@dataclass
class TrainingConfig:
    # 训练过程配置
    data_path: str = "data/raw/training_dialogues.json"
    batch_size: int = 32
    num_workers: int = 2
    learning_rate: float = 0.001
    weight_decay: float = 0.1
    num_epochs: int = 50
    warmup_steps: int = 1000
    gradient_clip: float = 1.0
    checkpoint_dir: str = "./checkpoints"
    checkpoint_save_freq: int = 5
    checkpoint_keep_last: int = 3

def load_configs(
    model_config_path: str =  CONFIG_DIR / "model_config.yaml",
    training_config_path: str = CONFIG_DIR / "training_config.yaml"
):
    # 加载模型配置
    with open(model_config_path, 'r', encoding='utf-8') as f:
        model_dict = yaml.safe_load(f)['model']
    model_config = ModelConfig(**model_dict)
    
    # 加载训练配置
    with open(training_config_path, 'r', encoding='utf-8') as f:
        training_dict = yaml.safe_load(f)['training']
    training_config = TrainingConfig(**training_dict)

    # 返回
    return model_config, training_config

# 提供全局访问
try:
    MODEL_CONFIG, TRAINING_CONFIG = load_configs()
except FileNotFoundError:
    # 如果未找到配置文件，则使用默认配置
    print(f"未找到配置文件")
    MODEL_CONFIG = ModelConfig()
    TRAINING_CONFIG = TrainingConfig()