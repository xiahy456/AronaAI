# test_env.py
import torch
from transformers import AutoTokenizer

# 1. 检查PyTorch和CUDA
print(f"PyTorch version: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}") # 希望输出为 True
if torch.cuda.is_available():
    print(f"GPU device: {torch.cuda.get_device_name(0)}")

# 2. 尝试加载一个小的分词器（不下载大模型）
tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")
print("Tokenizer loaded successfully!")

print("环境验证通过！")