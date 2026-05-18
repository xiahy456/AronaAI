"""
记忆管理模块 - 让模型拥有长期记忆能力
自动识别需要记忆的信息并存储，在对话中检索相关记忆
"""
import re
from typing import List, Dict, Optional
from backend.vector_store import MemoryVectorStore
from backend.chain_compressor import ChainCompressor
from backend.config import MEMORY_CONFIG


class MemoryManager:
    """
    记忆管理器 - 管理AI的长期记忆
    功能：
    1. 自动识别用户输入中需要记忆的信息
    2. 将记忆存储到向量数据库
    3. 在对话中检索相关记忆
    """

    def __init__(self):
        self.vector_store = MemoryVectorStore()
        self.compressor = ChainCompressor()
        self.min_memory_length = MEMORY_CONFIG["min_memory_length"]

        # 需要记忆的关键词模式
        # 使用 [^，。！？\n]+ 匹配到句尾标点或换行为止，捕获完整信息
        # 注意：更具体的模式放在前面，避免被通用模式错误匹配
        self.memory_patterns = [
            # 身份信息（优先匹配）
            # "我是" 模式要求后面跟的是用户自称的名字，排除 "我是Arona" 这种AI自我介绍
            r"(?:我叫|我的名字叫|你可以叫我)\s*([^，。！？\n]{1,20})",
            # 年龄
            r"(?:我今年)\s*(\d+)\s*岁",
            # 偏好（在"记住"之前匹配，避免"请记住我最喜欢的颜色"被"记住"截胡）
            r"(?<!请记住)(?:我最喜欢|我喜欢|我爱|我讨厌|我不喜欢)\s*([^，。！？\n]{1,20})",
            # 位置
            r"(?:我住在|我来自|我家在)\s*([^，。！？\n]{1,20})",
            # 职业
            r"(?:我的工作|我的职业|我是做)\s*([^，。！？\n]{1,20})",
            # 爱好
            r"(?:我的爱好|我的兴趣|我喜欢做)\s*([^，。！？\n]{1,20})",
            # 显式要求记住
            r"(?:请记住|记住|别忘了|记一下)\s*([^，。！？\n]{1,20})",
            # 拥有物
            r"(?:我有|我养了|我有个)\s*([^，。！？\n]{1,20})",
        ]

    def extract_memories(self, text: str) -> List[Dict]:
        """
        从文本中提取需要记忆的信息

        Args:
            text: 用户输入的文本

        Returns:
            提取的记忆列表，每项包含 text 和 memory_type
        """
        memories = []

        # 如果文本是疑问句（包含问号或疑问语气词），跳过提取
        # 疑问句中的匹配很可能是反问/提问，不是陈述事实
        question_markers = ["?", "？", "吗", "呢", "吧", "什么", "怎么", "为什么", "如何", "哪"]
        is_question = any(marker in text for marker in question_markers)

        for pattern in self.memory_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                # 处理匹配结果
                if isinstance(match, tuple):
                    content = " ".join([m for m in match if m])
                else:
                    content = match

                content = content.strip()
                if len(content) >= self.min_memory_length:
                    # 疑问句中的匹配很可能是反问/提问，不是陈述事实，跳过
                    if is_question:
                        continue
                    # 判断记忆类型
                    memory_type = self._classify_memory(pattern, content)
                    memories.append({
                        "text": content,
                        "type": memory_type
                    })

        return memories

    def _classify_memory(self, pattern: str, content: str) -> str:
        """分类记忆类型"""
        if "名字" in pattern or "叫" in pattern:
            return "identity"
        elif "喜欢" in pattern or "爱" in pattern or "讨厌" in pattern:
            return "preference"
        elif "住" in pattern or "来自" in pattern:
            return "location"
        elif "岁" in pattern or "今年" in pattern:
            return "age"
        elif "工作" in pattern or "职业" in pattern:
            return "occupation"
        elif "爱好" in pattern or "兴趣" in pattern:
            return "hobby"
        elif "记住" in pattern or "记一下" in pattern:
            return "explicit"
        elif "有" in pattern or "养" in pattern:
            return "possession"
        else:
            return "fact"

    def store_memory(self, text: str, user_id: str = "default",
                     memory_type: str = "fact") -> Optional[str]:
        """
        存储记忆

        Args:
            text: 记忆文本
            user_id: 用户ID
            memory_type: 记忆类型

        Returns:
            记忆ID，如果失败返回None
        """
        # 压缩提取关键信息
        key_info = self.compressor.extract_key_info(text)

        if len(key_info) < self.min_memory_length:
            return None

        return self.vector_store.add_memory(key_info, user_id, memory_type)

    def process_and_store(self, user_input: str, assistant_response: str,
                           user_id: str = "default") -> List[str]:
        """
        处理对话并自动存储需要记忆的信息

        Args:
            user_input: 用户输入
            assistant_response: 模型回复
            user_id: 用户ID

        Returns:
            存储的记忆ID列表
        """
        stored_ids = []

        # 从用户输入中提取记忆
        user_memories = self.extract_memories(user_input)
        for memory in user_memories:
            memory_id = self.store_memory(
                memory["text"],
                user_id=user_id,
                memory_type=memory["type"]
            )
            if memory_id:
                stored_ids.append(memory_id)

        # 从模型回复中提取可能的重要信息
        assistant_memories = self.extract_memories(assistant_response)
        for memory in assistant_memories:
            memory_id = self.store_memory(
                memory["text"],
                user_id=user_id,
                memory_type=memory["type"]
            )
            if memory_id:
                stored_ids.append(memory_id)

        return stored_ids

    def retrieve_memories(self, query: str, user_id: str = "default",
                           k: int = None) -> List[Dict]:
        """
        检索相关记忆

        Args:
            query: 查询文本
            user_id: 用户ID
            k: 返回数量

        Returns:
            相关记忆列表
        """
        return self.vector_store.search_memory(query, user_id, k=k)

    def get_memory_context(self, query: str, user_id: str = "default") -> str:
        """
        获取记忆上下文（供模型使用）

        Args:
            query: 用户查询
            user_id: 用户ID

        Returns:
            格式化的记忆上下文
        """
        memories = self.retrieve_memories(query, user_id)
        if not memories:
            return ""

        memory_texts = []
        for mem in memories:
            mem_type = mem["metadata"].get("memory_type", "fact")
            mem_text = mem["document"]
            memory_texts.append(f"[{mem_type}] {mem_text}")

        return f"【相关记忆】\n" + "\n".join(memory_texts)

    def get_all_memories(self, user_id: str = "default") -> List[Dict]:
        """获取用户所有记忆"""
        return self.vector_store.get_user_memories(user_id)

    def clear_user_memories(self, user_id: str = "default"):
        """清空用户记忆"""
        memories = self.get_all_memories(user_id)
        ids = [m["id"] for m in memories]
        if ids:
            self.vector_store.delete_by_ids(ids)
