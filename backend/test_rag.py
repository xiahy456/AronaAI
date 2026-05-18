"""
RAG 数据库操作功能测试脚本
测试以下模块：
1. VectorStore - 向量数据库基础操作
2. KnowledgeVectorStore - 知识库向量存储
3. MemoryVectorStore - 记忆向量存储
4. KnowledgeBase - 知识库管理器（RAG核心）
5. MemoryManager - 记忆管理器
6. SemanticCache - 语义缓存
7. ChainCompressor - 链路压缩
"""
import sys
import os
import time

# 确保 backend 目录在路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.vector_store import VectorStore, KnowledgeVectorStore, MemoryVectorStore
from backend.knowledge_base import KnowledgeBase
from backend.memory_manager import MemoryManager
from backend.semantic_cache import SemanticCache
from backend.chain_compressor import ChainCompressor


def print_separator(title):
    """打印分隔线"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def test_vector_store():
    """测试 VectorStore 基础操作"""
    print_separator("测试 VectorStore 基础操作")

    # 使用测试集合名，避免影响生产数据
    store = VectorStore(collection_name="test_collection")

    # 1. 测试添加文本
    print("\n[测试1] 添加文本...")
    texts = [
        "Arona是一个可爱的AI助手",
        "Arona喜欢帮助用户解决问题",
        "Arona来自一个神奇的世界",
        "Arona拥有强大的知识库",
    ]
    ids = store.add_texts(texts)
    print(f"  添加了 {len(ids)} 条文本")
    print(f"  IDs: {ids}")

    # 2. 测试去重添加
    print("\n[测试2] 测试去重添加...")
    duplicate_ids = store.add_texts(["Arona是一个可爱的AI助手"])
    print(f"  去重后实际添加了 {len(duplicate_ids)} 条 (期望: 0 条新增)")

    # 3. 测试相似度搜索
    print("\n[测试3] 测试相似度搜索...")
    results = store.similarity_search("Arona是谁", k=2)
    print(f"  搜索结果: {len(results)} 条")
    for i, r in enumerate(results):
        print(f"    [{i}] 文本: {r['document'][:50]}...")
        print(f"        距离: {r['distance']:.4f}")

    # 4. 测试获取所有文档
    print("\n[测试4] 测试获取所有文档...")
    all_docs = store.get_all_documents()
    print(f"  文档总数: {len(all_docs)}")

    # 5. 测试计数
    print("\n[测试5] 测试计数...")
    count = store.count()
    print(f"  集合中文档数量: {count}")

    # 6. 测试删除
    print("\n[测试6] 测试删除文档...")
    if ids:
        store.delete_by_ids([ids[0]])
        new_count = store.count()
        print(f"  删除后文档数量: {new_count} (期望: {count - 1})")

    # 7. 清理测试数据
    print("\n[测试7] 清理测试集合...")
    store.clear()
    final_count = store.count()
    print(f"  清理后文档数量: {final_count} (期望: 0)")

    print("\n✅ VectorStore 基础操作测试完成")


def test_knowledge_vector_store():
    """测试 KnowledgeVectorStore"""
    print_separator("测试 KnowledgeVectorStore")

    store = KnowledgeVectorStore()

    # 1. 测试添加知识（自动分块）
    print("\n[测试1] 添加长文本知识（自动分块）...")
    long_text = """
    Arona是一个基于人工智能的虚拟助手，专为提供友好、温暖的对话体验而设计。
    Arona拥有丰富的知识储备，可以回答各种问题，从日常生活到专业知识。
    Arona的设计理念是让每个人都能享受到AI带来的便利，同时保持人性化的交互方式。
    Arona支持多种功能，包括对话、知识问答、记忆管理等。
    Arona的架构基于最新的自然语言处理技术，能够理解复杂的语义和上下文。
    Arona的长期目标是成为用户最信赖的AI伙伴，陪伴用户度过每一天。
    """
    ids = store.add_knowledge(long_text, source="测试文档")
    print(f"  分块数量: {len(ids)}")
    print(f"  分块IDs: {ids}")

    # 2. 测试知识搜索
    print("\n[测试2] 测试知识搜索...")
    results = store.search_knowledge("Arona是什么", k=3)
    print(f"  搜索结果: {len(results)} 条")
    for i, r in enumerate(results):
        print(f"    [{i}] 文本: {r['document'][:60]}...")
        print(f"        来源: {r['metadata'].get('source', 'N/A')}")
        print(f"        距离: {r['distance']:.4f}")

    # 3. 清理
    print("\n[测试3] 清理测试数据...")
    store.clear()
    print("  已清理")

    print("\n✅ KnowledgeVectorStore 测试完成")


def test_memory_vector_store():
    """测试 MemoryVectorStore"""
    print_separator("测试 MemoryVectorStore")

    store = MemoryVectorStore()

    # 1. 测试添加记忆
    print("\n[测试1] 添加记忆...")
    memory_id1 = store.add_memory("用户叫小明，今年25岁", user_id="user_001", memory_type="identity")
    memory_id2 = store.add_memory("用户喜欢编程和玩游戏", user_id="user_001", memory_type="preference")
    memory_id3 = store.add_memory("用户住在北京", user_id="user_001", memory_type="location")
    # 添加另一个用户的记忆
    memory_id4 = store.add_memory("用户叫小红", user_id="user_002", memory_type="identity")
    print(f"  记忆1 ID: {memory_id1}")
    print(f"  记忆2 ID: {memory_id2}")
    print(f"  记忆3 ID: {memory_id3}")
    print(f"  记忆4 (其他用户) ID: {memory_id4}")

    # 2. 测试记忆搜索（按用户过滤）
    print("\n[测试2] 测试记忆搜索（按用户过滤）...")
    results = store.search_memory("用户的信息", user_id="user_001", k=5)
    print(f"  用户 user_001 的记忆: {len(results)} 条 (期望: 3 条)")
    for i, r in enumerate(results):
        print(f"    [{i}] 类型: {r['metadata'].get('memory_type', 'N/A')}")
        print(f"        内容: {r['document']}")

    # 3. 测试获取用户所有记忆
    print("\n[测试3] 测试获取用户所有记忆...")
    user_memories = store.get_user_memories("user_001")
    print(f"  用户 user_001 所有记忆: {len(user_memories)} 条")
    for i, m in enumerate(user_memories):
        print(f"    [{i}] {m['document']}")

    # 4. 清理
    print("\n[测试4] 清理测试数据...")
    store.clear()
    print("  已清理")

    print("\n✅ MemoryVectorStore 测试完成")


def test_knowledge_base():
    """测试 KnowledgeBase（RAG核心功能）"""
    print_separator("测试 KnowledgeBase（RAG核心功能）")

    kb = KnowledgeBase()

    # 1. 测试添加文档
    print("\n[测试1] 添加文档...")
    doc_text = """
    Arona是一个基于人工智能的虚拟助手，由先进的自然语言处理技术驱动。
    Arona可以理解和回答各种问题，从简单的日常对话到复杂的专业知识。
    Arona的设计注重用户体验，提供温暖、友好的交互方式。
    Arona支持长期记忆功能，能够记住用户的偏好和历史对话。
    Arona的知识库可以不断更新和扩展，以提供更准确的信息。
    """
    ids = kb.add_document(doc_text, source="Arona介绍")
    print(f"  添加了 {len(ids)} 个分块")

    # 2. 测试批量添加
    print("\n[测试2] 测试批量添加文档...")
    documents = [
        {"text": "Python是一种高级编程语言，广泛应用于数据科学和人工智能领域。", "source": "编程知识"},
        {"text": "机器学习是人工智能的一个分支，让计算机能够从数据中学习。", "source": "AI知识"},
        {"text": "自然语言处理（NLP）是AI的重要领域，涉及文本理解和生成。", "source": "AI知识"},
    ]
    all_ids = kb.add_documents(documents)
    print(f"  批量添加了 {len(all_ids)} 个分块")

    # 3. 测试检索
    print("\n[测试3] 测试知识检索...")
    results = kb.retrieve("Arona是什么", k=3)
    print(f"  检索结果: {len(results)} 条")
    for i, r in enumerate(results):
        print(f"    [{i}] {r['document'][:60]}...")

    # 4. 测试检索并压缩
    print("\n[测试4] 测试检索并压缩...")
    compressed = kb.retrieve_and_compress("Arona是什么", k=3, max_length=200)
    print(f"  压缩后上下文长度: {len(compressed)} 字符")
    print(f"  压缩后内容: {compressed[:100]}...")

    # 5. 测试获取知识上下文
    print("\n[测试5] 测试获取知识上下文...")
    context = kb.get_knowledge_context("什么是机器学习")
    print(f"  知识上下文: {context[:100]}...")

    # 6. 测试统计
    print("\n[测试6] 测试统计信息...")
    stats = kb.get_stats()
    print(f"  知识库统计: {stats}")

    # 7. 测试列出文档
    print("\n[测试7] 测试列出所有文档...")
    all_docs = kb.list_documents()
    print(f"  文档总数: {len(all_docs)}")

    # 8. 清理
    print("\n[测试8] 清理测试数据...")
    kb.clear()
    print("  已清理")

    print("\n✅ KnowledgeBase 测试完成")


def test_memory_manager():
    """测试 MemoryManager"""
    print_separator("测试 MemoryManager")

    mm = MemoryManager()

    # 1. 测试提取记忆
    print("\n[测试1] 测试从文本中提取记忆...")
    test_texts = [
        "你好，我叫张三，今年28岁",
        "我喜欢打篮球和听音乐",
        "我住在上海，是一名软件工程师",
        "请记住我最喜欢的颜色是蓝色",
        "我养了一只猫叫咪咪",
    ]
    for text in test_texts:
        memories = mm.extract_memories(text)
        print(f"  输入: {text}")
        if memories:
            for m in memories:
                print(f"    -> 提取: [{m['type']}] {m['text']}")
        else:
            print(f"    -> 未提取到记忆")

    # 2. 测试存储记忆
    print("\n[测试2] 测试存储记忆...")
    memory_id = mm.store_memory("用户叫张三，今年28岁", user_id="test_user", memory_type="identity")
    print(f"  存储记忆 ID: {memory_id}")

    # 3. 测试处理对话并自动存储
    print("\n[测试3] 测试对话处理与自动存储...")
    stored_ids = mm.process_and_store(
        "我叫李四，我喜欢画画",
        "很高兴认识你，李四！画画是一个很棒的爱好。",
        user_id="test_user"
    )
    print(f"  自动存储了 {len(stored_ids)} 条记忆")

    # 4. 测试检索记忆
    print("\n[测试4] 测试记忆检索...")
    memories = mm.retrieve_memories("用户的信息", user_id="test_user", k=5)
    print(f"  检索到 {len(memories)} 条记忆")
    for i, m in enumerate(memories):
        print(f"    [{i}] [{m['metadata'].get('memory_type', 'N/A')}] {m['document']}")

    # 5. 测试获取记忆上下文
    print("\n[测试5] 测试获取记忆上下文...")
    context = mm.get_memory_context("用户的信息", user_id="test_user")
    print(f"  记忆上下文:\n{context}")

    # 6. 测试获取所有记忆
    print("\n[测试6] 测试获取所有记忆...")
    all_memories = mm.get_all_memories("test_user")
    print(f"  用户所有记忆: {len(all_memories)} 条")

    # 7. 清理
    print("\n[测试7] 清理测试数据...")
    mm.clear_user_memories("test_user")
    remaining = mm.get_all_memories("test_user")
    print(f"  清理后剩余: {len(remaining)} 条 (期望: 0)")

    print("\n✅ MemoryManager 测试完成")


def test_semantic_cache():
    """测试 SemanticCache"""
    print_separator("测试 SemanticCache")

    cache = SemanticCache()

    # 1. 测试存储缓存
    print("\n[测试1] 测试存储缓存...")
    cache.set("Arona是谁", "Arona是一个可爱的AI助手", "相关知识上下文")
    cache.set("今天天气怎么样", "今天天气晴朗，温度适宜", "天气信息")
    print("  已存储2条缓存")

    # 2. 测试精确命中
    print("\n[测试2] 测试精确命中...")
    result = cache.get("Arona是谁")
    if result:
        print(f"  ✅ 命中缓存! 回复: {result['response']}")
        print(f"     相似度: {result['similarity']:.4f}")
    else:
        print("  ❌ 未命中缓存")

    # 3. 测试语义相似命中
    print("\n[测试3] 测试语义相似命中...")
    result = cache.get("请问Arona是什么")
    if result:
        print(f"  ✅ 命中缓存! 回复: {result['response']}")
        print(f"     相似度: {result['similarity']:.4f}")
    else:
        print("  ❌ 未命中缓存")

    # 4. 测试不相关查询（应不命中）
    print("\n[测试4] 测试不相关查询（应不命中）...")
    result = cache.get("如何学习编程")
    if result:
        print(f"  ❌ 不应命中但命中了: {result['response']}")
    else:
        print("  ✅ 正确未命中（不相关查询）")

    # 5. 测试缓存统计
    print("\n[测试5] 测试缓存统计...")
    stats = cache.get_stats()
    print(f"  缓存统计: {stats}")

    # 6. 测试使缓存失效
    print("\n[测试6] 测试缓存失效...")
    cache.invalidate("Arona是谁")
    result = cache.get("Arona是谁")
    if result:
        print("  ❌ 缓存未失效")
    else:
        print("  ✅ 缓存已成功失效")

    # 7. 清理
    print("\n[测试7] 清理缓存...")
    cache.clear()
    stats = cache.get_stats()
    print(f"  清理后缓存大小: {stats['size']} (期望: 0)")

    print("\n✅ SemanticCache 测试完成")


def test_chain_compressor():
    """测试 ChainCompressor"""
    print_separator("测试 ChainCompressor")

    compressor = ChainCompressor()

    # 1. 测试基本压缩
    print("\n[测试1] 测试基本压缩...")
    documents = [
        {"document": "Arona是一个基于人工智能的虚拟助手，由先进的自然语言处理技术驱动。", "metadata": {}, "distance": 0.1},
        {"document": "Arona可以理解和回答各种问题，从简单的日常对话到复杂的专业知识。", "metadata": {}, "distance": 0.2},
        {"document": "Arona的设计注重用户体验，提供温暖、友好的交互方式。", "metadata": {}, "distance": 0.3},
        {"document": "Arona支持长期记忆功能，能够记住用户的偏好和历史对话。", "metadata": {}, "distance": 0.4},
        {"document": "Arona的知识库可以不断更新和扩展，以提供更准确的信息。", "metadata": {}, "distance": 0.5},
    ]
    compressed = compressor.compress(documents, "Arona是什么", max_length=300)
    print(f"  压缩后长度: {len(compressed)} 字符")
    print(f"  压缩后内容:\n{compressed}")

    # 2. 测试去重
    print("\n[测试2] 测试去重...")
    duplicate_docs = documents + [documents[0], documents[1]]
    compressed_dedup = compressor.compress(duplicate_docs, "Arona是什么", max_length=500)
    print(f"  去重后长度: {len(compressed_dedup)} 字符")

    # 3. 测试提取关键信息
    print("\n[测试3] 测试提取关键信息...")
    long_text = "我叫小明，今年25岁，是一名软件工程师。我喜欢编程和玩游戏。我住在北京，养了一只猫。"
    key_info = compressor.extract_key_info(long_text, max_length=50)
    print(f"  原始文本: {long_text}")
    print(f"  提取关键信息: {key_info}")

    # 4. 测试复杂度评分
    print("\n[测试4] 测试查询复杂度评分...")
    test_queries = [
        ("你好", "简单查询"),
        ("为什么天空是蓝色的", "中等复杂度"),
        ("请详细分析机器学习和深度学习的主要区别以及各自的优缺点", "复杂查询"),
    ]
    for query, desc in test_queries:
        score = compressor._complexity_score(query)
        print(f"  [{desc}] '{query}' -> 复杂度评分: {score}")

    print("\n✅ ChainCompressor 测试完成")


def test_integration():
    """测试 RAG 集成流程"""
    print_separator("测试 RAG 集成流程")

    print("\n模拟完整的 RAG 工作流程...\n")

    # 1. 初始化组件
    kb = KnowledgeBase()
    mm = MemoryManager()
    cache = SemanticCache()

    # 2. 添加知识
    print("[步骤1] 添加知识到知识库...")
    kb.add_document(
        "Arona是一个基于AI的虚拟助手，由先进的自然语言处理技术驱动。"
        "Arona可以理解和回答各种问题，提供温暖友好的交互体验。"
        "Arona支持长期记忆功能，能够记住用户的偏好和历史对话。",
        source="Arona介绍"
    )
    kb.add_document(
        "机器学习是人工智能的核心分支，让计算机从数据中学习。"
        "深度学习是机器学习的一个子集，使用多层神经网络。"
        "自然语言处理（NLP）让计算机理解和生成人类语言。",
        source="AI知识"
    )
    print(f"  知识库文档数: {kb.count()}")

    # 3. 模拟用户对话
    print("\n[步骤2] 模拟用户对话...")
    user_inputs = [
        "你好，我叫小明",
        "Arona是什么",
        "什么是机器学习",
        "你还记得我叫什么吗",
    ]

    for user_input in user_inputs:
        print(f"\n  用户: {user_input}")

        # 检查缓存
        cached = cache.get(user_input)
        if cached:
            print(f"  [缓存命中] Arona: {cached['response']}")
            continue

        # 检索知识
        knowledge_context = kb.get_knowledge_context(user_input)
        if knowledge_context:
            print(f"  [知识检索] 找到相关知识")

        # 检索记忆
        memory_context = mm.get_memory_context(user_input, user_id="integration_test")
        if memory_context:
            print(f"  [记忆检索] 找到相关记忆")

        # 模拟回复
        response = f"你好！我是Arona，很高兴为你服务。"
        print(f"  [生成回复] Arona: {response}")

        # 存储到缓存
        cache.set(user_input, response, knowledge_context)

        # 处理记忆
        stored = mm.process_and_store(user_input, response, user_id="integration_test")
        if stored:
            print(f"  [记忆存储] 存储了 {len(stored)} 条记忆")

    # 4. 验证记忆
    print("\n[步骤3] 验证记忆功能...")
    memories = mm.get_all_memories("integration_test")
    print(f"  用户记忆数量: {len(memories)}")
    for m in memories:
        print(f"    [{m['metadata'].get('memory_type', 'N/A')}] {m['document']}")

    # 5. 清理
    print("\n[步骤4] 清理测试数据...")
    kb.clear()
    mm.clear_user_memories("integration_test")
    cache.clear()
    print("  所有测试数据已清理")

    print("\n✅ RAG 集成测试完成")


def main():
    """运行所有测试"""
    print("=" * 60)
    print("  RAG 数据库操作功能测试")
    print("=" * 60)
    print(f"  开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Python: {sys.version}")

    tests = [
        ("VectorStore 基础操作", test_vector_store),
        ("KnowledgeVectorStore", test_knowledge_vector_store),
        ("MemoryVectorStore", test_memory_vector_store),
        ("KnowledgeBase (RAG核心)", test_knowledge_base),
        ("MemoryManager", test_memory_manager),
        ("SemanticCache", test_semantic_cache),
        ("ChainCompressor", test_chain_compressor),
        ("RAG 集成测试", test_integration),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            test_func()
            passed += 1
            print(f"\n  ✅ {name} 测试通过")
        except Exception as e:
            failed += 1
            print(f"\n  ❌ {name} 测试失败: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print(f"  测试结果汇总")
    print("=" * 60)
    print(f"  总测试数: {len(tests)}")
    print(f"  通过: {passed}")
    print(f"  失败: {failed}")
    print(f"  结束时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
