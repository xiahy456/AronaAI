import sys
import os
import torch
# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def test_trained_conversation():
    """测试训练后的对话能力"""
    print("=== 测试训练后的对话 ===")
    
    from model.aronalm import AronaLM
    from inference.conversation_manager import ConversationManager
    
    # 1. 创建模型并加载训练权重
    model = AronaLM()
    
    # 检查是否有训练好的模型
    checkpoint_path = "llm/aronaLM/checkpoints/best_model.pt"
    if os.path.exists(checkpoint_path):
        print(f"加载训练好的模型: {checkpoint_path}")
        model.load_state_dict(torch.load(checkpoint_path, map_location='cpu'))
    else:
        print("【!】没有找到训练好的模型，使用随机初始化模型")
    
    # 2. 创建对话管理器
    chat_manager = ConversationManager(model, max_history=8)
    
    # 3. 测试对话
    test_dialogue = [
        "你好",
        "今天需要继续处理来自千禧年科技学院的文件"
    ]
    
    for user_input in test_dialogue:
        print(f"\n老师: {user_input}")
        response = chat_manager.chat(user_input)
        print(f"阿罗娜: {response}")
    
    print(f"\n{chat_manager.get_history_summary()}")

if __name__ == "__main__":
    test_trained_conversation()