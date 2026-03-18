# scripts/merge_data_for_training.py
import json
import os
import random
from tqdm import tqdm

def merge_datasets():
    """合并CLUECorpus和LCCC数据，创建训练/验证集"""
    
    base_dir = "llm/aronaLM/data/processed"
    
    # 输入文件
    clue_file = os.path.join(base_dir, "cluecorpus_small.jsonl")
    lccc_file = os.path.join(base_dir, "lccc.jsonl")
    
    # 输出文件
    train_file = os.path.join(base_dir, "train.jsonl")
    val_file = os.path.join(base_dir, "val.jsonl")
    
    # 首先统计总行数
    total_lines = 0
    for file_path in [clue_file, lccc_file]:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                total_lines += sum(1 for _ in f)
    
    print(f"总样本数: {total_lines:,}")
    
    # 验证集大小（0.5%）
    val_size = int(total_lines * 0.005)
    print(f"验证集大小: {val_size:,}")
    
    # 使用蓄水池采样
    val_indices = set()
    if val_size > 0:
        # 随机选择验证集索引
        val_indices = set(random.sample(range(total_lines), val_size))
    
    # 写入文件
    train_writer = open(train_file, 'w', encoding='utf-8')
    val_writer = open(val_file, 'w', encoding='utf-8')
    
    try:
        current_idx = 0
        for file_path in [clue_file, lccc_file]:
            if not os.path.exists(file_path):
                continue
                
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in tqdm(f, desc=f"处理 {os.path.basename(file_path)}"):
                    if current_idx in val_indices:
                        val_writer.write(line)
                    else:
                        train_writer.write(line)
                    
                    current_idx += 1
                    
                    # 每100万条打印一次进度
                    if current_idx % 1000000 == 0:
                        print(f"已处理 {current_idx:,} 条")
        
        print(f"\n处理完成！")
        print(f"训练集: {current_idx - len(val_indices):,} 条")
        print(f"验证集: {len(val_indices):,} 条")
        
    finally:
        train_writer.close()
        val_writer.close()

if __name__ == "__main__":
    merge_datasets()