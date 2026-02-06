import sys
import os
# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from model.tokenizer import tokenizer
from configs import MODEL_CONFIG

def verify_fixed_tokenizer():
    """验证修复后的分词器"""
    print("=== 验证分词器修复 ===")
    
    # 1. 检查特殊token是否存在
    print("1. 检查特殊token:")
    special_tokens = {
        '[PAD]': MODEL_CONFIG.pad_token_id,
        '[EOS]': MODEL_CONFIG.eos_token_id,
        '[UNK]': MODEL_CONFIG.unk_token_id
    }
    
    for token, expected_id in special_tokens.items():
        if token in tokenizer.char_to_id:
            actual_id = tokenizer.char_to_id[token]
            if actual_id == expected_id:
                print(f"   ✅ '{token}' -> ID: {actual_id} (正确)")
            else:
                print(f"   ❌ '{token}' -> ID: {actual_id} (期望: {expected_id})")
        else:
            print(f"   ❌ '{token}' 不在词汇表中！")
    
    # 2. 测试编码解码
    print("\n2. 测试编码解码:")
    
    test_cases = [
        ("你好[EOS]", "测试带EOS"),
        ("[EOS]", "仅EOS"),
        ("测试[PAD]句子", "测试带PAD"),
        ("未知字符𓀀", "测试未知字符")
    ]
    
    for text, description in test_cases:
        print(f"\n   {description}: '{text}'")
        
        # 编码
        encoded = tokenizer.encode(text)
        print(f"     编码: {encoded}")
        
        # 解码（不跳过特殊token）
        decoded_raw = tokenizer.decode(encoded, skip_special_tokens=False)
        print(f"     原始解码: '{decoded_raw}'")
        
        # 解码（跳过特殊token）
        decoded_clean = tokenizer.decode(encoded, skip_special_tokens=True)
        print(f"     清理解码: '{decoded_clean}'")
    
    # 3. 测试EOS处理
    print("\n3. 测试EOS处理:")
    
    # 正常句子
    normal_text = "你好，老师！"
    normal_encoded = tokenizer.encode(normal_text)
    normal_decoded = tokenizer.decode(normal_encoded, skip_special_tokens=True)
    print(f"   正常句子: '{normal_text}' -> '{normal_decoded}'")
    
    # 带EOS的句子
    eos_text = normal_text + "[EOS]"
    eos_encoded = tokenizer.encode(eos_text)
    eos_decoded = tokenizer.decode(eos_encoded, skip_special_tokens=True)
    print(f"   带EOS句子: '{eos_text}' -> '{eos_decoded}'")
    
    # 检查是否真的移除了EOS
    if normal_decoded == eos_decoded:
        print("   ✅ EOS被正确移除了")
    else:
        print(f"   ❌ EOS移除有问题: '{normal_decoded}' vs '{eos_decoded}'")

if __name__ == "__main__":
    verify_fixed_tokenizer()