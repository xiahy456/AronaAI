"""
RAG知识库模块 - 知识检索增强生成
负责知识存储、检索和与模型生成的集成
"""
from typing import List, Dict, Optional
from backend.vector_store import KnowledgeVectorStore
from backend.chain_compressor import ChainCompressor


class KnowledgeBase:
    """
    知识库管理器 - 提供RAG能力
    支持知识的添加、检索和压缩
    """

    def __init__(self):
        self.vector_store = KnowledgeVectorStore()
        self.compressor = ChainCompressor()

    def add_document(self, text: str, source: str = "") -> List[str]:
        """
        添加文档到知识库

        Args:
            text: 文档文本
            source: 来源标识

        Returns:
            分块ID列表
        """
        return self.vector_store.add_knowledge(text, source=source)

    def add_documents(self, documents: List[Dict]) -> List[str]:
        """
        批量添加文档

        Args:
            documents: 文档列表，每项包含 text 和 source

        Returns:
            所有分块的ID列表
        """
        all_ids = []
        for doc in documents:
            ids = self.add_document(doc["text"], doc.get("source", ""))
            all_ids.extend(ids)
        return all_ids

    def retrieve(self, query: str, k: int = None) -> List[Dict]:
        """
        检索相关知识

        Args:
            query: 查询文本
            k: 返回结果数量

        Returns:
            检索到的文档列表
        """
        return self.vector_store.search_knowledge(query, k=k)

    def retrieve_and_compress(self, query: str, k: int = None,
                               max_length: int = None) -> str:
        """
        检索并压缩知识

        Args:
            query: 查询文本
            k: 检索数量
            max_length: 压缩后的最大长度

        Returns:
            压缩后的上下文字符串
        """
        documents = self.retrieve(query, k=k)
        if not documents:
            return ""

        return self.compressor.compress(documents, query, max_length=max_length)

    def get_knowledge_context(self, query: str) -> str:
        """
        获取知识上下文（供模型使用）

        Args:
            query: 用户查询

        Returns:
            格式化的知识上下文
        """
        compressed = self.retrieve_and_compress(query)
        if compressed:
            return f"【相关知识】\n{compressed}"
        return ""

    def count(self) -> int:
        """获取知识库文档数量"""
        return self.vector_store.count()

    def clear(self):
        """清空知识库"""
        self.vector_store.clear()
