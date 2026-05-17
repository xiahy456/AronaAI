"""
Arona AI WebSocket 服务主程序
使用 WebSocket 与单个客户端连接，接收输入并返回模型输出
"""
import sys
import os
import json
import asyncio
import logging
import uuid
from typing import Optional, Dict, Any
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from backend.arona_engine import AronaEngine

# ========== 日志配置 ==========
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("AronaAI-Service")

# ========== FastAPI 应用 ==========
app = FastAPI(
    title="Arona AI WebSocket Service",
    description="Arona AI 后端 WebSocket 服务（单客户端模式）",
    version="1.0.0",
)

# ========== 全局引擎实例（单例） ==========
_engine: Optional[AronaEngine] = None
_current_session_id: Optional[str] = None


def get_engine() -> AronaEngine:
    """获取或初始化引擎实例（懒加载）"""
    global _engine
    if _engine is None:
        logger.info("正在初始化 Arona AI 引擎...")
        _engine = AronaEngine()
        logger.info("Arona AI 引擎初始化完成")
    return _engine


# ========== 消息协议定义 ==========
"""
客户端 -> 服务端消息格式:

1. 对话请求:
{
    "type": "chat",
    "content": "用户输入文本",
    "options": {
        "use_cache": true,
        "use_rag": true,
        "use_memory": true
    }
}

2. 清空会话:
{
    "type": "clear_session"
}

3. 获取统计信息:
{
    "type": "get_stats"
}

4. 心跳:
{
    "type": "ping"
}


服务端 -> 客户端消息格式:

1. 对话响应（完整）:
{
    "type": "chat_response",
    "content": "模型回复文本",
    "from_cache": false,
    "context_used": true,
    "latency": 1.234,
    "timestamp": "2024-01-01T12:00:00"
}

2. 对话响应（流式）:
{
    "type": "chat_stream",
    "content": "文本片段",
    "done": false
}
... 最后一条:
{
    "type": "chat_stream",
    "content": "",
    "done": true,
    "from_cache": false,
    "context_used": true,
    "latency": 1.234
}

3. 错误响应:
{
    "type": "error",
    "code": "ERROR_CODE",
    "message": "错误描述"
}

4. 心跳响应:
{
    "type": "pong",
    "timestamp": "2024-01-01T12:00:00"
}

5. 操作结果:
{
    "type": "result",
    "success": true,
    "message": "操作成功"
}
"""


# ========== 消息处理函数 ==========

async def handle_chat(websocket: WebSocket, data: Dict[str, Any]):
    """
    处理对话请求
    支持流式和非流式两种模式
    """
    global _current_session_id
    engine = get_engine()
    content = data.get("content", "").strip()
    options = data.get("options", {})
    stream = data.get("stream", False)

    if not content:
        await websocket.send_json({
            "type": "error",
            "code": "EMPTY_CONTENT",
            "message": "输入内容不能为空"
        })
        return

    use_cache = options.get("use_cache", True)
    use_rag = options.get("use_rag", True)
    use_memory = options.get("use_memory", True)

    logger.info(f"收到对话请求 | content: {content[:50]}...")

    try:
        if stream:
            # ===== 流式模式 =====
            result = engine.chat(
                user_input=content,
                session_id=_current_session_id,
                use_cache=use_cache,
                use_rag=use_rag,
                use_memory=use_memory
            )

            response_text = result["response"]
            # 按标点符号分割，模拟流式输出
            import re
            parts = re.split(r'([，。！？、；：\n])', response_text)
            buffer = ""
            for part in parts:
                if not part:
                    continue
                buffer += part
                if part in "，。！？、；：\n" or len(buffer) >= 20:
                    await websocket.send_json({
                        "type": "chat_stream",
                        "content": buffer,
                        "done": False
                    })
                    buffer = ""
                    await asyncio.sleep(0.02)

            if buffer:
                await websocket.send_json({
                    "type": "chat_stream",
                    "content": buffer,
                    "done": False
                })

            # 流式结束标记
            await websocket.send_json({
                "type": "chat_stream",
                "content": "",
                "done": True,
                "from_cache": result["from_cache"],
                "context_used": result["context_used"],
                "latency": result["latency"]
            })
        else:
            # ===== 非流式模式 =====
            result = engine.chat(
                user_input=content,
                session_id=_current_session_id,
                use_cache=use_cache,
                use_rag=use_rag,
                use_memory=use_memory
            )

            await websocket.send_json({
                "type": "chat_response",
                "content": result["response"],
                "from_cache": result["from_cache"],
                "context_used": result["context_used"],
                "latency": round(result["latency"], 3),
                "memories_stored": result["memories_stored"],
                "timestamp": datetime.now().isoformat()
            })

    except Exception as e:
        logger.error(f"对话处理失败 | 错误: {e}", exc_info=True)
        await websocket.send_json({
            "type": "error",
            "code": "CHAT_ERROR",
            "message": f"对话处理失败: {str(e)}"
        })


async def handle_clear_session(websocket: WebSocket):
    """处理清空会话请求"""
    global _current_session_id
    engine = get_engine()

    try:
        engine.clear_session(_current_session_id)
        # 清空后重新创建会话
        _current_session_id = engine.create_session()
        await websocket.send_json({
            "type": "result",
            "success": True,
            "message": "会话已清空并重置"
        })
        logger.info("会话已清空并重置")
    except Exception as e:
        logger.error(f"清空会话失败 | 错误: {e}")
        await websocket.send_json({
            "type": "error",
            "code": "CLEAR_ERROR",
            "message": f"清空会话失败: {str(e)}"
        })


async def handle_get_stats(websocket: WebSocket):
    """处理获取统计信息请求"""
    engine = get_engine()

    try:
        stats = engine.get_stats()
        stats["timestamp"] = datetime.now().isoformat()

        await websocket.send_json({
            "type": "stats",
            "data": stats
        })
    except Exception as e:
        logger.error(f"获取统计信息失败 | 错误: {e}")
        await websocket.send_json({
            "type": "error",
            "code": "STATS_ERROR",
            "message": f"获取统计信息失败: {str(e)}"
        })


async def handle_list_knowledge(websocket: WebSocket):
    """处理列出知识库请求"""
    engine = get_engine()

    try:
        items = engine.list_knowledge()
        await websocket.send_json({
            "type": "knowledge_list",
            "data": {
                "items": items,
                "total": len(items)
            },
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"列出知识库失败 | 错误: {e}")
        await websocket.send_json({
            "type": "error",
            "code": "KNOWLEDGE_LIST_ERROR",
            "message": f"列出知识库失败: {str(e)}"
        })


async def handle_search_knowledge(websocket: WebSocket, data: Dict[str, Any]):
    """处理搜索知识库请求"""
    engine = get_engine()
    query = data.get("query", "").strip()
    k = data.get("k", 3)

    if not query:
        await websocket.send_json({
            "type": "error",
            "code": "EMPTY_QUERY",
            "message": "搜索关键词不能为空"
        })
        return

    try:
        items = engine.search_knowledge(query, k=k)
        await websocket.send_json({
            "type": "knowledge_search",
            "data": {
                "query": query,
                "items": items,
                "total": len(items)
            },
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"搜索知识库失败 | 错误: {e}")
        await websocket.send_json({
            "type": "error",
            "code": "KNOWLEDGE_SEARCH_ERROR",
            "message": f"搜索知识库失败: {str(e)}"
        })


async def handle_add_knowledge(websocket: WebSocket, data: Dict[str, Any]):
    """处理添加知识请求"""
    engine = get_engine()
    content = data.get("content", data.get("text", "")).strip()
    source = data.get("source", "")

    if not content:
        await websocket.send_json({
            "type": "error",
            "code": "EMPTY_KNOWLEDGE_CONTENT",
            "message": "知识内容不能为空"
        })
        return

    try:
        ids = engine.add_knowledge(content, source=source)
        await websocket.send_json({
            "type": "result",
            "success": True,
            "message": "知识已添加",
            "ids": ids,
            "count": len(ids)
        })
    except Exception as e:
        logger.error(f"添加知识失败 | 错误: {e}")
        await websocket.send_json({
            "type": "error",
            "code": "KNOWLEDGE_ADD_ERROR",
            "message": f"添加知识失败: {str(e)}"
        })


async def handle_delete_knowledge(websocket: WebSocket, data: Dict[str, Any]):
    """处理删除知识请求"""
    engine = get_engine()
    ids = data.get("ids", [])

    if not isinstance(ids, list) or not ids:
        await websocket.send_json({
            "type": "error",
            "code": "EMPTY_KNOWLEDGE_IDS",
            "message": "删除ID列表不能为空"
        })
        return

    try:
        deleted_count = engine.delete_knowledge(ids)
        await websocket.send_json({
            "type": "result",
            "success": True,
            "message": "知识已删除",
            "deleted_count": deleted_count
        })
    except Exception as e:
        logger.error(f"删除知识失败 | 错误: {e}")
        await websocket.send_json({
            "type": "error",
            "code": "KNOWLEDGE_DELETE_ERROR",
            "message": f"删除知识失败: {str(e)}"
        })


async def handle_clear_knowledge(websocket: WebSocket):
    """处理清空知识库请求"""
    engine = get_engine()

    try:
        engine.clear_knowledge()
        await websocket.send_json({
            "type": "result",
            "success": True,
            "message": "知识库已清空"
        })
    except Exception as e:
        logger.error(f"清空知识库失败 | 错误: {e}")
        await websocket.send_json({
            "type": "error",
            "code": "KNOWLEDGE_CLEAR_ERROR",
            "message": f"清空知识库失败: {str(e)}"
        })


async def handle_get_knowledge_stats(websocket: WebSocket):
    """处理获取知识库统计请求"""
    engine = get_engine()

    try:
        stats = engine.get_knowledge_stats()
        stats["timestamp"] = datetime.now().isoformat()
        await websocket.send_json({
            "type": "knowledge_stats",
            "data": stats
        })
    except Exception as e:
        logger.error(f"获取知识库统计失败 | 错误: {e}")
        await websocket.send_json({
            "type": "error",
            "code": "KNOWLEDGE_STATS_ERROR",
            "message": f"获取知识库统计失败: {str(e)}"
        })


async def handle_ping(websocket: WebSocket):
    """处理心跳请求"""
    await websocket.send_json({
        "type": "pong",
        "timestamp": datetime.now().isoformat()
    })


# ========== 消息路由 ==========

async def route_message(websocket: WebSocket, data: Dict[str, Any]):
    """消息路由 - 根据 type 分发到对应的处理函数"""
    msg_type = data.get("type", "")

    if msg_type == "chat":
        await handle_chat(websocket, data)
    elif msg_type == "clear_session":
        await handle_clear_session(websocket)
    elif msg_type == "get_stats":
        await handle_get_stats(websocket)
    elif msg_type == "list_knowledge":
        await handle_list_knowledge(websocket)
    elif msg_type == "search_knowledge":
        await handle_search_knowledge(websocket, data)
    elif msg_type == "add_knowledge":
        await handle_add_knowledge(websocket, data)
    elif msg_type == "delete_knowledge":
        await handle_delete_knowledge(websocket, data)
    elif msg_type == "clear_knowledge":
        await handle_clear_knowledge(websocket)
    elif msg_type == "get_knowledge_stats":
        await handle_get_knowledge_stats(websocket)
    elif msg_type == "ping":
        await handle_ping(websocket)
    else:
        await websocket.send_json({
            "type": "error",
            "code": "UNKNOWN_TYPE",
            "message": f"未知的消息类型: {msg_type}"
        })


# ========== WebSocket 端点 ==========

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket 主端点
    单客户端模式：只接受一个客户端连接
    """
    global _current_session_id

    await websocket.accept()

    # 初始化引擎和会话
    engine = get_engine()
    _current_session_id = engine.create_session()

    logger.info(f"客户端已连接 | session_id: {_current_session_id}")

    try:
        # 发送连接成功消息
        await websocket.send_json({
            "type": "connected",
            "message": "已连接到 Arona AI 服务",
            "session_id": _current_session_id,
            "timestamp": datetime.now().isoformat()
        })

        while True:
            raw_data = await websocket.receive_text()

            try:
                data = json.loads(raw_data)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "code": "INVALID_JSON",
                    "message": "无效的 JSON 格式"
                })
                continue

            await route_message(websocket, data)

    except WebSocketDisconnect:
        logger.info("客户端已断开连接")
    except Exception as e:
        logger.error(f"WebSocket 异常 | 错误: {e}", exc_info=True)
    finally:
        _current_session_id = None


# ========== HTTP 端点 ==========

@app.get("/")
async def root():
    """根路径 - 返回服务信息"""
    return {
        "service": "Arona AI WebSocket Service",
        "version": "1.0.0",
        "status": "running",
        "client_connected": _current_session_id is not None,
        "endpoints": {
            "websocket": "/ws",
            "health": "/health"
        }
    }


@app.get("/health")
async def health_check():
    """健康检查端点"""
    engine_loaded = _engine is not None
    return {
        "status": "healthy" if engine_loaded else "initializing",
        "engine_loaded": engine_loaded,
        "client_connected": _current_session_id is not None,
        "timestamp": datetime.now().isoformat()
    }


# ========== 启动入口 ==========

def start_server(host: str = "0.0.0.0", port: int = 20456, reload: bool = False):
    """
    启动 WebSocket 服务

    Args:
        host: 监听地址，默认 0.0.0.0
        port: 监听端口，默认 20456
        reload: 是否启用热重载（开发模式）
    """
    logger.info(f"正在启动 Arona AI WebSocket 服务（单客户端模式）...")
    logger.info(f"监听地址: {host}:{port}")
    logger.info(f"WebSocket 端点: ws://{host}:{port}/ws")
    logger.info(f"健康检查: http://{host}:{port}/health")

    uvicorn.run(
        "backend.ai_service:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
        ws_max_size=1024 * 1024,
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Arona AI WebSocket 服务（单客户端模式）")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="监听地址")
    parser.add_argument("--port", type=int, default=20456, help="监听端口")
    parser.add_argument("--reload", action="store_true", help="启用热重载（开发模式）")
    args = parser.parse_args()

    start_server(host=args.host, port=args.port, reload=args.reload)
