"""
对话管理模块 - 管理多轮对话历史和会话状态
"""
import time
import json
import os
from typing import List, Dict, Optional
from backend.config import CONVERSATION_CONFIG


class ConversationManager:
    """
    对话管理器 - 管理每个用户/会话的对话历史
    支持会话过期、历史截断等
    """

    def __init__(self):
        self.max_history_turns = CONVERSATION_CONFIG["max_history_turns"]
        self.max_history_tokens = CONVERSATION_CONFIG["max_history_tokens"]
        self.session_ttl = CONVERSATION_CONFIG["session_ttl"]

        # 会话存储: {session_id: {"messages": [...], "last_active": timestamp}}
        self.sessions: Dict[str, Dict] = {}

    def _clean_expired_sessions(self):
        """清理过期会话"""
        now = time.time()
        expired = [
            sid for sid, session in self.sessions.items()
            if now - session["last_active"] > self.session_ttl
        ]
        for sid in expired:
            del self.sessions[sid]

    def create_session(self, session_id: str) -> str:
        """
        创建新会话

        Args:
            session_id: 会话ID

        Returns:
            会话ID
        """
        self.sessions[session_id] = {
            "messages": [],
            "last_active": time.time(),
            "created_at": time.time()
        }
        return session_id

    def get_session(self, session_id: str) -> Optional[Dict]:
        """
        获取会话

        Args:
            session_id: 会话ID

        Returns:
            会话数据，不存在则返回None
        """
        self._clean_expired_sessions()
        session = self.sessions.get(session_id)
        if session:
            session["last_active"] = time.time()
        return session

    def add_message(self, session_id: str, role: str, content: str) -> List[Dict]:
        """
        添加消息到会话历史

        Args:
            session_id: 会话ID
            role: 角色 (user/assistant)
            content: 消息内容

        Returns:
            更新后的消息列表
        """
        session = self.get_session(session_id)
        if session is None:
            session = self.sessions.setdefault(session_id, {
                "messages": [],
                "last_active": time.time(),
                "created_at": time.time()
            })

        session["messages"].append({
            "role": role,
            "content": content,
            "timestamp": time.time()
        })
        session["last_active"] = time.time()

        # 截断历史
        self._truncate_history(session)

        return session["messages"]

    def _truncate_history(self, session: Dict):
        """
        截断历史对话，控制token数量

        Args:
            session: 会话数据
        """
        messages = session["messages"]

        # 先按轮次截断
        if len(messages) > self.max_history_turns * 2:
            # 保留最近的 max_history_turns 轮
            messages[:] = messages[-(self.max_history_turns * 2):]

        # 再按token数截断（粗略估计：中文字符≈1.5 token，英文≈0.3 token）
        total_tokens = 0
        truncated = []
        for msg in reversed(messages):
            # 粗略估计token数
            char_count = len(msg["content"])
            estimated_tokens = int(char_count * 0.8)  # 中文为主的估计
            if total_tokens + estimated_tokens > self.max_history_tokens:
                break
            total_tokens += estimated_tokens
            truncated.insert(0, msg)

        session["messages"] = truncated

    def get_history(self, session_id: str) -> List[Dict]:
        """
        获取对话历史（用于模型输入的格式）

        Args:
            session_id: 会话ID

        Returns:
            格式化的历史消息列表 [{"role": "user"/"assistant", "content": "..."}]
        """
        session = self.get_session(session_id)
        if session is None:
            return []

        history = []
        for msg in session["messages"]:
            history.append({
                "role": msg["role"],
                "content": msg["content"]
            })

        return history

    def get_recent_history(self, session_id: str, turns: int = 3) -> List[Dict]:
        """
        获取最近的几轮对话历史

        Args:
            session_id: 会话ID
            turns: 轮次数

        Returns:
            最近几轮的历史消息
        """
        session = self.get_session(session_id)
        if session is None:
            return []

        messages = session["messages"]
        recent = messages[-(turns * 2):]

        history = []
        for msg in recent:
            history.append({
                "role": msg["role"],
                "content": msg["content"]
            })

        return history

    def clear_session(self, session_id: str):
        """清空会话"""
        if session_id in self.sessions:
            del self.sessions[session_id]

    def get_session_count(self) -> int:
        """获取活跃会话数量"""
        self._clean_expired_sessions()
        return len(self.sessions)

    def get_all_session_ids(self) -> List[str]:
        """获取所有会话ID"""
        self._clean_expired_sessions()
        return list(self.sessions.keys())
