import json
import os
import argparse
from pathlib import Path

def merge_json_to_jsonl(input_dir, output_file):
    # 确保输入目录存在
    input_path = Path(input_dir)
    if not input_path.is_dir():
        print(f"错误：目录 '{input_dir}' 不存在")
        return False
    
    # 获取所有JSON文件
    json_files = list(input_path.glob("*.json"))
    if not json_files:
        print(f"警告：在目录 '{input_dir}' 中没有找到JSON文件")
        return False
    
    print(f"找到 {len(json_files)} 个JSON文件")
    
    # 打开输出文件
    with open(output_file, 'w', encoding='utf-8') as out_f:
        total_conversations = 0
        
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as in_f:
                    data = json.load(in_f)
                
                # 确保数据是列表格式
                if not isinstance(data, list):
                    print(f"警告：文件 {json_file.name} 的根节点不是数组，跳过")
                    continue
                
                for item in data:
                    # 确保每个item包含conversation字段
                    if 'conversation' not in item:
                        print(f"警告：文件 {json_file.name} 中的某个对象缺少'conversation'字段，跳过该项")
                        continue
                    
                    conversation = item['conversation']
                    messages = []
                    
                    for msg in conversation:
                        if 'role' not in msg or 'content' not in msg:
                            print(f"警告：文件 {json_file.name} 中的消息缺少role或content字段，跳过该消息")
                            continue
                        
                        # 转换角色名称
                        role = msg['role']
                        if role == 'User':
                            role = 'user'
                        elif role == 'Arona':
                            role = 'assistant'
                        # 其他角色保持不变
                        
                        messages.append({
                            "role": role,
                            "content": msg['content']
                        })
                    
                    if messages:  # 只有非空消息列表才写入
                        out_f.write(json.dumps({"messages": messages}, ensure_ascii=False) + '\n')
                        total_conversations += 1
                        
            except json.JSONDecodeError as e:
                print(f"错误：文件 {json_file.name} 不是有效的JSON格式 - {e}")
            except Exception as e:
                print(f"错误：处理文件 {json_file.name} 时出错 - {e}")
        
        print(f"完成！共写入 {total_conversations} 条对话到 {output_file}")
    
    return True

def main():
    input_dir = "llm/aronaLM/data/adjust/normal"
    output_file = "llm/aronaLM/data/adjust/normal/normal.jsonl"
    
    merge_json_to_jsonl(input_dir, output_file)

if __name__ == "__main__":
    main()