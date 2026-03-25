# training/finetune_lora_simple.py
import torch
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    TrainingArguments,
    Trainer,
    DataCollatorForSeq2Seq
)
from peft import LoraConfig, get_peft_model, TaskType
from datasets import Dataset
import json

def finetune_lora():
    """LoRA微调"""
    
    print("="*60)
    print("LoRA微调阿罗娜模型")
    print("="*60)
    
    # 1. 加载模型（直接使用FP16，不需要8bit）
    model_name = "/arona-ai/model/hunyuan"
    
    tokenizer = AutoTokenizer.from_pretrained(
        model_name,
        trust_remote_code=True
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    
    # 直接加载FP16模型
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.float16,  # 半精度，显存约3.6GB
        device_map="auto",
        trust_remote_code=True
    )
    
    print(f"模型加载完成")
    print(f"显存占用: {torch.cuda.memory_allocated()/1024**3:.2f} GB")
    
    # 2. 配置LoRA
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=24,   # 16
        lora_alpha=48,  # 16
        lora_dropout=0.1,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        bias="none"
    )
    
    model = get_peft_model(model, lora_config)
    
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"可训练参数: {trainable/1e6:.2f}M / {total/1e6:.0f}M ({trainable/total*100:.2f}%)")
    
    # 3. 加载数据
    data_path = "/root/autodl-tmp/data/adjust/intimate.jsonl"
    conversations = []
    with open(data_path, 'r', encoding='utf-8') as f:
        for line in f:
            conversations.append(json.loads(line))
    
    dataset = Dataset.from_list(conversations)
    print(f"数据量: {len(dataset)} 条对话")
    
    # 4. 预处理
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
            max_length=256,
            padding=False
        )
        tokenized["labels"] = tokenized["input_ids"].copy()
        return tokenized
    
    tokenized_dataset = dataset.map(
        preprocess_function,
        remove_columns=dataset.column_names,
        batched=False,
        num_proc=4
    )
    
    # 5. 训练参数
    training_args = TrainingArguments(
        output_dir="/root/autodl-tmp/checkpoint/intimate",
        num_train_epochs=12,    #10->12
        per_device_train_batch_size=4,
        gradient_accumulation_steps=2,
        learning_rate=2e-4,
        warmup_ratio=0.1,
        logging_steps=10,
        save_strategy="epoch",
        save_total_limit=3,
        fp16=True,  # 启用FP16混合精度训练
        report_to="none",
    )
    
    data_collator = DataCollatorForSeq2Seq(
        tokenizer,
        pad_to_multiple_of=8,
        return_tensors="pt"
    )
    
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset,
        data_collator=data_collator,
        processing_class=tokenizer,
    )
    
    # 6. 训练
    print("\n开始训练...")
    trainer.train()
    
    # 7. 保存
    model.save_pretrained("/root/autodl-tmp/checkpoint/intimate/final_model")
    tokenizer.save_pretrained("/root/autodl-tmp/checkpoint/intimate/final_model")
    
    print("\n✅ LoRA微调完成！")

if __name__ == "__main__":
    finetune_lora()