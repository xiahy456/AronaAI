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
    def __init__(self, vocab_size=MODEL_CONFIG.vocab_size):
        self.vocab_size = vocab_size
        self.cutter = cutword.Cutter()
        self.char_to_id = {}
        self.id_to_char = {}
        self._build_vocab()
        print(f"CutWord分词器初始化完成，词汇表大小: {self.get_vocab_size()}")
    
    # 构建词汇表
    def _build_vocab(self):
        # 特殊token
        special_tokens = {
            MODEL_CONFIG.pad_token_id: '[PAD]',
            MODEL_CONFIG.eos_token_id: '[EOS]', 
            MODEL_CONFIG.unk_token_id: '[UNK]'
        }
        
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
        
        # 构建映射表
        current_id = len(special_tokens)
        
        # 添加特殊token
        for token, token_id in special_tokens.items():
            self.char_to_id[token] = token_id
            self.id_to_char[token_id] = token
        
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
        # 使用cutword分词
        words = self.cutter.cutword(text)
        tokens = []
        
        for word in words:
            # 对每个词中的字符进行编码
            for char in word:
                if char in self.char_to_id:
                    tokens.append(self.char_to_id[char])
                else:
                    # 如果字符不在词汇表中，添加到词汇表（如果还有空间）
                    if len(self.char_to_id) < self.vocab_size:
                        new_id = len(self.char_to_id)
                        self.char_to_id[char] = new_id
                        self.id_to_char[new_id] = char
                        tokens.append(new_id)
                    else:
                        tokens.append(MODEL_CONFIG.unk_token_id)
                        print(f"警告: 字符 '{char}' 不在词汇表中，使用[UNK]替代")
        
        return tokens
    
    # 将token id序列解码为文本
    def decode(self, token_ids: List[int]) -> str:
        
        chars = []
        for token_id in token_ids:
            if token_id in self.id_to_char:
                char = self.id_to_char[token_id]
                # 跳过特殊token（除了显示调试）
                if char not in ['[PAD]', '[EOS]', '[UNK]']:
                    chars.append(char)
                elif char == '[UNK]':
                    chars.append('?')  # 用?表示未知字符
        return ''.join(chars)
    
    def get_vocab_size(self) -> int:
        return len(self.char_to_id)

# 创建全局分词器实例
tokenizer = Tokenizer()