"""
本地嵌入模块 - 使用TF-IDF + SVD实现文本向量化
无需下载外部模型，完全本地运行
"""
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from typing import List, Optional


class LocalEmbedding:
    """
    本地嵌入模型 - 基于TF-IDF和SVD的文本向量化
    无需网络连接，完全本地运行
    """

    def __init__(self, vector_size: int = 128):
        self.vector_size = vector_size
        self.tfidf = TfidfVectorizer(
            max_features=5000,
            analyzer='char',
            ngram_range=(1, 3),
            sublinear_tf=True
        )
        self.svd = TruncatedSVD(n_components=vector_size, random_state=42)
        self._fitted = False
        self._vocab = set()

    def _build_vocab(self, texts: List[str]):
        """构建词汇表"""
        for text in texts:
            # 简单分词：按字符和常见分隔符
            for i in range(len(text)):
                self._vocab.add(text[i:i+1])
            # 添加常见双字词
            for i in range(len(text) - 1):
                self._vocab.add(text[i:i+2])

    def _text_to_features(self, text: str) -> str:
        """将文本转换为特征表示"""
        return text

    def fit(self, texts: List[str]):
        """训练嵌入模型"""
        if len(texts) < 2:
            # 如果文本太少，添加一些默认文本
            texts = texts + ["默认文本", "默认查询", "你好", "再见"]

        # 训练TF-IDF
        tfidf_matrix = self.tfidf.fit_transform(texts)

        # 训练SVD降维
        n_components = min(self.vector_size, tfidf_matrix.shape[1] - 1)
        if n_components < 1:
            n_components = 1
        self.svd = TruncatedSVD(n_components=n_components, random_state=42)
        self.svd.fit(tfidf_matrix)

        self._fitted = True

    def encode(self, texts: List[str], normalize: bool = True) -> np.ndarray:
        """
        将文本编码为向量

        Args:
            texts: 文本列表
            normalize: 是否归一化

        Returns:
            向量数组 shape=(len(texts), vector_size)
        """
        if not self._fitted:
            self.fit(texts)

        # TF-IDF变换
        tfidf_matrix = self.tfidf.transform(texts)

        # SVD降维
        embeddings = self.svd.transform(tfidf_matrix)

        # 如果维度不足，填充0
        if embeddings.shape[1] < self.vector_size:
            padding = np.zeros((embeddings.shape[0], self.vector_size - embeddings.shape[1]))
            embeddings = np.hstack([embeddings, padding])

        if normalize:
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            norms = np.where(norms == 0, 1.0, norms)
            embeddings = embeddings / norms

        return embeddings

    def encode_single(self, text: str, normalize: bool = True) -> np.ndarray:
        """编码单个文本"""
        return self.encode([text], normalize=normalize)[0]


# 全局单例
_global_embedding = None


def get_embedding() -> LocalEmbedding:
    """获取全局嵌入模型实例"""
    global _global_embedding
    if _global_embedding is None:
        _global_embedding = LocalEmbedding(vector_size=128)
    return _global_embedding
