"""
向量数据库模块 - 使用ChromaDB进行向量存储和检索
支持知识库存储和记忆存储
"""
import os
import json
import hashlib
import chromadb
from chromadb.config import Settings
from chromadb.api.types import EmbeddingFunction as ChromaEmbeddingFunction
from typing import List, Dict, Optional, Tuple
from backend.config import VECTOR_DB_CONFIG, EMBEDDING_CONFIG
from backend.embeddings import get_embedding


class LocalEmbeddingFunction(ChromaEmbeddingFunction):
    """自定义嵌入函数，使用本地TF-IDF+SVD生成嵌入向量"""

    def __init__(self):
        self.model = get_embedding()

    def __call__(self, input: List[str]) -> List[List[float]]:
        embeddings = self.model.encode(input, normalize=True)
        return embeddings.tolist()


class VectorStore:
    """向量数据库管理器，封装ChromaDB操作"""

    def __init__(self, collection_name: str = None):
        self.persist_dir = VECTOR_DB_CONFIG["persist_directory"]
        self.embedding_fn = LocalEmbeddingFunction()

        # 初始化ChromaDB客户端
        self.client = chromadb.PersistentClient(
            path=self.persist_dir,
            settings=Settings(anonymized_telemetry=False)
        )

        # 获取或创建集合
        self.collection_name = collection_name or VECTOR_DB_CONFIG["collection_name"]
        try:
            self.collection = self.client.get_collection(
                name=self.collection_name,
                embedding_function=self.embedding_fn
            )
        except (ValueError, chromadb.errors.NotFoundError):
            self.collection = self.client.create_collection(
                name=self.collection_name,
                embedding_function=self.embedding_fn
            )

    def add_texts(self, texts: List[str], metadatas: Optional[List[Dict]] = None,
                   ids: Optional[List[str]] = None) -> List[str]:
        """
        添加文本到向量数据库

        Args:
            texts: 文本列表
            metadatas: 元数据列表
            ids: ID列表，如果不提供则自动生成

        Returns:
            ID列表
        """
        if ids is None:
            ids = [hashlib.md5(text.encode()).hexdigest()[:16] for text in texts]
        if metadatas is None:
            metadatas = [{} for _ in texts]

        # 去重：检查已存在的ID
        existing_ids = set()
        try:
            existing = self.collection.get(ids=ids)
            if existing and existing["ids"]:
                existing_ids = set(existing["ids"])
        except Exception:
            pass

        # 过滤掉已存在的
        new_texts, new_metadatas, new_ids = [], [], []
        for i, tid in enumerate(ids):
            if tid not in existing_ids:
                new_texts.append(texts[i])
                new_metadatas.append(metadatas[i])
                new_ids.append(tid)

        if new_texts:
            self.collection.add(
                documents=new_texts,
                metadatas=new_metadatas,
                ids=new_ids
            )

        return ids

    def similarity_search(self, query: str, k: int = None) -> List[Dict]:
        """
        语义相似度搜索

        Args:
            query: 查询文本
            k: 返回结果数量

        Returns:
            搜索结果列表，每项包含 document, metadata, distance
        """
        k = k or VECTOR_DB_CONFIG["similarity_top_k"]
        results = self.collection.query(
            query_texts=[query],
            n_results=k
        )

        documents = []
        if results and results["documents"]:
            for i in range(len(results["documents"][0])):
                documents.append({
                    "document": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else 0.0
                })

        return documents

    def get_all_documents(self) -> List[Dict]:
        """获取所有文档"""
        results = self.collection.get()
        documents = []
        if results and results["documents"]:
            for i in range(len(results["documents"])):
                documents.append({
                    "document": results["documents"][i],
                    "metadata": results["metadatas"][i] if results["metadatas"] else {},
                    "id": results["ids"][i]
                })
        return documents

    def delete_by_ids(self, ids: List[str]):
        """根据ID删除文档"""
        self.collection.delete(ids=ids)

    def count(self) -> int:
        """获取文档数量"""
        return self.collection.count()

    def clear(self):
        """清空集合"""
        self.client.delete_collection(self.collection_name)
        self.collection = self.client.create_collection(
            name=self.collection_name,
            embedding_function=self.embedding_fn
        )


class KnowledgeVectorStore(VectorStore):
    """知识库向量存储"""

    def __init__(self):
        from backend.config import KNOWLEDGE_CONFIG
        super().__init__(collection_name=KNOWLEDGE_CONFIG["knowledge_collection"])

    def add_knowledge(self, text: str, source: str = "", chunk_size: int = None,
                       chunk_overlap: int = None) -> List[str]:
        """
        添加知识文本（自动分块）

        Args:
            text: 知识文本
            source: 来源
            chunk_size: 分块大小
            chunk_overlap: 分块重叠

        Returns:
            分块ID列表
        """
        from backend.config import KNOWLEDGE_CONFIG
        chunk_size = chunk_size or KNOWLEDGE_CONFIG["chunk_size"]
        chunk_overlap = chunk_overlap or KNOWLEDGE_CONFIG["chunk_overlap"]

        # 简单分块
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunks.append(text[start:end])
            start += chunk_size - chunk_overlap

        metadatas = [{"source": source, "chunk_index": i, "total_chunks": len(chunks)}
                     for i in range(len(chunks))]

        return self.add_texts(chunks, metadatas=metadatas)

    def search_knowledge(self, query: str, k: int = None) -> List[Dict]:
        """搜索知识库"""
        return self.similarity_search(query, k=k)


class MemoryVectorStore(VectorStore):
    """记忆向量存储"""

    def __init__(self):
        from backend.config import MEMORY_CONFIG
        super().__init__(collection_name=MEMORY_CONFIG["memory_collection"])

    def add_memory(self, memory_text: str, user_id: str = "default",
                   memory_type: str = "fact") -> str:
        """
        添加记忆

        Args:
            memory_text: 记忆文本
            user_id: 用户ID
            memory_type: 记忆类型 (fact/preference/event)

        Returns:
            记忆ID
        """
        memory_id = hashlib.md5(memory_text.encode()).hexdigest()[:16]
        self.add_texts(
            [memory_text],
            metadatas=[{
                "user_id": user_id,
                "memory_type": memory_type,
                "timestamp": str(__import__("time").time())
            }],
            ids=[memory_id]
        )
        return memory_id

    def search_memory(self, query: str, user_id: str = "default", k: int = None) -> List[Dict]:
        """搜索记忆"""
        from backend.config import MEMORY_CONFIG
        k = k or MEMORY_CONFIG["similarity_top_k"]
        results = self.similarity_search(query, k=k * 2)  # 多搜一些再过滤

        # 过滤用户
        filtered = [r for r in results if r["metadata"].get("user_id") == user_id]
        return filtered[:k]

    def get_user_memories(self, user_id: str = "default") -> List[Dict]:
        """获取用户所有记忆"""
        all_docs = self.get_all_documents()
        return [d for d in all_docs if d["metadata"].get("user_id") == user_id]
