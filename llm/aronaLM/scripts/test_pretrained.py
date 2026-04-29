# scripts/test_pretrained.py
import torch
import sys
import os
# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.append('.')
from model.pretrain_model import PretrainLM
from model.tokenizer import tokenizer

def test_pretrained_model(model_path):
    """测试预训练模型"""
    
    # 加载模型
    model = PretrainLM()
    checkpoint = torch.load(model_path, map_location='cpu')
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()
    
    print("=== 预训练模型测试 ===\n")
    
    test_inputs = [
        "你好",
        "今天天气",
        "我喜欢",
        "人工智能",
        "机器学习",
        "中国",
        "北京"
    ]
    
    for prompt in test_inputs:
        # 编码
        input_ids = torch.tensor([tokenizer.encode(prompt)], dtype=torch.long)
        
        # 生成
        with torch.no_grad():
            output_ids = model.generate(
                input_ids,
                max_new_tokens=20,
                temperature=0.8
            )
        
        # 解码
        generated = tokenizer.decode(output_ids[0].tolist(), skip_special_tokens=True)
        print(f"输入: {prompt}")
        print(f"输出: {generated}")
        print("-" * 40)

if __name__ == "__main__":
    test_pretrained_model("/root/autodl-tmp/checkpoint/pretrain_small/best_model.pt")