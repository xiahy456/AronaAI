import json
import torch
from pathlib import Path
from torch.utils.data import Dataset, DataLoader, IterableDataset
from typing import List, Dict, Tuple
import sys
import os
# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(str(Path(__file__).parent.parent))
from configs import MODEL_CONFIG, TRAINING_CONFIG
from model.tokenizer import tokenizer

class PretrainIterableDataset(IterableDataset):
    """可迭代的预训练数据集 - 流式加载，不占用内存"""
    
    def __init__(self, data_path, max_seq_length=MODEL_CONFIG.max_gen_length):
        self.data_path = data_path
        self.max_seq_length = max_seq_length
        
        # 只计算文件大小，不加载数据
        self.file_size = Path(data_path).stat().st_size
        print(f"数据集文件大小: {self.file_size / 1024**3:.2f} GB")
    
    def __iter__(self):
        """迭代器 - 逐行读取，不加载到内存"""
        with open(self.data_path, 'r', encoding='utf-8') as f:
            for line in f:
                sample = json.loads(line)
                token_ids = sample['token_ids'].copy()
                
                # 添加EOS token
                token_ids.append(MODEL_CONFIG.eos_token_id)
                
                # 截断或填充
                if len(token_ids) > self.max_seq_length:
                    token_ids = token_ids[:self.max_seq_length]
                else:
                    padding = [MODEL_CONFIG.pad_token_id] * (self.max_seq_length - len(token_ids))
                    token_ids = token_ids + padding
                
                # 创建输入和标签
                input_ids = torch.tensor(token_ids[:-1], dtype=torch.long)
                labels = torch.tensor(token_ids[1:], dtype=torch.long)
                
                yield {
                    'input_ids': input_ids,
                    'labels': labels
                }
    
    def __len__(self):
        """返回一个估计的长度（用于进度条）"""
        # 粗略估计：假设每条约100字节
        return self.file_size // 100

def create_pretrain_dataloader(data_path, batch_size=24, shuffle=False, num_workers=2, max_seq_length=128):
    """创建流式预训练数据加载器
    
    Args:
        data_path: 数据文件路径
        batch_size: 批次大小
        shuffle: 是否打乱（对流式数据集无效）
        num_workers: 数据加载进程数（30GB数据建议用2）
        max_seq_length: 最大序列长度
    
    Returns:
        DataLoader对象
    """
    dataset = PretrainIterableDataset(data_path, max_seq_length)
    
    dataloader = DataLoader(
        dataset,
        batch_size=batch_size,
        num_workers=num_workers,
        pin_memory=True if torch.cuda.is_available() else False,
        prefetch_factor=2 if num_workers > 0 else None,
        persistent_workers=True if num_workers > 0 else False,
        drop_last=True
    )
    
    print(f"流式数据加载器创建完成:")
    print(f"  - 数据集类型: 流式迭代 (不占用内存)")
    print(f"  - Batch大小: {batch_size}")
    print(f"  - 数据加载进程: {num_workers}")
    print(f"  - 预估每个epoch步数: {len(dataset) // batch_size:,}")
    
    return dataloader