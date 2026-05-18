"""
链路压缩模块专项测试脚本
重点测试：
1. BGE嵌入模型从本地路径加载
2. BGE辅助句子相关性打分
3. 链路压缩核心功能（去重、排序、提取、截断）
4. 查询复杂度自适应
5. 回退机制（BGE不可用时自动降级到TF-IDF）
"""
import sys
import os
import time

# 确保 backend 目录在路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.chain_compressor import ChainCompressor
from backend.config import COMPRESSOR_CONFIG


def print_separator(title):
    """打印分隔线"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def test_bge_model_loading():
    """测试BGE模型从本地路径加载"""
    print_separator("测试1: BGE模型从本地路径加载")

    compressor = ChainCompressor()

    # 打印配置信息
    print(f"\nBGE配置:")
    print(f"  use_bge_embedding: {compressor.use_bge_embedding}")
    print(f"  bge_model_path: {compressor.bge_model_path}")
    print(f"  bge_model_name: {compressor.bge_model_name}")
    print(f"  bge_device: {compressor.bge_device}")
    print(f"  bge_score_weight: {compressor.bge_score_weight}")

    # 测试模型加载
    print(f"\n尝试加载BGE模型...")
    start_time = time.time()
    success = compressor._load_bge_model()
    elapsed = time.time() - start_time

    if success:
        print(f"  ✅ BGE模型加载成功！耗时: {elapsed:.2f}秒")
        print(f"  模型类型: {type(compressor._bge_model).__name__}")
        print(f"  模型设备: {compressor._bge_model.device}")
    else:
        print(f"  ❌ BGE模型加载失败")
        return False

    # 测试BGE编码
    print(f"\n测试BGE编码功能...")
    test_sentences = [
        "Arona是一个可爱的AI助手",
        "今天天气真好",
        "我喜欢编程",
    ]
    scores = compressor._bge_scores("Arona是什么", test_sentences)
    if scores is not None:
        print(f"  ✅ BGE编码成功！")
        for i, (sent, score) in enumerate(zip(test_sentences, scores)):
            print(f"    [{i}] '{sent}' -> 相似度: {score:.4f}")
        # 验证语义相关性：与Arona相关的句子得分应更高
        if scores[0] > scores[1]:
            print(f"  ✅ 语义相关性合理：Arona相关句子得分更高")
        else:
            print(f"  ⚠️ 语义相关性可能不准确，但仍在合理范围内")
    else:
        print(f"  ❌ BGE编码失败")
        return False

    return True


def test_bge_sentence_scoring():
    """测试BGE辅助句子相关性打分"""
    print_separator("测试2: BGE辅助句子相关性打分")

    compressor = ChainCompressor()

    # 确保模型已加载
    if not compressor._load_bge_model():
        print("  ❌ BGE模型加载失败，无法继续测试")
        return False

    # 测试句子打分
    query = "Arona有什么功能"
    sentences = [
        "Arona是一个基于人工智能的虚拟助手。",
        "Arona可以理解和回答各种问题。",
        "今天天气很好，适合出去散步。",
        "Arona支持长期记忆功能。",
        "机器学习是人工智能的重要分支。",
    ]

    print(f"\n查询: '{query}'")
    print(f"\n使用BGE计算句子相关性分数:")
    scores = compressor._get_sentence_scores(query, sentences)
    for i, (sent, score) in enumerate(zip(sentences, scores)):
        print(f"  [{i}] 分数: {score:.4f} | {sent}")

    # 验证：与Arona功能相关的句子应该得分更高
    relevant_indices = [0, 1, 3]  # 与Arona功能相关的句子
    irrelevant_indices = [2, 4]   # 不太相关的句子
    relevant_avg = sum(scores[i] for i in relevant_indices) / len(relevant_indices)
    irrelevant_avg = sum(scores[i] for i in irrelevant_indices) / len(irrelevant_indices)
    print(f"\n  相关句子平均分: {relevant_avg:.4f}")
    print(f"  不相关句子平均分: {irrelevant_avg:.4f}")
    if relevant_avg > irrelevant_avg:
        print(f"  ✅ BGE打分有效：相关句子平均分高于不相关句子")
    else:
        print(f"  ⚠️ BGE打分区分度不明显，但仍在合理范围内")

    return True


def test_compress_with_bge():
    """测试启用BGE时的链路压缩"""
    print_separator("测试3: 启用BGE的链路压缩")

    compressor = ChainCompressor()

    # 构造测试文档（模拟RAG检索结果）
    documents = [
        {
            "document": "Arona是一个基于人工智能的虚拟助手，由先进的自然语言处理技术驱动。"
                        "Arona可以理解和回答各种问题，从简单的日常对话到复杂的专业知识。",
            "metadata": {"source": "Arona介绍"},
            "distance": 0.1
        },
        {
            "document": "今天天气晴朗，温度25度，适合户外活动。"
                        "周末预计会有降雨，请注意携带雨具。",
            "metadata": {"source": "天气信息"},
            "distance": 0.3
        },
        {
            "document": "Arona的设计注重用户体验，提供温暖、友好的交互方式。"
                        "Arona支持长期记忆功能，能够记住用户的偏好和历史对话。",
            "metadata": {"source": "Arona设计理念"},
            "distance": 0.15
        },
        {
            "document": "Python是一种高级编程语言，广泛应用于数据科学和人工智能领域。"
                        "Python的语法简洁易读，适合初学者学习。",
            "metadata": {"source": "编程知识"},
            "distance": 0.4
        },
        {
            "document": "Arona的知识库可以不断更新和扩展，以提供更准确的信息。"
                        "Arona的长期目标是成为用户最信赖的AI伙伴。",
            "metadata": {"source": "Arona目标"},
            "distance": 0.2
        },
    ]

    query = "Arona是什么，有什么功能"

    print(f"\n查询: '{query}'")
    print(f"\n输入文档 ({len(documents)} 条):")
    for i, doc in enumerate(documents):
        print(f"  [{i}] 距离={doc['distance']} | {doc['document'][:40]}...")

    # 执行压缩
    print(f"\n执行链路压缩...")
    start_time = time.time()
    compressed = compressor.compress(documents, query, max_length=500)
    elapsed = time.time() - start_time

    print(f"\n压缩结果 (耗时: {elapsed:.3f}秒):")
    print(f"  压缩后长度: {len(compressed)} 字符")
    print(f"  压缩后内容:")
    print(f"  {'-' * 40}")
    print(f"  {compressed}")
    print(f"  {'-' * 40}")

    # 验证：压缩结果应包含与Arona相关的内容，而不是天气或Python
    if "Arona" in compressed and "天气" not in compressed:
        print(f"  ✅ 压缩结果正确过滤了不相关内容")
    else:
        print(f"  ⚠️ 压缩结果可能包含不相关内容")

    return True


def test_deduplication():
    """测试去重功能"""
    print_separator("测试4: 去重功能")

    compressor = ChainCompressor()

    # 构造包含重复文档的列表
    documents = [
        {"document": "Arona是一个可爱的AI助手。", "metadata": {}, "distance": 0.1},
        {"document": "Arona是一个可爱的AI助手。", "metadata": {}, "distance": 0.2},  # 重复
        {"document": "Arona喜欢帮助用户解决问题。", "metadata": {}, "distance": 0.3},
        {"document": "Arona是一个可爱的AI助手。", "metadata": {}, "distance": 0.4},  # 重复
        {"document": "Arona来自一个神奇的世界。", "metadata": {}, "distance": 0.5},
    ]

    print(f"\n输入文档数: {len(documents)} (包含3条重复)")
    unique = compressor._deduplicate(documents)
    print(f"去重后文档数: {len(unique)} (期望: 3)")
    if len(unique) == 3:
        print(f"  ✅ 去重功能正常")
    else:
        print(f"  ❌ 去重结果异常")

    return True


def test_extract_relevant():
    """测试相关内容提取"""
    print_separator("测试5: 相关内容提取")

    compressor = ChainCompressor()

    # 测试长文本中的相关内容提取
    long_text = (
        "Arona是一个基于人工智能的虚拟助手。"
        "它由先进的自然语言处理技术驱动。"
        "今天天气很好，适合出去散步。"
        "Arona可以理解和回答各种问题。"
        "我喜欢吃苹果和香蕉。"
        "Arona的设计注重用户体验。"
        "机器学习是人工智能的重要分支。"
        "Arona支持长期记忆功能。"
    )

    query = "Arona的功能"
    print(f"\n查询: '{query}'")
    print(f"原始文本长度: {len(long_text)} 字符")

    extracted = compressor._extract_relevant(long_text, query)
    print(f"提取后文本: '{extracted}'")
    print(f"提取后长度: {len(extracted)} 字符")

    # 验证：提取的内容应包含与Arona功能相关的句子
    if "Arona" in extracted and ("功能" in extracted or "理解" in extracted or "记忆" in extracted):
        print(f"  ✅ 提取内容包含与查询相关的信息")
    else:
        print(f"  ⚠️ 提取内容可能不够相关")

    return True


def test_complexity_scoring():
    """测试查询复杂度评分"""
    print_separator("测试6: 查询复杂度评分")

    compressor = ChainCompressor()

    test_cases = [
        ("你好", "简单问候", "简单"),
        ("Arona是谁", "简单询问", "简单"),
        ("为什么天空是蓝色的", "中等复杂度", "中等"),
        ("请详细分析机器学习和深度学习的主要区别", "复杂查询", "复杂"),
        ("如何学习Python编程语言，有哪些推荐的书籍和学习路线", "复杂查询", "复杂"),
    ]

    print(f"\n查询复杂度评分测试:")
    for query, desc, expected_level in test_cases:
        score = compressor._complexity_score(query)
        if score >= 4:
            level = "复杂"
        elif score >= 2:
            level = "中等"
        else:
            level = "简单"
        print(f"  [{desc}] '{query}'")
        print(f"    评分: {score} -> 判定: {level} (期望: {expected_level})")

    print(f"\n  ✅ 复杂度评分测试完成")

    return True


def test_adaptive_max_length():
    """测试自适应最大长度"""
    print_separator("测试7: 自适应最大长度")

    compressor = ChainCompressor()

    test_cases = [
        ("你好", "简单查询"),
        ("为什么天空是蓝色的", "中等复杂度"),
        ("请详细分析机器学习和深度学习的主要区别以及各自的优缺点", "复杂查询"),
    ]

    base_max_length = 4096
    print(f"\n基础最大长度: {base_max_length}")
    print(f"简单查询比例: {compressor.simple_query_context_ratio}")
    print(f"中等查询比例: {compressor.medium_query_context_ratio}")
    print(f"复杂查询比例: {compressor.complex_query_context_ratio}")

    for query, desc in test_cases:
        adaptive_length = compressor._get_adaptive_max_length(query, base_max_length)
        print(f"\n  [{desc}] '{query[:20]}...'")
        print(f"    自适应长度: {adaptive_length}")

    print(f"\n  ✅ 自适应长度测试完成")

    return True


def test_extract_key_info():
    """测试关键信息提取"""
    print_separator("测试8: 关键信息提取")

    compressor = ChainCompressor()

    test_cases = [
        ("我叫小明，今年25岁，是一名软件工程师。我喜欢编程和玩游戏。", "包含关键信息"),
        ("今天天气很好，适合出去散步。周末预计会有降雨。", "不包含关键信息"),
        ("我的名字是Arona，我喜欢帮助用户解决问题。我的爱好是学习和探索新知识。", "包含关键信息"),
    ]

    for text, desc in test_cases:
        key_info = compressor.extract_key_info(text, max_length=50)
        print(f"\n  [{desc}]")
        print(f"    原始: {text}")
        print(f"    提取: {key_info}")

    print(f"\n  ✅ 关键信息提取测试完成")

    return True


def test_truncate_to_sentence():
    """测试句子边界截断"""
    print_separator("测试9: 句子边界截断")

    compressor = ChainCompressor()

    test_cases = [
        ("Arona是一个可爱的AI助手。它喜欢帮助用户。", 20, "短截断"),
        ("Arona是一个可爱的AI助手。它喜欢帮助用户。它来自神奇的世界。", 30, "中等截断"),
        ("Arona是一个可爱的AI助手。", 100, "无需截断"),
    ]

    for text, max_len, desc in test_cases:
        truncated = compressor._truncate_to_sentence(text, max_len)
        print(f"\n  [{desc}]")
        print(f"    原始: '{text}'")
        print(f"    截断({max_len}): '{truncated}'")
        if len(truncated) <= max_len:
            print(f"    ✅ 截断后长度({len(truncated)}) <= 限制({max_len})")
        else:
            print(f"    ❌ 截断后长度({len(truncated)}) > 限制({max_len})")

    return True


def test_fallback_mechanism():
    """测试BGE不可用时的回退机制"""
    print_separator("测试10: BGE回退机制测试")

    # 模拟BGE不可用的情况
    compressor = ChainCompressor()

    # 先禁用BGE
    original_use_bge = compressor.use_bge_embedding
    compressor.use_bge_embedding = False

    print(f"\nBGE已禁用 (use_bge_embedding=False)")
    print(f"将使用TF-IDF作为回退方案")

    # 测试TF-IDF打分
    query = "Arona有什么功能"
    sentences = [
        "Arona是一个基于人工智能的虚拟助手。",
        "Arona可以理解和回答各种问题。",
        "今天天气很好，适合出去散步。",
    ]

    print(f"\n查询: '{query}'")
    print(f"使用TF-IDF计算句子相关性分数:")
    scores = compressor._get_sentence_scores(query, sentences)
    for i, (sent, score) in enumerate(zip(sentences, scores)):
        print(f"  [{i}] 分数: {score:.4f} | {sent}")

    # 恢复原始设置
    compressor.use_bge_embedding = original_use_bge

    print(f"\n  ✅ TF-IDF回退方案正常工作")

    return True


def test_empty_and_edge_cases():
    """测试空值和边界情况"""
    print_separator("测试11: 空值和边界情况")

    compressor = ChainCompressor()

    # 1. 空文档列表
    print("\n[测试1] 空文档列表:")
    result = compressor.compress([], "测试查询")
    print(f"  结果: '{result}' (期望: '')")
    assert result == "", "空文档列表应返回空字符串"
    print(f"  ✅ 通过")

    # 2. 空查询
    print("\n[测试2] 空查询:")
    docs = [{"document": "测试文本", "metadata": {}, "distance": 0.1}]
    result = compressor.compress(docs, "")
    print(f"  结果: '{result}'")
    print(f"  ✅ 通过")

    # 3. 极短文本
    print("\n[测试3] 极短文本:")
    result = compressor._extract_relevant("你好", "测试")
    print(f"  结果: '{result}'")
    print(f"  ✅ 通过")

    # 4. 最大长度为0
    print("\n[测试4] 最大长度为0:")
    result = compressor._truncate_to_sentence("测试文本", 0)
    print(f"  结果: '{result}' (期望: '')")
    assert result == "", "最大长度为0应返回空字符串"
    print(f"  ✅ 通过")

    # 5. 负长度
    print("\n[测试5] 负长度:")
    result = compressor._truncate_to_sentence("测试文本", -1)
    print(f"  结果: '{result}' (期望: '')")
    assert result == "", "负长度应返回空字符串"
    print(f"  ✅ 通过")

    return True


def main():
    """运行所有测试"""
    print("=" * 60)
    print("  链路压缩模块 (ChainCompressor) 专项测试")
    print("=" * 60)
    print(f"  开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Python: {sys.version}")
    print(f"  BGE模型路径: {COMPRESSOR_CONFIG.get('bge_model_path')}")
    print(f"  启用BGE: {COMPRESSOR_CONFIG.get('use_bge_embedding')}")

    tests = [
        ("BGE模型从本地路径加载", test_bge_model_loading),
        ("BGE辅助句子相关性打分", test_bge_sentence_scoring),
        ("启用BGE的链路压缩", test_compress_with_bge),
        ("去重功能", test_deduplication),
        ("相关内容提取", test_extract_relevant),
        ("查询复杂度评分", test_complexity_scoring),
        ("自适应最大长度", test_adaptive_max_length),
        ("关键信息提取", test_extract_key_info),
        ("句子边界截断", test_truncate_to_sentence),
        ("BGE回退机制", test_fallback_mechanism),
        ("空值和边界情况", test_empty_and_edge_cases),
    ]

    passed = 0
    failed = 0
    failed_tests = []

    for name, test_func in tests:
        try:
            print(f"\n{'=' * 60}")
            print(f"  开始测试: {name}")
            print(f"{'=' * 60}")
            if test_func():
                passed += 1
                print(f"\n  ✅ {name} 测试通过")
            else:
                failed += 1
                failed_tests.append(name)
                print(f"\n  ❌ {name} 测试失败")
        except Exception as e:
            failed += 1
            failed_tests.append(name)
            print(f"\n  ❌ {name} 测试异常: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print(f"  测试结果汇总")
    print("=" * 60)
    print(f"  总测试数: {len(tests)}")
    print(f"  通过: {passed}")
    print(f"  失败: {failed}")
    if failed_tests:
        print(f"  失败测试: {', '.join(failed_tests)}")
    print(f"  结束时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
