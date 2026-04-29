"""
嵌入模块 - 支持本地TF-IDF和外部sentence-transformers两种模式
提供文本向量化功能，用于语义相似度计算
"""
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from typing import List, Optional, Union
import re
import os
from pathlib import Path


class LocalEmbedding:
    """
    本地嵌入模型 - 基于TF-IDF和SVD的文本向量化
    无需下载外部模型，完全本地运行
    使用jieba分词提升中文语义理解能力
    """

    def __init__(self, vector_size: int = 256):
        self.vector_size = vector_size
        # 使用词级特征（通过空格分隔的词），配合sublinear_tf提升区分度
        # token_pattern 使用 \S+ 匹配所有非空白字符（包括单字符中文词）
        self.tfidf = TfidfVectorizer(
            max_features=8000,
            analyzer='word',
            token_pattern=r'\S+',
            ngram_range=(1, 2),
            sublinear_tf=True,
            min_df=1,
            max_df=0.95,
        )
        self.svd = TruncatedSVD(n_components=min(vector_size, 200), random_state=42)
        self._fitted = False
        self._has_jieba = False

        # 尝试导入jieba
        try:
            import jieba
            self._jieba = jieba
            self._has_jieba = True
            # 初始化jieba
            jieba.initialize()
        except ImportError:
            self._has_jieba = False

    def _tokenize(self, text: str) -> str:
        """
        对文本进行分词，返回空格分隔的词序列
        优先使用jieba分词，回退到字符级特征
        """
        if not text or not text.strip():
            return ""

        if self._has_jieba:
            # 使用jieba精确模式分词
            words = self._jieba.lcut(text)
            # 过滤掉单字符标点和空白
            words = [w for w in words if w.strip() and not re.match(r'^[^\w]+$', w)]
            return ' '.join(words)
        else:
            # 回退方案：按字符和常见分隔符
            tokens = []
            parts = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z0-9]+|[^\w\s]', text)
            for part in parts:
                if re.match(r'[\u4e00-\u9fff]+', part):
                    for char in part:
                        tokens.append(char)
                elif re.match(r'[a-zA-Z0-9]+', part):
                    tokens.append(part.lower())
            return ' '.join(tokens)

    def fit(self, texts: List[str]):
        """训练嵌入模型"""
        if len(texts) < 2:
            texts = texts + ["默认文本", "默认查询", "你好", "再见", "谢谢", "帮助", "问题", "回答"]

        tokenized_texts = [self._tokenize(t) for t in texts]
        tfidf_matrix = self.tfidf.fit_transform(tokenized_texts)

        n_components = min(self.vector_size, tfidf_matrix.shape[1] - 1, 200)
        if n_components < 2:
            n_components = 2
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

        tokenized_texts = [self._tokenize(t) for t in texts]
        tfidf_matrix = self.tfidf.transform(tokenized_texts)
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


class ExternalEmbedding:
    """
    外部嵌入模型 - 使用 sentence-transformers 预训练模型
    提供高质量的中文语义向量，大幅提升语义区分度
    模型会自动下载到 models/ 目录下
    """

    def __init__(self, model_name: str = "paraphrase-multilingual-MiniLM-L12-v2",
                 device: str = "cpu"):
        from sentence_transformers import SentenceTransformer

        # 优先从本地 models 目录加载
        project_root = Path(__file__).parent.parent
        local_model_path = str(project_root / "models" / model_name)

        if os.path.exists(local_model_path):
            print(f"从本地加载嵌入模型: {local_model_path}")
            self.model = SentenceTransformer(local_model_path, device=device)
        else:
            print(f"正在下载嵌入模型 {model_name} 到 {local_model_path} ...")
            # 先下载到临时目录，再移动到目标位置
            self.model = SentenceTransformer(model_name, device=device)
            # 保存到本地 models 目录
            os.makedirs(os.path.dirname(local_model_path), exist_ok=True)
            self.model.save(local_model_path)
            print(f"嵌入模型已保存到: {local_model_path}")

        self.vector_size = self.model.get_sentence_embedding_dimension()
        print(f"嵌入模型加载完成 | 模型: {model_name} | 向量维度: {self.vector_size} | 设备: {device}")

    def encode(self, texts: List[str], normalize: bool = True) -> np.ndarray:
        """
        将文本编码为向量

        Args:
            texts: 文本列表
            normalize: 是否归一化

        Returns:
            向量数组 shape=(len(texts), vector_size)
        """
        embeddings = self.model.encode(texts, normalize_embeddings=normalize)
        return np.array(embeddings)

    def encode_single(self, text: str, normalize: bool = True) -> np.ndarray:
        """编码单个文本"""
        return self.encode([text], normalize=normalize)[0]


# 全局单例
_global_embedding = None


def get_embedding() -> Union[LocalEmbedding, ExternalEmbedding]:
    """
    获取全局嵌入模型实例
    根据配置选择使用本地TF-IDF模型或外部sentence-transformers模型
    """
    global _global_embedding
    if _global_embedding is None:
        from backend.config import EMBEDDING_CONFIG

        use_external = EMBEDDING_CONFIG.get("use_external", False)
        if use_external:
            print("使用外部嵌入模型 (sentence-transformers)")
            _global_embedding = ExternalEmbedding(
                model_name=EMBEDDING_CONFIG["model_name"],
                device=EMBEDDING_CONFIG["device"]
            )
        else:
            print("使用本地嵌入模型 (TF-IDF + SVD)")
            _global_embedding = LocalEmbedding(vector_size=256)

    return _global_embedding
