import torch
import os
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    TrainingArguments,
    Trainer,
    DataCollatorForSeq2Seq
)
from datasets import load_dataset
import json

# ========== 配置参数 ==========
MODEL_NAME = "/arona-ai/model/hunyuan"
DATA_PATH = "/root/autodl-tmp/data/adjust/normal.jsonl"  # 你的训练数据文件
OUTPUT_DIR = "/root/autodl-tmp/checkpoint/normal"

# 训练超参数
BATCH_SIZE = 2
GRADIENT_ACCUMULATION = 8  # 有效batch size = 16
LEARNING_RATE = 2e-5
NUM_EPOCHS = 3
MAX_LENGTH = 256  # 最大序列长度
WARMUP_RATIO = 0.05
SAVE_STEPS = 50
LOGGING_STEPS = 10

# ========== 1. 加载模型和分词器 ==========
print("正在加载模型和分词器...")
tokenizer = AutoTokenizer.from_pretrained(
    MODEL_NAME,
    trust_remote_code=True
)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    torch_dtype=torch.float32,
    device_map="auto",
    trust_remote_code=True
)

# 设置padding token
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token
    model.config.pad_token_id = model.config.eos_token_id

print(f"模型加载完成，参数量: {sum(p.numel() for p in model.parameters()) / 1e9:.2f}B")
print(f"模型设备: {model.device}")

# ========== 2. 加载和处理数据 ==========
print("\n正在加载训练数据...")
dataset = load_dataset("json", data_files=DATA_PATH, split="train")
print(f"数据量: {len(dataset)} 条对话")

# 格式化函数：将messages转换为模型输入格式
def format_chat(example):
    """使用模型的chat template格式化对话"""
    messages = example["messages"]
    # 应用chat template，不添加生成提示
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=False
    )
    return {"text": text}

# 应用格式化
print("正在格式化数据...")
dataset = dataset.map(format_chat)

# 分词函数
def tokenize_function(examples):
    """将文本转换为token ids"""
    tokenized = tokenizer(
        examples["text"],
        truncation=True,
        max_length=MAX_LENGTH,
        padding=False,
        return_tensors=None
    )
    # 设置labels（因果LM训练需要）
    tokenized["labels"] = tokenized["input_ids"].copy()
    return tokenized

# 应用分词
print("正在分词...")
tokenized_dataset = dataset.map(
    tokenize_function,
    batched=True,
    remove_columns=["text", "messages"]  # 移除原始列，节省内存
)

print(f"分词完成，示例序列长度: {len(tokenized_dataset[0]['input_ids'])}")

# ========== 3. 设置训练参数 ==========
print("\n配置训练参数...")
training_args = TrainingArguments(
    # 输出和保存
    output_dir=OUTPUT_DIR,
    save_strategy="steps",
    save_steps=SAVE_STEPS,
    save_total_limit=3,  # 只保留最后3个checkpoint
    
    # 日志
    logging_dir=f"{OUTPUT_DIR}/logs",
    logging_strategy="steps",
    logging_steps=LOGGING_STEPS,
    report_to="none",
    
    # 训练配置
    num_train_epochs=NUM_EPOCHS,
    per_device_train_batch_size=BATCH_SIZE,
    gradient_accumulation_steps=GRADIENT_ACCUMULATION,
    learning_rate=LEARNING_RATE,
    warmup_ratio=WARMUP_RATIO,
    lr_scheduler_type="cosine",
    
    # 优化
    fp16=False,  # 混合精度训练
    bf16=False,
    gradient_checkpointing=True,  # 节省显存
    optim="adamw_torch",
    
    # 其他
    dataloader_num_workers=4,
    dataloader_pin_memory=True,
    remove_unused_columns=False,  # 避免数据列问题
    seed=42,
)

# ========== 4. 数据整理器 ==========
data_collator = DataCollatorForSeq2Seq(
    tokenizer=tokenizer,
    model=model,
    padding=True,
    return_tensors="pt"
)

# ========== 5. 初始化Trainer ==========
print("\n初始化Trainer...")
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_dataset,
    data_collator=data_collator,
    processing_class=tokenizer,
)

# ========== 6. 开始训练 ==========
print("\n" + "=" * 60)
print("开始训练！")
print("=" * 60)
print(f"有效batch size: {BATCH_SIZE * GRADIENT_ACCUMULATION}")
print(f"总训练步数: ~{len(tokenized_dataset) * NUM_EPOCHS // (BATCH_SIZE * GRADIENT_ACCUMULATION)}")
print("=" * 60)

trainer.train()

# ========== 7. 保存最终模型 ==========
print("\n保存最终模型...")
trainer.save_model(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)

print(f"\n✅ 训练完成！模型已保存至: {OUTPUT_DIR}")

# ========== 8. 测试模型 ==========
print("\n测试微调后的模型...")
test_inputs = [
    "晚上好，阿罗娜。",
    "今天工作好累啊",
    "阿罗娜喜欢什么？"
]

model.eval()
for test_input in test_inputs:
    messages = [{"role": "user", "content": test_input}]
    inputs = tokenizer.apply_chat_template(
        messages,
        add_generation_prompt=True,
        return_tensors="pt",
        enable_thinking=False
    ).to(model.device)
    
    with torch.no_grad():
        outputs = model.generate(
            inputs,
            max_new_tokens=128,
            temperature=0.7,
            top_p=0.9,
            do_sample=True,
            repetition_penalty=1.05
        )
    
    response = tokenizer.decode(outputs[0][inputs.shape[1]:], skip_special_tokens=True)
    print(f"\n用户: {test_input}")
    print(f"阿罗娜: {response}")

print("\n✅ 所有步骤完成！")