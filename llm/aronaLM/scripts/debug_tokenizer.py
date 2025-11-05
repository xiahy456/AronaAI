import sys
import os
# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from model.tokenizer import tokenizer

# 分词器检测
def debug_tokenizer():
    test_text = "你好，老师！"
    print(f"测试文本: '{test_text}'")
    # 编码
    token_ids = tokenizer.encode(test_text)
    print(f"编码结果: {token_ids}")
    # 解码
    decoded_text = tokenizer.decode(token_ids)
    print(f"解码结果: '{decoded_text}'")
    # 检查词汇表大小
    vocab_size = tokenizer.get_vocab_size()
    print(f"词汇表大小: {vocab_size}")
    # 检查一些字符的映射
    test_chars = ["你", "好", "，", "老", "师", "！"]
    for char in test_chars:
        if char in tokenizer.char_to_id:
            print(f"'{char}' -> {tokenizer.char_to_id[char]}")
        else:
            print(f"'{char}' -> 未在词汇表中")

if __name__ == "__main__":
    debug_tokenizer()