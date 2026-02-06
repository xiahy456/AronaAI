import torch
import sys
import os
# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# 重新初始化模型以适应新的分词器
def reinitialize_model():
    print("重新初始化模型...")
    from model.aronalm import AronaLM
    
    # 创建新模型（会使用新的分词器）
    model = AronaLM()
    
    # 保存新模型
    torch.save(model.state_dict(), "llm/aronaLM/checkpoints/reinitialized_model.pt")
    print("新模型已保存: llm/aronaLM/checkpoints/reinitialized_model.pt")
    
    # 测试新模型
    from model.tokenizer import tokenizer
    
    model.eval()
    test_input = "你好"
    input_tokens = tokenizer.encode(test_input)
    input_ids = torch.tensor([input_tokens], dtype=torch.long)
    
    with torch.no_grad():
        generated = model.generate(input_ids, max_length=20)
        generated_text = tokenizer.decode(generated[0].tolist(), skip_special_tokens=True)
        
        print(f"测试输入: '{test_input}'")
        print(f"生成结果: '{generated_text}'")

if __name__ == "__main__":
    reinitialize_model()