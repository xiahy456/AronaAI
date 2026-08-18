# scripts/load_original.py
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

def test_original_model():
    """测试原始模型是否正常"""
    
    original_path = "/arona-ai/model/hunyuan"
    
    print("加载原始模型...")
    
    tokenizer = AutoTokenizer.from_pretrained(
        original_path,
        trust_remote_code=True
    )
    
    model = AutoModelForCausalLM.from_pretrained(
        original_path,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True
    )
    model.eval()
    
    print("原始模型加载成功")
    
    # 测试
    messages = [{"role": "user", "content": "你好"}]
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False
    )
    
    inputs = tokenizer(text, return_tensors="pt").to(model.device)
    
    with torch.no_grad():
        outputs = model(**inputs)
        logits = outputs.logits
        print(f"Logits 是否有NaN: {torch.isnan(logits).any()}")
        print(f"Logits 范围: min={logits.min():.4f}, max={logits.max():.4f}")
        
        generated = model.generate(
            **inputs,
            max_new_tokens=50,
            do_sample=False
        )
        response = tokenizer.decode(generated[0], skip_special_tokens=True)
        print(f"生成: {response}")

if __name__ == "__main__":
    test_original_model()