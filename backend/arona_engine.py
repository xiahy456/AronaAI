"""
Arona AI 核心引擎 - 集成所有模块的调用接口
提供统一的对话、知识检索、记忆管理、缓存等功能
"""
import time
import uuid
from typing import Optional, Dict, List, Any
from backend.model_loader import ModelLoader
from backend.conversation_manager import ConversationManager
from backend.knowledge_base import KnowledgeBase
from backend.memory_manager import MemoryManager
from backend.semantic_cache import SemanticCache


class AronaEngine:
    """
    Arona AI 核心引擎
    集成所有模块，提供统一的调用接口

    工作流程：
    1. 检查语义缓存 -> 命中则直接返回
    2. 获取对话历史
    3. 检索相关记忆
    4. 检索知识库（RAG）
    5. 链路压缩
    6. 构建完整上下文
    7. 模型生成
    8. 存储记忆
    9. 更新对话历史
    10. 写入语义缓存
    """

    def __init__(self):
        self.model = ModelLoader()
        self.conversation = ConversationManager()
        self.knowledge_base = KnowledgeBase()
        self.memory_manager = MemoryManager()
        self.cache = SemanticCache()

        # 系统提示词
        self.system_prompt = (
            "你是阿罗娜（Arona），一个可爱、活泼的AI助手。"
            "你来自基沃托斯（Kivotos），是什亭之匣的管理员。"
            "你性格开朗、热情，喜欢帮助老师解决问题。"
            "在回答时，请保持可爱活泼的语气，但也要确保回答准确有用。"
        )

    def chat(self, user_input: str, session_id: str = None,
             user_id: str = "default", use_cache: bool = True,
             use_rag: bool = True, use_memory: bool = True) -> Dict:
        """
        核心对话接口

        Args:
            user_input: 用户输入
            session_id: 会话ID，不提供则自动创建
            user_id: 用户ID
            use_cache: 是否使用语义缓存
            use_rag: 是否使用RAG知识检索
            use_memory: 是否使用记忆检索

        Returns:
            {
                "response": str,          # 模型回复
                "session_id": str,        # 会话ID
                "from_cache": bool,       # 是否来自缓存
                "context_used": bool,     # 是否使用了额外上下文
                "latency": float,         # 响应时间（秒）
                "memories_stored": int,   # 新存储的记忆数
            }
        """
        start_time = time.time()

        # 1. 创建或获取会话
        if session_id is None:
            session_id = str(uuid.uuid4())
            self.conversation.create_session(session_id)

        # 2. 检查语义缓存（快速路径）
        if use_cache:
            cached = self.cache.get(user_input)
            if cached:
                # 更新对话历史（缓存命中也要记录）
                self.conversation.add_message(session_id, "user", user_input)
                self.conversation.add_message(session_id, "assistant", cached["response"])

                return {
                    "response": cached["response"],
                    "session_id": session_id,
                    "from_cache": True,
                    "context_used": bool(cached.get("context")),
                    "latency": time.time() - start_time,
                    "memories_stored": 0
                }

        # 3. 构建上下文
        context_parts = []
        context_used = False

        # 4. 检索相关记忆
        if use_memory:
            memory_context = self.memory_manager.get_memory_context(user_input, user_id)
            if memory_context:
                context_parts.append(memory_context)
                context_used = True

        # 5. 检索知识库（RAG）
        if use_rag:
            knowledge_context = self.knowledge_base.get_knowledge_context(user_input)
            if knowledge_context:
                context_parts.append(knowledge_context)
                context_used = True

        # 6. 合并上下文
        full_context = "\n\n".join(context_parts) if context_parts else ""

        # 7. 获取对话历史
        history = self.conversation.get_history(session_id)

        # 8. 模型生成
        response = self.model.generate_with_context(
            user_input=user_input,
            context=full_context,
            history=history,
            system_prompt=self.system_prompt
        )

        # 9. 存储记忆
        memories_stored = 0
        if use_memory:
            stored_ids = self.memory_manager.process_and_store(
                user_input, response, user_id
            )
            memories_stored = len(stored_ids)

        # 10. 更新对话历史
        self.conversation.add_message(session_id, "user", user_input)
        self.conversation.add_message(session_id, "assistant", response)

        # 11. 写入语义缓存
        if use_cache:
            self.cache.set(user_input, response, context=full_context)

        latency = time.time() - start_time

        return {
            "response": response,
            "session_id": session_id,
            "from_cache": False,
            "context_used": context_used,
            "latency": latency,
            "memories_stored": memories_stored
        }

    def chat_stream(self, user_input: str, session_id: str = None,
                    user_id: str = "default", use_cache: bool = True,
                    use_rag: bool = True, use_memory: bool = True):
        """
        流式对话接口（生成器）

        Args:
            参数同 chat()

        Yields:
            逐步生成的文本片段
        """
        # 先获取完整结果
        result = self.chat(
            user_input=user_input,
            session_id=session_id,
            user_id=user_id,
            use_cache=use_cache,
            use_rag=use_rag,
            use_memory=use_memory
        )

        # 模拟流式输出（按字符/词分割）
        response = result["response"]
        # 按标点符号和空格分割
        import re
        parts = re.split(r'([，。！？、；：\n])', response)
        for part in parts:
            if part:
                yield part

    # ========== 知识库管理接口 ==========

    def add_knowledge(self, text: str, source: str = "") -> List[str]:
        """添加知识到知识库"""
        return self.knowledge_base.add_document(text, source)

    def add_knowledge_batch(self, documents: List[Dict]) -> List[str]:
        """批量添加知识"""
        return self.knowledge_base.add_documents(documents)

    def search_knowledge(self, query: str, k: int = 3) -> List[Dict]:
        """搜索知识库"""
        return self.knowledge_base.retrieve(query, k=k)

    def get_knowledge_count(self) -> int:
        """获取知识库文档数量"""
        return self.knowledge_base.count()

    def clear_knowledge(self):
        """清空知识库"""
        self.knowledge_base.clear()

    # ========== 记忆管理接口 ==========

    def get_user_memories(self, user_id: str = "default") -> List[Dict]:
        """获取用户记忆"""
        return self.memory_manager.get_all_memories(user_id)

    def clear_user_memories(self, user_id: str = "default"):
        """清空用户记忆"""
        self.memory_manager.clear_user_memories(user_id)

    def add_memory_manually(self, text: str, user_id: str = "default",
                            memory_type: str = "fact") -> Optional[str]:
        """手动添加记忆"""
        return self.memory_manager.store_memory(text, user_id, memory_type)

    # ========== 会话管理接口 ==========

    def create_session(self, session_id: str = None) -> str:
        """创建新会话"""
        if session_id is None:
            session_id = str(uuid.uuid4())
        self.conversation.create_session(session_id)
        return session_id

    def get_history(self, session_id: str, turns: int = None):
        """获取对话历史"""
        if turns:
            return self.conversation.get_recent_history(session_id, turns)
        return self.conversation.get_history(session_id)

    def clear_session(self, session_id: str):
        """清空会话"""
        self.conversation.clear_session(session_id)

    def clear_all_sessions(self):
        """清空所有会话"""
        for sid in self.conversation.get_all_session_ids():
            self.conversation.clear_session(sid)

    # ========== 缓存管理接口 ==========

    def clear_cache(self):
        """清空语义缓存"""
        self.cache.clear()

    def get_cache_stats(self) -> Dict:
        """获取缓存统计"""
        return self.cache.get_stats()

    # ========== 系统管理接口 ==========

    def get_stats(self) -> Dict:
        """获取系统统计信息"""
        return {
            "sessions": self.conversation.get_session_count(),
            "knowledge_count": self.knowledge_base.count(),
            "cache": self.cache.get_stats(),
        }

    def set_system_prompt(self, prompt: str):
        """设置系统提示词"""
        self.system_prompt = prompt
