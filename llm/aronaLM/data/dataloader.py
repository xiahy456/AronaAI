import json
import torch
from pathlib import Path
from torch.utils.data import Dataset, DataLoader
from typing import List, Dict, Tuple
import sys
import os
# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from configs import MODEL_CONFIG, TRAINING_CONFIG
from model.tokenizer import tokenizer

# 对话数据集
class DialogueDataset(Dataset):
    def __init__(self, data_path: str):
        self.data_path = self._resolve_data_path(data_path)
        self.dialogues = self._load_data()
        self.samples = self._prepare_samples()

    # 加载数据路径
    def _resolve_data_path(self, data_path:str) -> Path:
        path = Path(data_path)
        # 如果路径直接存在，直接返回
        if path.exists():
            return path
        # 尝试相对于当前文件(dataloader.py)所在目录的路径
        current_dir = Path(__file__).parent  # data目录
        possible_paths = [
            current_dir / data_path,                    # data/目录下
            current_dir / "raw" / data_path,            # data/raw/目录下
            current_dir / data_path,                    # 再次尝试data目录
            Path.cwd() / "data" / "raw" / data_path,    # 项目根目录下的data/raw
            Path.cwd() / data_path,                     # 项目根目录下
        ]
        for possible_path in possible_paths:
            print(f"尝试路径: {possible_path}")  # 调试信息
            if possible_path.exists():
                print(f"找到文件: {possible_path}")  # 调试信息
                return possible_path
        # 如果都找不到，抛出详细错误
        raise FileNotFoundError(
            f"找不到数据文件: {data_path}\n"
            f"当前工作目录: {Path.cwd()}\n"
            f"data目录: {Path(__file__).parent}\n"
            f"尝试过的路径: {[str(p) for p in possible_paths]}"
        )

    # 加载对话数据
    def _load_data(self) -> List[Dict]:
        print(f"正在加载数据文件: {self.data_path}")  # 调试信息
        with open(self.data_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"成功加载 {len(data)} 条对话数据")  # 调试信息
        return data

    # # 准备单轮对话训练样本
    # def _prepare_samples(self) -> List[Tuple[List[int], List[int]]]:
    #     samples = []
    #     for dialogue in self.dialogues:
    #         input_text = dialogue["input"]
    #         output_text = dialogue["output"]
    #         # 编码为token
    #         input_ids = tokenizer.encode(input_text)
    #         output_ids = tokenizer.encode(output_text)
    #         samples.append((input_ids, output_ids))
    #     return samples

    # 准备多轮对话训练样本
    def _prepare_samples(self) -> List[Tuple[List[int], List[int]]]:
        samples = []
        for dialogue in self.dialogues:
            if "conversation" in dialogue:
                # 多轮对话格式
                conversation = dialogue["conversation"]
                # 为每轮对话构建训练样本
                for i in range(1, len(conversation)):
                    if conversation[i]["role"] == "Arona":
                        # 构建上下文（之前的所有对话）
                        context_parts = []
                        for j in range(i):
                            role = conversation[j]["role"]
                            content = conversation[j]["content"]
                            role_display = "User" if role == "User" else "Arona"
                            context_parts.append(f"{role_display}: {content}")
                        input_text = " ".join(context_parts)
                        output_text = conversation[i]["content"] + "[EOS]"
                        # 编码为token
                        input_ids = tokenizer.encode(input_text)
                        output_ids = tokenizer.encode(output_text)
                        samples.append((input_ids, output_ids))
                    # 兼容单轮对话格式
            elif "input" in dialogue and "output" in dialogue:
                input_text = dialogue["input"]
                output_text = dialogue["output"] = "[EOS]"
                # 编码为token
                input_ids = tokenizer.encode(input_text)
                output_ids = tokenizer.encode(output_text)
                samples.append((input_ids, output_ids))

        print(f"从对话数据中准备了 {len(samples)} 个训练样本")
        return samples
    
    def __len__(self):
        return len(self.samples)
    
    def __getitem__(self, idx):
        input_ids, output_ids = self.samples[idx]

        # 构建模型输入：input_ids + output_ids
        # 输入：[input_ids]
        # 输出：[output_ids]（偏移一位）

        # 截断或填充到固定长度
        input_ids = self._pad_or_truncate(input_ids, MODEL_CONFIG.max_seq_length)
        output_ids = self._pad_or_truncate(output_ids, MODEL_CONFIG.max_seq_length)

        return {
            'input_ids': torch.tensor(input_ids, dtype=torch.long),
            'output_ids': torch.tensor(output_ids, dtype=torch.long),
        }
    
    # 填充或截断序列到固定长度
    def _pad_or_truncate(self, token_ids: List[int], max_length: int) -> List[int]:
        if len(token_ids) > max_length:
            return token_ids[:max_length]
        else:
            padding = [MODEL_CONFIG.pad_token_id] * (max_length - len(token_ids))
            return token_ids + padding

# 创建数据加载器
def create_data_loader(data_path: str, batch_size: int = None, shuffle: bool = True):
    if data_path is None:
        data_path = TRAINING_CONFIG.data_path
    if batch_size is None:
        batch_size = TRAINING_CONFIG.batch_size
        
    print(f"创建数据加载器，数据路径: {data_path}")  # 调试信息
    dataset = DialogueDataset(data_path)
    dataloader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=TRAINING_CONFIG.num_workers
    )
    return dataloader

# 测试数据加载器
def test_dataloader():
    try:
        dataloader = create_data_loader("raw/training_dialogues.json")
        for i, batch in enumerate(dataloader):
            print(f"Batch {i}:")
            print(f"  input_ids shape: {batch['input_ids'].shape}")
            print(f"  output_ids shape: {batch['output_ids'].shape}")
            # 解码回文本查看
            input_text = tokenizer.decode(batch['input_ids'][0].tolist())
            output_text = tokenizer.decode(batch['output_ids'][0].tolist())
            print(f"  input text: {input_text}")
            print(f"  output text: {output_text}")
            print()
            if i >= 1:
                break
    except Exception as e:
        print(f"错误: {e}")
        print("\n当前目录结构:")
        current_dir = Path(__file__).parent
        for file_path in current_dir.rglob("*"):
            print(f"  {file_path.relative_to(current_dir.parent)}")

# 测试
if __name__ == "__main__":
    test_dataloader()