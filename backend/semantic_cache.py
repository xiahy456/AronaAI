"""
语义缓存模块 - 基于语义相似度的缓存系统
避免重复的RAG链路调用，提升响应速度
改进版本：增强语义区分度，防止短文本误匹配
"""
import os
import json
import time
import hashlib
import pickle
from typing import Optional, Dict, List, Any
import numpy as np
from backend.config import CACHE_CONFIG
from backend.embeddings import get_embedding


class SemanticCache:
    """
    语义缓存 - 通过语义相似度判断缓存命中
    改进版本：
    1. 对短文本使用更高的相似度阈值（短文本区分度低）
    2. 要求最佳匹配与次佳匹配之间有显著差距
    3. 使用更严格的相似度计算
    """

    def __init__(self):
        self.cache_dir = CACHE_CONFIG["cache_dir"]
        self.base_similarity_threshold = CACHE_CONFIG["similarity_threshold"]
        self.max_cache_size = CACHE_CONFIG["max_cache_size"]
        self.ttl = CACHE_CONFIG["ttl"]

        # 短文本阈值提升参数
        self.short_text_length = 10  # 少于10个字符视为短文本
        self.short_text_threshold_boost = 0.10  # 短文本额外提高0.1

        # 最小相似度差距：最佳匹配必须比次佳匹配高至少此值
        self.min_similarity_gap = 0.15

        # 加载本地嵌入模型
        self.embedding_model = get_embedding()

        # 缓存数据结构: {query_hash: {"query": str, "embedding": list, "response": str,
        #                               "context": str, "timestamp": float, "access_count": int}}
        self.cache: Dict[str, Dict] = {}
        self.cache_file = os.path.join(self.cache_dir, "semantic_cache.pkl")
        self._load_cache()

    def _load_cache(self):
        """从磁盘加载缓存"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "rb") as f:
                    self.cache = pickle.load(f)
                print(f"已加载语义缓存，共 {len(self.cache)} 条")
            except Exception as e:
                print(f"加载缓存失败: {e}")
                self.cache = {}

    def _save_cache(self):
        """保存缓存到磁盘"""
        os.makedirs(self.cache_dir, exist_ok=True)
        try:
            with open(self.cache_file, "wb") as f:
                pickle.dump(self.cache, f)
        except Exception as e:
            print(f"保存缓存失败: {e}")

    def _get_embedding(self, text: str) -> List[float]:
        """获取文本的嵌入向量"""
        embedding = self.embedding_model.encode_single(text, normalize=True)
        return embedding.tolist()

    def _cosine_similarity(self, emb1: List[float], emb2: List[float]) -> float:
        """计算余弦相似度"""
        emb1 = np.array(emb1, dtype=np.float64)
        emb2 = np.array(emb2, dtype=np.float64)
        dot_product = np.dot(emb1, emb2)
        # 数值稳定性处理
        dot_product = np.clip(dot_product, -1.0, 1.0)
        return float(dot_product)

    def _get_dynamic_threshold(self, query: str) -> float:
        """
        根据查询长度动态调整相似度阈值
        短文本区分度低，需要更高的阈值
        """
        threshold = self.base_similarity_threshold
        if len(query) <= self.short_text_length:
            threshold += self.short_text_threshold_boost
        return threshold

    def _clean_expired(self):
        """清理过期缓存"""
        now = time.time()
        expired_keys = [
            k for k, v in self.cache.items()
            if now - v["timestamp"] > self.ttl
        ]
        for k in expired_keys:
            del self.cache[k]

        # 如果缓存太大，删除最不常用的
        if len(self.cache) > self.max_cache_size:
            sorted_items = sorted(
                self.cache.items(),
                key=lambda x: x[1]["access_count"]
            )
            for k, _ in sorted_items[:len(self.cache) - self.max_cache_size]:
                del self.cache[k]

    def get(self, query: str) -> Optional[Dict]:
        """
        从缓存中获取匹配的结果

        Args:
            query: 用户查询

        Returns:
            如果命中缓存返回 {"response": str, "context": str}，否则返回 None
        """
        self._clean_expired()

        if not self.cache:
            return None

        query_embedding = self._get_embedding(query)
        dynamic_threshold = self._get_dynamic_threshold(query)

        # 收集所有相似度得分
        similarities = []
        for cache_key, cache_item in self.cache.items():
            similarity = self._cosine_similarity(
                query_embedding, cache_item["embedding"]
            )
            similarities.append((similarity, cache_key, cache_item))

        # 按相似度降序排序
        similarities.sort(key=lambda x: x[0], reverse=True)

        if not similarities:
            return None

        best_similarity, best_key, best_match = similarities[0]

        # 检查最佳匹配是否超过动态阈值
        if best_similarity < dynamic_threshold:
            return None

        # 如果有多个匹配，检查最佳与次佳之间的差距
        if len(similarities) > 1:
            second_similarity = similarities[1][0]
            similarity_gap = best_similarity - second_similarity

            # 如果差距太小，说明查询与多个缓存项都相似，可能是模糊匹配，不命中
            if similarity_gap < self.min_similarity_gap:
                return None

        # 额外检查：如果最佳匹配的查询与当前查询长度差异过大，降低置信度
        cached_query = best_match.get("query", "")
        length_ratio = min(len(query), len(cached_query)) / max(len(query), len(cached_query), 1)
        if length_ratio < 0.5:
            # 长度差异超过一倍，很可能是不同的问题
            return None

        # 更新访问计数
        best_match["access_count"] += 1
        self._save_cache()

        return {
            "response": best_match["response"],
            "context": best_match.get("context", ""),
            "similarity": best_similarity
        }

    def set(self, query: str, response: str, context: str = ""):
        """
        将结果存入缓存

        Args:
            query: 用户查询
            response: 模型回复
            context: 使用的上下文
        """
        self._clean_expired()

        # 生成缓存键
        query_hash = hashlib.md5(query.encode()).hexdigest()

        self.cache[query_hash] = {
            "query": query,
            "embedding": self._get_embedding(query),
            "response": response,
            "context": context,
            "timestamp": time.time(),
            "access_count": 1
        }

        self._save_cache()

    def invalidate(self, query: str):
        """使与查询相关的缓存失效"""
        query_embedding = self._get_embedding(query)
        dynamic_threshold = self._get_dynamic_threshold(query)
        invalid_keys = []
        for cache_key, cache_item in self.cache.items():
            similarity = self._cosine_similarity(
                query_embedding, cache_item["embedding"]
            )
            if similarity >= dynamic_threshold:
                invalid_keys.append(cache_key)

        for k in invalid_keys:
            del self.cache[k]

        if invalid_keys:
            self._save_cache()

    def clear(self):
        """清空缓存"""
        self.cache = {}
        self._save_cache()

    def get_stats(self) -> Dict:
        """获取缓存统计信息"""
        return {
            "size": len(self.cache),
            "max_size": self.max_cache_size,
            "ttl": self.ttl,
            "base_threshold": self.base_similarity_threshold,
            "short_text_threshold_boost": self.short_text_threshold_boost,
            "min_similarity_gap": self.min_similarity_gap,
        }
