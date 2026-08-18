import json

# 读取你的原始JSON文件
with open('llm/aronaLM/data/adjust/normal/total.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# 转换为新格式
converted_data = []
for item in data:
    messages = []
    for turn in item['conversation']:
        # 转换角色名：User -> user, Arona -> assistant
        role = 'user' if turn['role'] == 'User' else 'assistant'
        messages.append({
            'role': role,
            'content': turn['content']
        })
    converted_data.append({'messages': messages})

# 保存为JSONL格式
with open('llm/aronaLM/data/adjust/normal.jsonl', 'w', encoding='utf-8') as f:
    for item in converted_data:
        f.write(json.dumps(item, ensure_ascii=False) + '\n')

print(f"转换完成！共 {len(converted_data)} 条对话")
print("\n第一条数据示例：")
print(json.dumps(converted_data[0], ensure_ascii=False, indent=2))