# scripts/test_finetune.py
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
import warnings
warnings.filterwarnings('ignore')

def test_arona_model(model_path):
    """测试微调后的阿罗娜模型"""
    
    print("="*60)
    print("测试阿罗娜模型")
    print("="*60)
    
    # 1. 加载tokenizer
    tokenizer = AutoTokenizer.from_pretrained(
        model_path,
        trust_remote_code=True
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    
    # 2. 加载模型 - 使用 float16 并设置更稳定的配置
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True,
        low_cpu_mem_usage=True
    )
    
    # 设置为评估模式
    model.eval()
    
    print(f"模型加载完成")
    print(f"设备: {model.device}")
    
    # 3. 测试对话
    test_cases = [
        "你好呀，阿罗娜",
        "今天想喝点什么？",
        "你觉得什么是梦想？",
        "谢谢你的帮助",
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
        
        # 生成（使用更稳定的参数）
        with torch.no_grad():
            try:
                outputs = model.generate(
                    **inputs,
                    max_new_tokens=128,
                    do_sample=True,
                    temperature=0.7,
                    top_p=0.9,
                    top_k=50,  # 添加 top_k 增加稳定性
                    repetition_penalty=1.1,
                    pad_token_id=tokenizer.pad_token_id,
                    eos_token_id=tokenizer.eos_token_id,
                    # 确保不会生成NaN
                    output_scores=False,
                    return_dict_in_generate=False
                )
                
                # 解码
                response = tokenizer.decode(
                    outputs[0][inputs.input_ids.shape[1]:], 
                    skip_special_tokens=True
                )
                
                print(f"阿罗娜: {response}")
                
            except Exception as e:
                print(f"生成出错: {e}")
                # 如果出错，尝试不使用采样
                print("尝试使用贪心解码...")
                outputs = model.generate(
                    **inputs,
                    max_new_tokens=128,
                    do_sample=False,
                    pad_token_id=tokenizer.pad_token_id,
                    eos_token_id=tokenizer.eos_token_id
                )
                response = tokenizer.decode(
                    outputs[0][inputs.input_ids.shape[1]:], 
                    skip_special_tokens=True
                )
                print(f"阿罗娜: {response}")

def test_with_debug(model_path):
    """带调试信息的测试"""
    
    print("="*60)
    print("调试模式测试")
    print("="*60)
    
    import os
    os.environ['CUDA_LAUNCH_BLOCKING'] = '1'
    
    tokenizer = AutoTokenizer.from_pretrained(
        model_path,
        trust_remote_code=True
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True
    )
    model.eval()
    
    # 简单测试
    user_input = "你好"
    messages = [{"role": "user", "content": user_input}]
    
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )
    
    print(f"输入文本: {text}")
    
    inputs = tokenizer(text, return_tensors="pt").to(model.device)
    
    print(f"输入shape: {inputs.input_ids.shape}")
    
    with torch.no_grad():
        # 先检查logits
        outputs = model(**inputs)
        print(f"Logits shape: {outputs.logits.shape}")
        print(f"Logits 是否有NaN: {torch.isnan(outputs.logits).any()}")
        print(f"Logits 是否有Inf: {torch.isinf(outputs.logits).any()}")
        
        # 简单生成
        generated = model.generate(
            inputs.input_ids,
            max_new_tokens=50,
            do_sample=False,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id
        )
        
        response = tokenizer.decode(generated[0], skip_special_tokens=True)
        print(f"生成结果: {response}")

if __name__ == "__main__":
    model_path = "/root/autodl-tmp/checkpoint/normal/final_model"
    
    # 先运行调试模式
    test_with_debug(model_path)
    
    # 再运行正常测试
    test_arona_model(model_path)