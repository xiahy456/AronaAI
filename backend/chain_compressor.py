"""
链路压缩模块 - 对RAG检索结果进行压缩和优化
减少传递给模型的上下文长度，提升推理效率
"""
import re
import math
from collections import Counter
from typing import List, Dict, Optional
from backend.config import COMPRESSOR_CONFIG


class ChainCompressor:
    """
    链路压缩器 - 对RAG检索到的上下文进行压缩
    包括：去重、相关性排序、摘要提取、长度控制
    """

    def __init__(self):
        self.max_context_length = COMPRESSOR_CONFIG["max_context_length"]
        self.summary_ratio = COMPRESSOR_CONFIG["summary_ratio"]
        self.tfidf_score_weight = COMPRESSOR_CONFIG.get("tfidf_score_weight", 3.0)
        self.simple_query_context_ratio = COMPRESSOR_CONFIG.get("simple_query_context_ratio", 0.6)
        self.medium_query_context_ratio = COMPRESSOR_CONFIG.get("medium_query_context_ratio", 0.8)
        self.complex_query_context_ratio = COMPRESSOR_CONFIG.get("complex_query_context_ratio", 1.0)
        self.use_bge_embedding = COMPRESSOR_CONFIG.get("use_bge_embedding", False)
        self.bge_model_name = COMPRESSOR_CONFIG.get("bge_model_name", "BAAI/bge-small-zh-v1.5")
        self.bge_device = COMPRESSOR_CONFIG.get("bge_device", "auto")
        self.bge_score_weight = COMPRESSOR_CONFIG.get("bge_score_weight", 3.0)
        self._bge_model = None

    def compress(self, documents: List[Dict], query: str,
                 max_length: int = None) -> str:
        """
        压缩文档列表为精简上下文

        Args:
            documents: 文档列表，每项包含 document, metadata, distance
            query: 原始查询
            max_length: 最大上下文长度

        Returns:
            压缩后的上下文字符串
        """
        if not documents:
            return ""

        max_length = self._get_adaptive_max_length(query, max_length or self.max_context_length)

        # 1. 去重
        unique_docs = self._deduplicate(documents)

        # 2. 按相关性排序（distance越小越相关）
        sorted_docs = sorted(unique_docs, key=lambda x: x.get("distance", 1.0))

        # 3. 提取关键内容
        compressed_parts = []
        current_length = 0

        for doc in sorted_docs:
            text = doc["document"]

            # 对每个文档进行压缩
            compressed_text = self._extract_relevant(text, query)
            if not compressed_text:
                continue

            # 检查是否超出长度限制
            separator_length = len("\n---\n") if compressed_parts else 0
            if current_length + separator_length + len(compressed_text) > max_length:
                # 如果还有空间，截断并添加
                remaining = max_length - current_length - separator_length
                truncated = self._truncate_to_sentence(compressed_text, remaining)
                if truncated:
                    compressed_parts.append(truncated)
                break

            compressed_parts.append(compressed_text)
            current_length += separator_length + len(compressed_text)

        return "\n---\n".join(compressed_parts)

    def _deduplicate(self, documents: List[Dict]) -> List[Dict]:
        """去重 - 基于文本相似度"""
        unique = []
        seen_texts = set()

        for doc in documents:
            text_key = self._normalize_for_dedup(doc["document"])
            if text_key not in seen_texts:
                seen_texts.add(text_key)
                unique.append(doc)

        return unique

    def _extract_relevant(self, text: str, query: str) -> str:
        """
        提取与查询最相关的内容

        Args:
            text: 原始文本
            query: 查询

        Returns:
            提取后的文本
        """
        if not text:
            return ""

        # 如果文本很短，直接返回
        if len(text) < 100:
            return text.strip()

        # 尝试找到包含查询关键词的句子
        query_keywords = set(self._tokenize(query))
        sentences = self._split_sentences(text)

        if len(sentences) <= 3:
            return text.strip()

        sentence_scores = self._get_sentence_scores(query, sentences)
        summary_ratio = self._get_adaptive_summary_ratio(query)

        # 给每个句子打分
        scored_sentences = []
        for idx, sentence in enumerate(sentences):
            sentence_lower = sentence.lower()
            score = 0.0

            # 关键词匹配
            for keyword in query_keywords:
                if keyword.lower() in sentence_lower:
                    score += 2.0

            score += sentence_scores[idx] * (self.bge_score_weight if self.use_bge_embedding else self.tfidf_score_weight)

            # 位置权重只作为轻微辅助，避免覆盖相关性判断
            if idx == 0 or idx == len(sentences) - 1:
                score += 0.3

            scored_sentences.append((sentence, score, idx))

        # 按分数排序，取前N个句子
        scored_sentences.sort(key=lambda x: x[1], reverse=True)
        top_n = max(2, int(len(sentences) * summary_ratio))
        selected = {s[2] for s in scored_sentences[:top_n]}

        # 按原文顺序重新排列
        ordered = []
        for idx, sentence in enumerate(sentences):
            if idx in selected:
                ordered.append(sentence)

        return " ".join(ordered)

    def _get_adaptive_max_length(self, query: str, max_length: int) -> int:
        """根据问题复杂度调整上下文长度，但不超过调用方传入的上限。"""
        complexity = self._complexity_score(query)
        if complexity >= 4:
            ratio = self.complex_query_context_ratio
        elif complexity >= 2:
            ratio = self.medium_query_context_ratio
        else:
            ratio = self.simple_query_context_ratio
        return max(1, min(max_length, int(max_length * ratio)))

    def _get_adaptive_summary_ratio(self, query: str) -> float:
        """复杂问题保留更多句子，简单问题沿用更强压缩。"""
        complexity = self._complexity_score(query)
        if complexity >= 4:
            return min(0.8, self.summary_ratio + 0.3)
        if complexity >= 2:
            return min(0.6, self.summary_ratio + 0.15)
        return self.summary_ratio

    def _complexity_score(self, query: str) -> int:
        """用轻量规则估计查询复杂度。"""
        query = query.strip()
        tokens = self._tokenize(query)
        score = 0

        if len(query) >= 30:
            score += 2
        elif len(query) >= 15:
            score += 1

        if len(tokens) >= 8:
            score += 1

        complex_markers = [
            "为什么", "如何", "怎么", "分析", "比较", "区别",
            "原因", "方案", "步骤", "影响", "优缺点", "详细",
        ]
        if any(marker in query for marker in complex_markers):
            score += 2

        if "?" in query or "？" in query:
            score += 1

        return score

    def _load_bge_model(self) -> bool:
        """懒加载BGE嵌入模型，仅首次调用时初始化。"""
        if self._bge_model is not None:
            return True
        try:
            from sentence_transformers import SentenceTransformer
            import torch
            device = self.bge_device
            if device == "auto":
                device = "cuda" if torch.cuda.is_available() else "cpu"
            self._bge_model = SentenceTransformer(
                self.bge_model_name,
                device=device
            )
            return True
        except Exception as e:
            print(f"BGE模型加载失败，回退到TF-IDF: {e}")
            self._bge_model = None
            return False

    def _bge_scores(self, query: str, sentences: List[str]) -> Optional[List[float]]:
        """使用BGE微模型计算查询与候选句子的语义相似度。"""
        if not self._load_bge_model():
            return None
        try:
            embeddings = self._bge_model.encode(
                [query] + sentences,
                normalize_embeddings=True,
                show_progress_bar=False
            )
            query_vec = embeddings[0].tolist()
            scores = []
            for i in range(1, len(embeddings)):
                sent_vec = embeddings[i].tolist()
                dot = sum(q * s for q, s in zip(query_vec, sent_vec))
                scores.append(max(-1.0, min(1.0, float(dot))))
            return scores
        except Exception as e:
            print(f"BGE编码失败，回退到TF-IDF: {e}")
            return None

    def _get_sentence_scores(self, query: str, sentences: List[str]) -> List[float]:
        """获取句子相关性分数，优先使用BGE，不可用时回退TF-IDF。"""
        if self.use_bge_embedding:
            bge_scores = self._bge_scores(query, sentences)
            if bge_scores is not None:
                return bge_scores
        return self._tfidf_scores(query, sentences)

    def _tfidf_scores(self, query: str, sentences: List[str]) -> List[float]:
        """计算查询与候选句子的字符级TF-IDF相似度。"""
        if not query.strip() or not sentences:
            return [0.0 for _ in sentences]

        documents = [query] + sentences
        tokenized_docs = [self._char_ngrams(doc) for doc in documents]
        if not tokenized_docs[0]:
            return [0.0 for _ in sentences]

        doc_count = len(tokenized_docs)
        document_frequency = Counter()
        for tokens in tokenized_docs:
            document_frequency.update(set(tokens))

        vectors = []
        for tokens in tokenized_docs:
            term_frequency = Counter(tokens)
            vector = {}
            for token, count in term_frequency.items():
                idf = math.log((1 + doc_count) / (1 + document_frequency[token])) + 1
                vector[token] = count * idf
            vectors.append(vector)

        query_vector = vectors[0]
        return [self._cosine_similarity(query_vector, vector) for vector in vectors[1:]]

    def _char_ngrams(self, text: str) -> List[str]:
        """生成字符n-gram，避免依赖外部分词器。"""
        normalized = re.sub(r'\s+', '', text.lower())
        tokens = []
        for size in (2, 3, 4):
            if len(normalized) >= size:
                tokens.extend(normalized[i:i + size] for i in range(len(normalized) - size + 1))
        return tokens

    def _cosine_similarity(self, left: Dict[str, float], right: Dict[str, float]) -> float:
        """计算稀疏向量余弦相似度。"""
        if not left or not right:
            return 0.0

        shared_tokens = set(left) & set(right)
        dot_product = sum(left[token] * right[token] for token in shared_tokens)
        left_norm = math.sqrt(sum(value * value for value in left.values()))
        right_norm = math.sqrt(sum(value * value for value in right.values()))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return dot_product / (left_norm * right_norm)

    def _normalize_for_dedup(self, text: str) -> str:
        """规范化文本后去重，避免空白和标点差异造成重复。"""
        normalized = re.sub(r'[\W_]+', '', text.lower())
        return normalized[:100]

    def _truncate_to_sentence(self, text: str, max_length: int) -> str:
        """优先在句子边界截断，避免把上下文切在半句话中间。"""
        if max_length <= 0:
            return ""
        if len(text) <= max_length:
            return text.strip()

        clipped = text[:max_length].rstrip()
        boundary = max(clipped.rfind(mark) for mark in "。！？.!?\n")
        if boundary >= max(0, min(20, max_length // 3)):
            return clipped[:boundary + 1].strip()
        return clipped.strip()

    def _tokenize(self, text: str) -> List[str]:
        """简单分词"""
        tokens = []
        raw_tokens = re.findall(r'[a-zA-Z0-9]+|[\u4e00-\u9fff]+', text.lower())
        for token in raw_tokens:
            tokens.append(token)
            if re.fullmatch(r'[\u4e00-\u9fff]+', token) and len(token) >= 2:
                tokens.extend(token[i:i + 2] for i in range(len(token) - 1))
        return tokens

    def _split_sentences(self, text: str) -> List[str]:
        """分句"""
        sentences = re.findall(r'[^。！？\n]+[。！？]?', text)
        return [s.strip() for s in sentences if s.strip()]

    def extract_key_info(self, text: str, max_length: int = 200) -> str:
        """
        提取关键信息（用于记忆存储时的精简）

        Args:
            text: 原始文本
            max_length: 最大长度

        Returns:
            提取的关键信息
        """
        if len(text) <= max_length:
            return text.strip()

        # 提取包含重要信息的部分
        # 优先保留包含"是"、"叫"、"喜欢"、"有"等关键词的句子
        important_keywords = ["是", "叫", "喜欢", "有", "想要", "希望",
                              "我的", "名字", "年龄", "爱好", "工作"]

        sentences = self._split_sentences(text)
        important_sentences = []

        for sentence in sentences:
            for keyword in important_keywords:
                if keyword in sentence:
                    important_sentences.append(sentence)
                    break

        if important_sentences:
            result = " ".join(important_sentences)
            if len(result) > max_length:
                result = self._truncate_to_sentence(result, max_length)
            return result

        # 如果没有找到关键词，返回开头部分
        return self._truncate_to_sentence(text, max_length)
