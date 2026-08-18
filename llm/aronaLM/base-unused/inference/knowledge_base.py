import sqlite3
import json
from typing import Dict, List, Any
from datetime import datetime
import hashlib

# 知识库系统
class KnowledgeBase:
    def __init__(self, db_path: str = "knowledge.db"):
        self.db_path = db_path
        self._init_database()

    # 初始化数据库
    def _init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # 用户信息表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id TEXT PRIMARY KEY,
                preferences TEXT,
                conversation_style TEXT,
                created_at TIMESTAMP,
                update_at TIMESTAMP
            )
        ''')
        # 事实信息表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS factual_knowledge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT,
                fact TEXT,
                source_conversation TEXT,
                confidence_score REAL,
                created_at TIMESTAMP
            )
        ''')
        # 对话模式表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversation_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_input_pattern TEXT,
                preferred_responce TEXT,
                success_count INTEGER DEFAULT 0
                last_used TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()

    # 保存用户偏好
    def save_user_preference(self, user_id: str, preference: Dict):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO user_profiles(
                user_id,
                preferences,
                updated_at
            )
            VALUES (?, ?, ?)
        ''', (user_id, json.dumps(preference), datetime.now()))