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

    def list_documents(self) -> List[Dict]:
        """列出知识库中的所有文档分块"""
        return self.vector_store.get_all_documents()

    def delete_documents(self, ids: List[str]) -> int:
        """根据ID删除知识库文档分块"""
        existing = self.vector_store.collection.get(ids=ids)
        existing_count = len(existing.get("ids", [])) if existing else 0
        self.vector_store.delete_by_ids(ids)
        return existing_count

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

    def get_stats(self) -> Dict:
        """获取知识库统计信息"""
        return {"count": self.count()}

    def clear(self):
        """清空知识库"""
        self.vector_store.clear()
