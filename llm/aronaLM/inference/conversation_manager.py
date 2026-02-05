import torch
from typing import List, Dict, Deque
from collections import deque
import sys
import os
# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from model.aronalm import AronaLM
from model.tokenizer import tokenizer
from configs import MODEL_CONFIG

class ConversationManager:
    def __init__(self, model: AronaLM, max_history: int = 16):
        self.model = model
        self.model.eval()
        self.max_history = model.config.max_history
        self.conversation_history = deque(maxlen=max_history)
    
    def add_to_history(self, role: str, content: str):
        # 添加对话到历史
        self.conversation_history.append({"role": role, "content": content})
    
    def get_context(self, user_input: str, include_persona: bool = True) -> str:
        # 构建对话上下文
        context_parts = []
        # 添加对话历史
        for turn in self.conversation_history:
            role_display = "User" if turn["role"] == "User" else "Arona"
            context_parts.append(f"{role_display}: {turn['content']}")
        # 添加当前输入
        context_parts.append(f"User: {user_input}")
        context_parts.append("Arona:")
        return " ".join(context_parts)
    
    def chat(self, user_input: str, max_length: int = 50) -> str:
        # 进行连续对话
        # 添加用户输入到历史
        self.add_to_history("User", user_input)
        # 构建上下文
        context = self.get_context(user_input)
        # 编码并生成回复
        context_ids = tokenizer.encode(context)
        input_ids = torch.tensor([context_ids], dtype=torch.long)
        with torch.no_grad():
            generated_ids = self.model.generate(input_ids, max_length=len(context_ids) + max_length)
            response_ids = generated_ids[0, len(context_ids):].tolist()
            response = tokenizer.decode(response_ids)
        # 清理回复（移除可能的重复内容）
        response = self._clean_response(response)
        # 添加助手回复到历史
        self.add_to_history("Arona", response)
        return response
    
    def _clean_response(self, response: str) -> str:
        # 清理生成的回复
        # 移除可能的重复上下文
        if "Arona:" in response:
            response = response.split("Arona:")[-1]
        # 移除EOS token
        response = response.replace("[EOS]", "").strip()
        return response
    
    def save_conversation(self, filepath: str):
        # 保存对话历史
        import json
        data = {
            "conversation_history": list(self.conversation_history)
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def load_conversation(self, filepath: str):
        # 加载对话历史
        import json
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.conversation_history = deque(data.get("conversation_history", []), maxlen=self.max_history)
    
    def clear_history(self):
        # 清空对话历史
        self.conversation_history.clear()
    
    def get_history_summary(self) -> str:
        # 获取对话历史摘要
        return f"当前有 {len(self.conversation_history)} 轮对话记录"