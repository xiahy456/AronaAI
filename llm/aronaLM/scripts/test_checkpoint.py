# scripts/test_checkpoint.py
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
import os
from pathlib import Path

def find_latest_checkpoint(checkpoint_dir):
    """找到最新的检查点"""
    checkpoint_dir = Path(checkpoint_dir)
    
    # 查找所有检查点目录
    checkpoints = list(checkpoint_dir.glob("checkpoint-*"))
    if not checkpoints:
        return None
    
    # 按修改时间排序
    checkpoints.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return checkpoints[0]

def test_checkpoint():
    """测试检查点模型"""
    
    checkpoint_dir = "/root/autodl-tmp/checkpoint/normal"
    
    # 找到最新的检查点
    latest = find_latest_checkpoint(checkpoint_dir)
    
    if latest is None:
        print("未找到检查点")
        return
    
    print(f"使用检查点: {latest}")
    
    # 加载tokenizer
    tokenizer = AutoTokenizer.from_pretrained(
        latest,
        trust_remote_code=True
    )
    
    # 加载模型 - 使用float16
    model = AutoModelForCausalLM.from_pretrained(
        latest,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True
    )
    model.eval()
    
    print("模型加载成功")
    
    # 快速测试
    messages = [{"role": "user", "content": "你好"}]
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False
    )
    
    inputs = tokenizer(text, return_tensors="pt").to(model.device)
    
    with torch.no_grad():
        # 先检查logits
        outputs = model(**inputs)
        logits = outputs.logits
        print(f"Logits 是否有NaN: {torch.isnan(logits).any()}")
        print(f"Logits 是否有Inf: {torch.isinf(logits).any()}")
        
        if not torch.isnan(logits).any():
            # 生成
            generated = model.generate(
                **inputs,
                max_new_tokens=50,
                do_sample=False,
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=tokenizer.eos_token_id
            )
            response = tokenizer.decode(generated[0], skip_special_tokens=True)
            print(f"生成: {response}")
        else:
            print("Logits包含NaN，模型可能未正确加载")

if __name__ == "__main__":
    test_checkpoint()