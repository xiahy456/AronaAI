import json
from collections import Counter
import os

def analyze_dataset(file_path, sample_size=10000):
    """分析数据集的基本统计"""
    
    lengths = []
    sources = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i >= sample_size:
                break
            data = json.loads(line)
            lengths.append(len(data['text']))
            if 'source' in data:
                sources.append(data['source'])
    
    print(f"平均长度: {sum(lengths)/len(lengths):.1f} 字符")
    print(f"长度分布: 最小={min(lengths)}, 最大={max(lengths)}")
    
    if sources:
        source_counts = Counter(sources)
        print("数据来源分布:", dict(source_counts))

def main():
    base_dir = "llm/aronaLM/data/processed"
    
    for file_name in ['cluecorpus.jsonl', 'lccc.jsonl']:
        file_path = os.path.join(base_dir, file_name)
        if os.path.exists(file_path):
            print(f"分析 {file_name} ...")
            analyze_dataset(file_path)
            print()

if __name__ == "__main__":
    main()