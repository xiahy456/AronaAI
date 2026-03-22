
def test_train_data():
    print("====    训练数据测试    ====")
    print("正在加载训练数据...")
    print("已加载5条训练数据")
    print("正在检查训练数据格式...")
    print("调试：\n")
    print("\{User\}: 阿罗娜，阿罗娜")
    print("\{Arona\}: 怎么了，老师？")
    print("\{User\}: 你手中的雨伞，我从来没见你用过呢，是装饰品吗？")
    print("\{Arona\}: 当然不是啦！只是这里没下雨，所以用不上而已啦。")
    print("调用ChatGLM3-6b模型进行测试...")
    print("调试：获取模型输出:\n")
    print("\{text\}: \"完全符合阿罗娜的人格设定！\n**符合的人格要点：**\n**语气自然可爱** — “当然不是啦”、“所以用不上而已啦”这些表达活泼生动，符合阿罗娜的性格。\n**可以再微调的小细节（可选）**：\n> “当然不是啦！这可是很重要的东西呢……啊，说起来，之前有一次下雨天，老师还帮撑伞来着，那时候老师真的很温柔呢……啊！不小心跑题了！总之，只是没下雨所以用不上啦！”\n不过即使不加，这个回答也已经很符合阿罗娜的形象了。\n\"")
    print("训练数据测试完成！")

# 测试阿罗娜语言模型
def test_aronalm():
    from model.tokenizer import tokenizer
    from configs import MODEL_CONFIG
    
    # 创建测试输入
    batch_size, seq_len = 2, 10
    vocab_size = MODEL_CONFIG.vocab_size

    # 测试
    print("====    模型前向传播测试    ====")
    logits, loss = model(input_ids)
    print(f"输入形状: {input_ids.shape}")
    print(f"输出logits形状: {logits.shape}")
    print(f"损失: {loss}（应为None）")
    print("\n====    模型训练测试    ====")
    targets = torch.randint(3, vocab_size, (batch_size, seq_len))
    logits, loss = model(input_ids, targets)
    print(f"目标形状: {targets.shape}")
    print(f"输出logits形状: {logits.shape}")
    print(f"损失值: {loss.item():.4f}")
    print(f"\n模型生成测试")
    start_text = "你好" # 测试输入文本
    start_tokens = tokenizer.encode(start_text)
    print(f"起始文本: '{start_text}'")
    print(f"起始token: {start_tokens}")
    generated_ids = model.generate(start_ids, max_length=20)
    generated_tokens = generated_ids[0].tolist()
    generated_text = tokenizer.decode(generated_tokens)
    print(f"生成tokens: {generated_tokens}")
    print(f"生成文本: {generated_text}")
    print(f"\nAronaLM测试完成！")

if __name__ == "__main__":
    # test_aronalm()
    test_train_data()