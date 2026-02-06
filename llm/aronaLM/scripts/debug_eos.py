import os
import sys
# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from model.tokenizer import tokenizer
from configs import MODEL_CONFIG

def debug_eos_token():
    """调试EOS token"""
    print("=== 调试EOS token ===")
    
    # 检查EOS token在词汇表中的映射
    print("1. 检查词汇表映射:")
    eos_text = "[EOS]"
    if eos_text in tokenizer.char_to_id:
        eos_id = tokenizer.char_to_id[eos_text]
        print(f"   '{eos_text}' -> ID: {eos_id}")
        print(f"   配置中的eos_token_id: {MODEL_CONFIG.eos_token_id}")
        
        if eos_id == MODEL_CONFIG.eos_token_id:
            print("   ✅ EOS token ID匹配正确")
        else:
            print("   ❌ EOS token ID不匹配！")
            
        # 检查反向映射
        if eos_id in tokenizer.id_to_char:
            mapped_back = tokenizer.id_to_char[eos_id]
            print(f"   ID {eos_id} -> '{mapped_back}'")
    else:
        print(f"   ❌ '{eos_text}' 不在词汇表中！")
    
    print("\n2. 测试编码解码:")
    test_sentences = [
        "你好[EOS]",
        "测试句子结束[EOS]",
        "[EOS]"
    ]
    
    for text in test_sentences:
        encoded = tokenizer.encode(text)
        decoded = tokenizer.decode(encoded)
        print(f"   原文: '{text}'")
        print(f"   编码: {encoded}")
        print(f"   解码: '{decoded}'")
        print()
    
    print("3. 检查所有特殊token:")
    special_tokens = ["[PAD]", "[EOS]", "[UNK]"]
    for token in special_tokens:
        if token in tokenizer.char_to_id:
            token_id = tokenizer.char_to_id[token]
            print(f"   '{token}' -> ID: {token_id}")
        else:
            print(f"   '{token}' -> 未找到")

if __name__ == "__main__":
    debug_eos_token()