"""
Agent 事件类型常量 —— 单一定义源。

loop.py 和 __init__.py 都引用此模块，避免循环导入。
"""

from __future__ import annotations


class EventType:
    """Agent 流式事件的类型定义。"""

    THINKING = "thinking"
    TOOL_CALL = "tool_call"
    ASSISTANT_TOOL_CALLS = "assistant_tool_calls"
    TOOL_RESULT = "tool_result"
    DONE = "done"
    ERROR = "error"
    HEARTBEAT = "heartbeat"
    META = "meta"
