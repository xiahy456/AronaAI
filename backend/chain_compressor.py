"""
链路压缩模块 - 对RAG检索结果进行压缩和优化
减少传递给模型的上下文长度，提升推理效率
"""
import re
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

        max_length = max_length or self.max_context_length

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

            # 检查是否超出长度限制
            if current_length + len(compressed_text) > max_length:
                # 如果还有空间，截断并添加
                remaining = max_length - current_length
                if remaining > 50:  # 至少保留50个字符
                    compressed_parts.append(compressed_text[:remaining])
                break

            compressed_parts.append(compressed_text)
            current_length += len(compressed_text)

        return "\n---\n".join(compressed_parts)

    def _deduplicate(self, documents: List[Dict]) -> List[Dict]:
        """去重 - 基于文本相似度"""
        unique = []
        seen_texts = set()

        for doc in documents:
            # 使用文本的前50个字符作为去重依据
            text_key = doc["document"][:50].strip()
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

        # 给每个句子打分
        scored_sentences = []
        for sentence in sentences:
            sentence_lower = sentence.lower()
            score = 0

            # 关键词匹配
            for keyword in query_keywords:
                if keyword.lower() in sentence_lower:
                    score += 2

            # 位置权重（开头和结尾的句子更重要）
            idx = sentences.index(sentence)
            if idx == 0 or idx == len(sentences) - 1:
                score += 1

            scored_sentences.append((sentence, score))

        # 按分数排序，取前N个句子
        scored_sentences.sort(key=lambda x: x[1], reverse=True)
        top_n = max(2, int(len(sentences) * self.summary_ratio))
        selected = [s[0] for s in scored_sentences[:top_n]]

        # 按原文顺序重新排列
        ordered = []
        for sentence in sentences:
            if sentence in selected:
                ordered.append(sentence)

        return " ".join(ordered)

    def _tokenize(self, text: str) -> List[str]:
        """简单分词"""
        # 按非字母数字字符分割
        tokens = re.findall(r'[\w\u4e00-\u9fff]+', text)
        return tokens

    def _split_sentences(self, text: str) -> List[str]:
        """分句"""
        # 按句号、问号、感叹号、换行分割
        sentences = re.split(r'[。！？\n]', text)
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
                result = result[:max_length]
            return result

        # 如果没有找到关键词，返回开头部分
        return text[:max_length]
