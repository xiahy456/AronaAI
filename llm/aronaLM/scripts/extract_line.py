#!/usr/bin/env python3
"""
更完整的JSONL文件截取工具
功能: 提取前N行，显示进度，统计文件大小
"""

import os
import sys
import json
import argparse
from tqdm import tqdm  # 需要安装: pip install tqdm

def extract_jsonl_lines(input_file, output_file, num_lines=100, validate_json=True):
    """提取JSONL文件的前num_lines行"""
    
    # 检查输入文件
    if not os.path.exists(input_file):
        print(f"错误: 文件 {input_file} 不存在")
        return False
    
    # 获取文件总行数（用于进度显示）
    print("正在统计文件总行数...")
    with open(input_file, 'r', encoding='utf-8') as f:
        total_lines = sum(1 for _ in f)
    
    print(f"总行数: {total_lines}")
    lines_to_extract = min(num_lines, total_lines)
    
    try:
        valid_lines = 0
        invalid_lines = 0
        
        with open(input_file, 'r', encoding='utf-8') as infile, \
             open(output_file, 'w', encoding='utf-8') as outfile:
            
            # 使用tqdm显示进度
            for i, line in enumerate(tqdm(infile, total=lines_to_extract, desc="处理中")):
                if i >= lines_to_extract:
                    break
                
                if validate_json:
                    try:
                        json.loads(line.strip())
                        outfile.write(line)
                        valid_lines += 1
                    except json.JSONDecodeError:
                        invalid_lines += 1
                        # 可以选择跳过或保留
                        # outfile.write(line)  # 如果要保留非JSON行
                else:
                    outfile.write(line)
                    valid_lines += 1
        
        # 输出统计信息
        print(f"\n成功提取 {valid_lines} 行到 {output_file}")
        if invalid_lines > 0:
            print(f"跳过 {invalid_lines} 行无效JSON")
        
        # 显示输出文件大小
        output_size = os.path.getsize(output_file)
        print(f"输出文件大小: {output_size / 1024:.2f} KB")
        
        return True
        
    except Exception as e:
        print(f"错误: {e}")
        return False

def main():
    success = extract_jsonl_lines(
        "llm/aronaLM/data/processed/lccc.jsonl",
        "llm/aronaLM/data/processed/extracted_lccc.jsonl",
        100,
        True
    )
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()