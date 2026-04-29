# scripts/test_cpu_debug.py
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
import warnings
warnings.filterwarnings('ignore')

def test_cpu(model_path):
    """在CPU上测试，避免CUDA问题"""
    
    print("="*60)
    print("CPU调试模式测试")
    print("="*60)
    
    # 加载tokenizer
    tokenizer = AutoTokenizer.from_pretrained(
        model_path,
        trust_remote_code=True
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    
    # 强制使用CPU和float32
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype=torch.float32,
        device_map="cpu",
        trust_remote_code=True,
        low_cpu_mem_usage=True
    )
    model.eval()
    
    print("模型加载完成")
    print(f"设备: {model.device}")
    
    # 测试用例
    test_inputs = [
        "你好",
        "今天天气怎么样",
        "谢谢"
    ]
    
    for user_input in test_inputs:
        print(f"\n{'='*40}")
        print(f"输入: {user_input}")
        
        try:
            # 构建消息
            messages = [{"role": "user", "content": user_input}]
            
            # 应用模板
            text = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False
            )
            
            print(f"模板文本: {text[:100]}...")
            
            # 编码
            inputs = tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=512
            )
            
            print(f"输入shape: {inputs.input_ids.shape}")
            
            # 检查输入
            print(f"输入ID范围: min={inputs.input_ids.min()}, max={inputs.input_ids.max()}")
            
            # 前向传播检查logits
            with torch.no_grad():
                outputs = model(**inputs)
                logits = outputs.logits
                print(f"Logits shape: {logits.shape}")
                print(f"Logits 范围: min={logits.min():.4f}, max={logits.max():.4f}")
                print(f"是否有NaN: {torch.isnan(logits).any()}")
                print(f"是否有Inf: {torch.isinf(logits).any()}")
                
                # 简单生成（贪心解码）
                generated = model.generate(
                    inputs.input_ids,
                    max_new_tokens=50,
                    do_sample=False,
                    pad_token_id=tokenizer.pad_token_id,
                    eos_token_id=tokenizer.eos_token_id,
                    temperature=1.0
                )
                
                response = tokenizer.decode(generated[0], skip_special_tokens=True)
                # 提取助手回复
                if "assistant" in response:
                    response = response.split("assistant")[-1].strip()
                print(f"生成结果: {response}")
                
        except Exception as e:
            print(f"错误: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    model_path = "/root/autodl-tmp/checkpoint/normal/final_model"
    test_cpu(model_path)