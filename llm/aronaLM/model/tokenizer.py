import json
import sys
import os
import cutword
from typing import List, Dict
# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from configs import MODEL_CONFIG

# 分词器
class Tokenizer:
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, vocab_size=MODEL_CONFIG.vocab_size):
        if not hasattr(self, 'initialized'):
            self.vocab_size = vocab_size
            self.cutter = cutword.Cutter()
            # 特殊token
            self.special_tokens = {
                '[PAD]': MODEL_CONFIG.pad_token_id,
                '[EOS]': MODEL_CONFIG.eos_token_id,
                '[UNK]': MODEL_CONFIG.unk_token_id
            }
            # 映射表
            self.char_to_id = {}
            self.id_to_char = {}
            self._build_vocab()
            self.initialized = True
            print(f"CutWord分词器初始化完成，词汇表大小: {self.get_vocab_size()}")
    
    # 构建词汇表
    def _build_vocab(self):
        # 特殊token
        current_id = 0
        # 添加特殊token作为整体
        for token, token_id in self.special_tokens.items():
            self.char_to_id[token] = token_id
            self.id_to_char[token_id] = token
            current_id = max(current_id, token_id + 1)
        
        # 基础字符集（作为后备）
        base_chars = []
        # 常用汉字
        for i in range(ord('一'), ord('龥') + 1):
            base_chars.append(chr(i))
            if len(base_chars) >= 5000:
                break
        # 英文字母、数字、标点
        base_chars.extend([chr(i) for i in range(ord('a'), ord('z') + 1)])
        base_chars.extend([chr(i) for i in range(ord('A'), ord('Z') + 1)])
        base_chars.extend([chr(i) for i in range(ord('0'), ord('9') + 1)])
        base_chars.extend('！？。，；：""''（）【】《》……—~～·、')
        base_chars.extend('!?.,;:\"\'()[]{}<>-~@#$%^&*_+=|/\\')
        base_chars.extend(' 😊🎬✨😄❤️🤣😂💕🌟🔥🎉📚🎵🍜☀️💪🎶')
        
        # 添加基础字符
        for char in base_chars:
            if current_id >= self.vocab_size:
                break
            if char not in self.char_to_id:
                self.char_to_id[char] = current_id
                self.id_to_char[current_id] = char
                current_id += 1
    
    # 将文本编码为token id序列
    def encode(self, text: str) -> List[int]:
        tokens = []
        # 特殊处理：检查是否包含特殊token
        i = 0
        while i < len(text):
            # 检查是否以特殊token开头
            found_special = False
            for special_token in ['[EOS]', '[PAD]', '[UNK]']:
                if text.startswith(special_token, i):
                    tokens.append(self.special_tokens[special_token])
                    i += len(special_token)
                    found_special = True
                    break
            
            if not found_special:
                # 普通字符处理
                char = text[i]
                if char in self.char_to_id:
                    tokens.append(self.char_to_id[char])
                else:
                    # 如果字符不在词汇表中，动态添加（如果有空间）
                    if len(self.char_to_id) < self.vocab_size and char not in self.char_to_id:
                        new_id = len(self.char_to_id)
                        self.char_to_id[char] = new_id
                        self.id_to_char[new_id] = char
                        tokens.append(new_id)
                    else:
                        tokens.append(self.special_tokens['[UNK]'])
                i += 1
        
        return tokens
    # 将token id序列解码为文本
    def decode(self, token_ids: List[int], skip_special_tokens: bool = True) -> str:
        
        chars = []
        for token_id in token_ids:
            if token_id in self.id_to_char:
                char = self.id_to_char[token_id]
                
                if skip_special_tokens:
                    # 跳过特殊token
                    if char in ['[PAD]', '[EOS]', '[UNK]']:
                        continue
                else:
                    # 如果要显示特殊token
                    if char in ['[PAD]', '[EOS]', '[UNK]']:
                        # 可以选择显示或不显示
                        if char == '[EOS]':
                            char = ''  # 不显示EOS
                
                chars.append(char)
            else:
                # 未知token ID
                if not skip_special_tokens:
                    chars.append('<?>')
        
        return ''.join(chars)
    
    def get_vocab_size(self) -> int:
        return len(self.char_to_id)

# 创建全局分词器实例
tokenizer = Tokenizer()