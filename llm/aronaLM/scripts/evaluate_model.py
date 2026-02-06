# scripts/evaluate_model.py
import torch
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

def evaluate_model():
    """评估模型质量"""
    
    from model.aronalm import AronaLM
    from model.tokenizer import tokenizer
    
    # 加载最佳模型
    model_paths = [
        "llm/aronaLM/checkpoints/best_curriculum_model.pt",
        "llm/aronaLM/checkpoints/best_model.pt",
        "llm/aronaLM/checkpoints/final_model.pt"
    ]
    
    model = AronaLM()
    
    for path in model_paths:
        if os.path.exists(path):
            print(f"加载模型: {path}")
            model.load_state_dict(torch.load(path, map_location='cpu'))
            break
    
    model.eval()
    
    # 测试用例
    test_cases = [
        ("你好", "基础问候"),
        ("早上好阿罗娜", "带名字问候"),
        ("今天需要处理来自千禧年科技学院的文件", "长句理解"),
        ("谢谢你的帮助，阿罗娜", "致谢"),
        ("明天见", "告别"),
        ("今天天气不错，我们去散步吧", "建议活动"),
        ("帮我把这些文件分类一下", "具体指令"),
    ]
    
    print("=== 模型评估 ===")
    
    for test_input, category in test_cases:
        print(f"\n[{category}]")
        print(f"老师: {test_input}")
        
        # 编码
        input_tokens = tokenizer.encode(test_input)
        input_ids = torch.tensor([input_tokens], dtype=torch.long)
        
        # 生成回复
        with torch.no_grad():
            generated = model.generate(
                input_ids,
                max_length=50,
                temperature=0.8
            )
            
            generated_text = tokenizer.decode(generated[0].tolist(), skip_special_tokens=True)
            # 移除输入部分（如果模型重复了输入）
            if generated_text.startswith(test_input):
                generated_text = generated_text[len(test_input):].strip()
            
            print(f"阿罗娜: {generated_text}")

if __name__ == "__main__":
    evaluate_model()