"""
Arona AI 后端测试脚本
测试所有模块的功能是否正常
"""
import sys
import os
import time

# 设置控制台编码为UTF-8
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_config():
    """测试配置模块"""
    print("\n" + "=" * 60)
    print("测试配置模块...")
    from backend.config import (
        MODEL_CONFIG, VECTOR_DB_CONFIG, CACHE_CONFIG,
        CONVERSATION_CONFIG, MEMORY_CONFIG, DATA_DIR
    )
    print(f"  模型路径: {MODEL_CONFIG['base_model_name']}")
    print(f"  LoRA路径: {MODEL_CONFIG['lora_path']}")
    print(f"  向量数据库目录: {VECTOR_DB_CONFIG['persist_directory']}")
    print(f"  缓存目录: {CACHE_CONFIG['cache_dir']}")
    print(f"  数据目录: {DATA_DIR}")
    print("  ✓ 配置模块测试通过")


def test_vector_store():
    """测试向量数据库"""
    print("\n" + "=" * 60)
    print("测试向量数据库...")
    from backend.vector_store import KnowledgeVectorStore, MemoryVectorStore

    # 测试知识库向量存储
    kv = KnowledgeVectorStore()
    print(f"  知识库集合: {kv.collection_name}")

    # 添加测试数据
    test_text = "阿罗娜是什亭之匣的管理员，来自基沃托斯。"
    ids = kv.add_knowledge(test_text, source="test")
    print(f"  添加知识文档: {ids}")

    # 搜索测试
    results = kv.search_knowledge("阿罗娜是谁", k=2)
    print(f"  搜索结果数: {len(results)}")
    if results:
        print(f"  搜索结果: {results[0]['document'][:50]}...")

    # 测试记忆向量存储
    mv = MemoryVectorStore()
    print(f"  记忆集合: {mv.collection_name}")

    mem_id = mv.add_memory("用户叫小明", user_id="test_user")
    print(f"  添加记忆: {mem_id}")

    mem_results = mv.search_memory("用户名字", user_id="test_user")
    print(f"  记忆搜索结果数: {len(mem_results)}")

    print("  ✓ 向量数据库测试通过")


def test_semantic_cache():
    """测试语义缓存"""
    print("\n" + "=" * 60)
    print("测试语义缓存...")
    from backend.semantic_cache import SemanticCache

    cache = SemanticCache()
    print(f"  缓存大小: {cache.get_stats()['size']}")

    # 测试设置和获取
    cache.set("你好，阿罗娜", "你好呀！老师！", context="")
    result = cache.get("你好，阿罗娜")
    assert result is not None, "缓存命中失败"
    print(f"  精确匹配: {result['response']}")

    # 测试语义相似匹配
    result2 = cache.get("你好阿罗娜")
    if result2:
        print(f"  语义匹配: {result2['response']} (相似度: {result2.get('similarity', 0):.3f})")

    # 测试不相关查询
    result3 = cache.get("今天天气怎么样")
    assert result3 is None, "不相关查询不应命中缓存"
    print("  不相关查询未命中缓存 ✓")

    cache.clear()
    print("  ✓ 语义缓存测试通过")


def test_conversation_manager():
    """测试对话管理"""
    print("\n" + "=" * 60)
    print("测试对话管理...")
    from backend.conversation_manager import ConversationManager

    cm = ConversationManager()
    session_id = cm.create_session("test_session")
    print(f"  创建会话: {session_id}")

    # 添加消息
    cm.add_message(session_id, "user", "你好")
    cm.add_message(session_id, "assistant", "你好呀！")
    cm.add_message(session_id, "user", "今天天气真好")
    cm.add_message(session_id, "assistant", "是啊，老师！")

    history = cm.get_history(session_id)
    print(f"  历史消息数: {len(history)}")

    recent = cm.get_recent_history(session_id, turns=1)
    print(f"  最近1轮消息数: {len(recent)}")

    cm.clear_session(session_id)
    print("  ✓ 对话管理测试通过")


def test_chain_compressor():
    """测试链路压缩"""
    print("\n" + "=" * 60)
    print("测试链路压缩...")
    from backend.chain_compressor import ChainCompressor

    compressor = ChainCompressor()

    # 测试文档压缩
    documents = [
        {"document": "阿罗娜是什亭之匣的管理员，她来自基沃托斯。她非常可爱，喜欢帮助老师。", "distance": 0.1},
        {"document": "基沃托斯是一个充满希望的地方，这里有各种各样的学生和社团。", "distance": 0.3},
        {"document": "什亭之匣是一个神秘的道具，里面住着阿罗娜。", "distance": 0.2},
    ]

    compressed = compressor.compress(documents, "阿罗娜是谁")
    print(f"  压缩后长度: {len(compressed)} 字符")
    print(f"  压缩内容: {compressed[:100]}...")

    # 测试关键信息提取
    key_info = compressor.extract_key_info(
        "我叫小明，今年18岁，我喜欢打篮球和听音乐。我住在北京。",
        max_length=50
    )
    print(f"  关键信息: {key_info}")

    print("  ✓ 链路压缩测试通过")


def test_memory_manager():
    """测试记忆管理"""
    print("\n" + "=" * 60)
    print("测试记忆管理...")
    from backend.memory_manager import MemoryManager

    mm = MemoryManager()

    # 测试记忆提取
    test_input = "我叫小明，我喜欢打篮球和听音乐"
    memories = mm.extract_memories(test_input)
    print(f"  提取记忆数: {len(memories)}")
    for mem in memories:
        print(f"    [{mem['type']}] {mem['text']}")

    # 测试存储和检索
    stored_ids = mm.process_and_store(
        "我叫小红，我最喜欢画画",
        "好的，小红，我记住你喜欢画画了！",
        user_id="test_user2"
    )
    print(f"  存储记忆数: {len(stored_ids)}")

    retrieved = mm.retrieve_memories("我的名字", user_id="test_user2")
    print(f"  检索记忆数: {len(retrieved)}")
    if retrieved:
        print(f"  记忆内容: {retrieved[0]['document']}")

    print("  ✓ 记忆管理测试通过")


def test_knowledge_base():
    """测试知识库"""
    print("\n" + "=" * 60)
    print("测试知识库...")
    from backend.knowledge_base import KnowledgeBase

    kb = KnowledgeBase()

    # 添加文档
    ids = kb.add_document(
        "阿罗娜是基沃托斯什亭之匣的管理员，她是一个可爱的人工智能助手。"
        "她喜欢帮助老师解决问题，性格活泼开朗。",
        source="arona_intro"
    )
    print(f"  添加文档分块数: {len(ids)}")

    # 检索
    results = kb.retrieve("阿罗娜是谁", k=2)
    print(f"  检索结果数: {len(results)}")

    # 检索并压缩
    compressed = kb.retrieve_and_compress("阿罗娜的性格")
    print(f"  压缩后上下文: {compressed[:100]}...")

    print("  ✓ 知识库测试通过")


def test_arona_engine():
    """测试核心引擎（不实际调用模型）"""
    print("\n" + "=" * 60)
    print("测试核心引擎（仅测试模块集成，不调用模型）...")
    from backend.arona_engine import AronaEngine

    engine = AronaEngine()

    # 测试会话管理
    session_id = engine.create_session()
    print(f"  创建会话: {session_id}")

    # 测试知识库管理
    engine.add_knowledge("阿罗娜是基沃托斯什亭之匣的管理员。", source="test")
    count = engine.get_knowledge_count()
    print(f"  知识库文档数: {count}")

    # 测试缓存
    stats = engine.get_cache_stats()
    print(f"  缓存统计: {stats}")

    # 测试记忆管理
    engine.add_memory_manually("用户叫测试用户", user_id="test")
    memories = engine.get_user_memories("test")
    print(f"  用户记忆数: {len(memories)}")

    # 测试统计
    system_stats = engine.get_stats()
    print(f"  系统统计: {system_stats}")

    print("  ✓ 核心引擎集成测试通过")


def main():
    """运行所有测试"""
    print("=" * 60)
    print("Arona AI 后端测试")
    print("=" * 60)

    tests = [
        test_config,
        test_vector_store,
        test_semantic_cache,
        test_conversation_manager,
        test_chain_compressor,
        test_memory_manager,
        test_knowledge_base,
        test_arona_engine,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  ✗ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print(f"测试完成: {passed} 通过, {failed} 失败")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
