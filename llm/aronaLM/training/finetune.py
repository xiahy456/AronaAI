# training/finetune_safe.py
import torch
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    TrainingArguments,
    Trainer,
    DataCollatorForSeq2Seq
)
from datasets import Dataset
import json
import os
import shutil
from pathlib import Path

def save_model_safely(model, tokenizer, path):
    """安全保存模型并验证"""
    
    # 创建临时目录
    temp_path = f"{path}_temp"
    if os.path.exists(temp_path):
        shutil.rmtree(temp_path)
    
    print(f"\n保存模型到临时目录: {temp_path}")
    
    # 保存到临时目录
    model.save_pretrained(temp_path, safe_serialization=True)
    tokenizer.save_pretrained(temp_path)
    
    # 立即验证
    print("验证保存的模型...")
    
    try:
        # 使用CPU加载验证
        test_model = AutoModelForCausalLM.from_pretrained(
            temp_path,
            torch_dtype=torch.float16,
            device_map="cpu",
            trust_remote_code=True
        )
        test_model.eval()
        
        # 简单测试
        test_input = "你好"
        test_text = tokenizer.apply_chat_template(
            [{"role": "user", "content": test_input}],
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False
        )
        test_ids = tokenizer(test_text, return_tensors="pt")
        
        with torch.no_grad():
            outputs = test_model(**test_ids)
            if torch.isnan(outputs.logits).any():
                print("❌ 验证失败：输出包含NaN")
                return False
            else:
                print("✅ 验证成功")
                
        # 清理临时模型
        del test_model
        torch.cuda.empty_cache()
        
        # 移动到最终位置
        if os.path.exists(path):
            shutil.rmtree(path)
        shutil.move(temp_path, path)
        print(f"模型已保存到: {path}")
        return True
        
    except Exception as e:
        print(f"验证失败: {e}")
        shutil.rmtree(temp_path)
        return False

def finetune_arona():
    """使用阿罗娜对话数据微调混元模型"""
    
    print("="*60)
    print("阿罗娜人格微调")
    print("="*60)
    
    # 1. 加载模型和tokenizer
    model_name = "/arona-ai/model/hunyuan"
    
    tokenizer = AutoTokenizer.from_pretrained(
        model_name,
        trust_remote_code=True
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    
    # 使用 float16
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True
    )
    
    print(f"模型加载完成")
    
    # 2. 加载数据
    data_path = "/root/autodl-tmp/data/adjust/normal.jsonl"
    print(f"\n加载数据: {data_path}")
    
    conversations = []
    with open(data_path, 'r', encoding='utf-8') as f:
        for line in f:
            conversations.append(json.loads(line))
    
    dataset = Dataset.from_list(conversations)
    print(f"数据量: {len(dataset)} 条对话")
    
    # 3. 预处理函数
    def preprocess_function(examples):
        text = tokenizer.apply_chat_template(
            examples["messages"],
            tokenize=False,
            add_generation_prompt=False,
            enable_thinking=False
        )
        
        tokenized = tokenizer(
            text,
            truncation=True,
            max_length=512,
            padding=False,
            return_tensors=None
        )
        
        tokenized["labels"] = tokenized["input_ids"].copy()
        return tokenized
    
    # 4. 预处理数据
    print("\n预处理数据...")
    tokenized_dataset = dataset.map(
        preprocess_function,
        remove_columns=dataset.column_names,
        batched=False,
        num_proc=4
    )
    
    # 5. 训练参数 - 简化配置
    training_args = TrainingArguments(
        output_dir="/root/autodl-tmp/checkpoint/normal",
        
        # 训练配置
        num_train_epochs=3,  # 减少到3轮
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        warmup_steps=50,
        
        # 优化器
        learning_rate=2e-5,
        weight_decay=0.01,
        
        # 保存
        save_strategy="epoch",
        save_total_limit=3,
        
        # 日志
        logging_steps=10,
        
        # 性能 - 关闭混合精度
        fp16=False,
        bf16=False,
        gradient_checkpointing=False,
        dataloader_num_workers=2,
        
        # 评估
        eval_strategy="no",
        
        report_to="none",
        
        # 确保保存完整
        save_safely=True,
    )
    
    # 6. 数据整理器
    data_collator = DataCollatorForSeq2Seq(
        tokenizer,
        pad_to_multiple_of=8,
        return_tensors="pt"
    )
    
    # 7. 创建Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset,
        data_collator=data_collator,
        processing_class=tokenizer,
    )
    
    # 8. 开始训练
    print("\n开始训练...")
    print(f"训练样本数: {len(dataset)}")
    print(f"训练轮数: {training_args.num_train_epochs}")
    
    trainer.train()
    
    # 9. 安全保存最终模型
    print("\n保存最终模型...")
    success = save_model_safely(
        model, 
        tokenizer, 
        "/root/autodl-tmp/checkpoint/normal/final_model"
    )
    
    if success:
        print("\n✅ 微调完成！")
        print(f"模型保存路径: /root/autodl-tmp/checkpoint/normal/final_model")
        
        # 测试加载
        print("\n测试加载...")
        test_model = AutoModelForCausalLM.from_pretrained(
            "/root/autodl-tmp/checkpoint/normal/final_model",
            torch_dtype=torch.float16,
            device_map="auto",
            trust_remote_code=True
        )
        test_model.eval()
        
        # 简单测试
        messages = [{"role": "user", "content": "你好"}]
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False
        )
        inputs = tokenizer(text, return_tensors="pt").to(test_model.device)
        
        with torch.no_grad():
            outputs = test_model.generate(
                **inputs,
                max_new_tokens=30,
                do_sample=False
            )
            response = tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
            print(f"测试生成: {response}")
    else:
        print("\n❌ 模型保存失败！")

if __name__ == "__main__":
    finetune_arona()