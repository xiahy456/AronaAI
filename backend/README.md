# 后端说明
## 目录结构
├── `backend`
    ├── `app` --后端组件
    ├── `tests` --测试
    ├── `data` --数据
    ├── `utils` --工具
    ├── `third-party` --第三方
    ├── `README.md` --后端说明文档
    └── `main.py` --程序入口

## 后端分层架构
    1. Presentation 前端交互层
    2. DialogueManager 对话管理层
    3. CoreAbilities 核心功能层
       - Memory 记忆模块
       - Emotion 情绪模块
       - Knowledge 知识检索
       - Personality 人格引擎
    4. LLM (Large Language Model) 大模型层
    5. DAO (Data Access Object) 数据持久层
