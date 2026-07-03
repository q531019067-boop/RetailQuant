"""
Agent 会话管理 —— 内存中存储对话历史，支持多轮追问。

会话 30 分钟无活动自动清理。
"""

from __future__ import annotations

import time

_sessions: dict[str, dict] = {}

TTL_SECONDS = 1800  # 30 分钟


def create_session() -> str:
    """创建新会话，返回 session_id。"""
    import uuid

    sid = str(uuid.uuid4())[:12]
    _sessions[sid] = {"messages": [], "created_at": time.time(), "last_access": time.time()}
    return sid


def get_session(sid: str) -> dict | None:
    """获取会话数据，过期返回 None。"""
    s = _sessions.get(sid)
    if s is None:
        return None
    if time.time() - s["last_access"] > TTL_SECONDS:
        del _sessions[sid]
        return None
    s["last_access"] = time.time()
    return s


def append_messages(sid: str, messages: list[dict]) -> None:
    """追加消息到会话历史。"""
    s = get_session(sid)
    if s:
        s["messages"].extend(messages)


def delete_session(sid: str) -> None:
    """删除会话。"""
    _sessions.pop(sid, None)
