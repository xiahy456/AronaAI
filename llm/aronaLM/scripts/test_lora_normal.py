# scripts/test_lora_model.py
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

def test_lora_model():
    """测试LoRA微调后的模型"""
    
    print("="*60)
    print("测试LoRA微调后的阿罗娜模型")
    print("="*60)
    
    # 加载基础模型和tokenizer
    base_model_name = "/arona-ai/model/hunyuan"
    lora_path = "/root/autodl-tmp/checkpoint/normal/final_model"
    
    tokenizer = AutoTokenizer.from_pretrained(
        base_model_name,
        trust_remote_code=True
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    
    # 加载基础模型（float16）
    model = AutoModelForCausalLM.from_pretrained(
        base_model_name,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True
    )
    
    # 加载LoRA权重
    model = PeftModel.from_pretrained(model, lora_path)
    model.eval()
    
    print("模型加载成功")
    
    # 测试对话
    test_cases = [
        "你好,请介绍一下自己",
        "早上好，阿罗娜",
        "阿罗娜喜欢喝什么？",
        "请介绍一下阿拜多斯高中",
        "你喜欢什么颜色？",
        "再见，阿罗娜"
    ]
    
    for user_input in test_cases:
        print(f"\n{'='*40}")
        print(f"老师: {user_input}")
        
        # 构建消息
        messages = [{"role": "user", "content": user_input}]
        
        # 应用聊天模板
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False
        )
        
        # 编码
        inputs = tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=512
        ).to(model.device)
        
        # 生成
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=128,
                do_sample=True,
                temperature=0.7,
                top_p=0.9,
                top_k=50,
                repetition_penalty=1.1,
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=tokenizer.eos_token_id
            )
        
        # 解码
        response = tokenizer.decode(
            outputs[0][inputs.input_ids.shape[1]:],
            skip_special_tokens=True
        )
        
        # 去除前缀
        response = response.removeprefix("<answer>\n") 
        response = response.removeprefix("<answer>")

        print(f"阿罗娜: {response}")

if __name__ == "__main__":
    test_lora_model()