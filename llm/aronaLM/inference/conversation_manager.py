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
        self.max_history = max_history
        self.conversation_history = deque(maxlen=max_history)