# scripts/check_data_stats.py
import os

def check_data_stats():
    """检查处理后的数据统计"""
    
    base_dir = "llm/aronaLM/data/processed"
    
    for file_name in ['cluecorpus.jsonl', 'lccc.jsonl']:
        file_path = os.path.join(base_dir, file_name)
        if os.path.exists(file_path):
            file_size = os.path.getsize(file_path) / 1024 / 1024  # MB
            
            # 计算行数
            with open(file_path, 'r', encoding='utf-8') as f:
                line_count = sum(1 for _ in f)
            
            print(f"{file_name}:")
            print(f"  大小: {file_size:.2f} MB")
            print(f"  样本数: {line_count:,}")
            print()

if __name__ == "__main__":
    check_data_stats()