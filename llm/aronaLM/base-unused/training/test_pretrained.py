# scripts/test_pretrained.py
import torch
from model.pretrain_model import PretrainLM
from model.tokenizer import tokenizer
from configs import MODEL_CONFIG

def test_pretrained_model():
    """测试预训练模型"""
    
    # 加载预训练好的模型
    model = PretrainLM()
    checkpoint = torch.load('llm/aronaLM/checkpoints/pretrain/best_model.pt', map_location='cpu')
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()
    
    # 测试生成
    test_prompts = [
        "今天天气",
        "人工智能",
        "我喜欢"
    ]
    
    for prompt in test_prompts:
        print(f"\n提示: {prompt}")
        
        # 编码
        input_ids = torch.tensor([tokenizer.encode(prompt)], dtype=torch.long)
        
        # 生成
        with torch.no_grad():
            output_ids = model.generate(
                input_ids,
                max_new_tokens=30,
                temperature=0.8,
                top_k=40
            )
        
        # 解码
        generated = tokenizer.decode(output_ids[0].tolist(), skip_special_tokens=True)
        print(f"生成: {generated}")

if __name__ == "__main__":
    test_pretrained_model()