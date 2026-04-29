from arona_engine import AronaEngine
import sys
import os
import time

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

engine = AronaEngine()
response = engine.chat("你好", session_id="session_001")
print("模型回复:", response["response"])