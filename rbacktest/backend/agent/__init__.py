"""
Agent 模块入口。

用法:
    from backend.agent import run_agent

    for event in run_agent("analyze", results, params):
        send_to_frontend(event)

绝对不会 raise —— 所有异常转为 {"type": "error", ...} 事件。
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

from backend.log import logger

from .client import LLMClient
from .formatter import format_backtest_context, format_empty_context
from .loop import agent_loop
from .prompts import ACTION_MAP
from .tools import get_tool_definitions


def run_agent(
    action: str,
    results: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    user_question: str = "",
    history: list[dict] | None = None,
    session_id: str | None = None,
) -> Generator[dict[str, Any], None, None]:
    """执行一次 Agent 任务。顶层兜底，所有异常转 error 事件。"""
    try:
        yield from _impl(action, results, params, user_question, history, session_id)
    except Exception as e:
        logger.error(f"run_agent 未捕获异常: {e}", exc_info=True)
        yield {"type": "error", "content": f"Agent 内部错误: {e}"}


def _impl(
    action: str,
    results: dict[str, Any] | None,
    params: dict[str, Any] | None,
    user_question: str,
    history: list[dict] | None,
    session_id: str | None,
) -> Generator[dict[str, Any], None, None]:
    """Agent 核心实现。"""
    from .session import append_messages, create_session, get_session

    action_cfg = ACTION_MAP.get(action, ACTION_MAP["analyze"])
    system_prompt = action_cfg["prompt"]

    # 构建上下文
    if user_question:
        context = user_question
    elif results and results.get("results"):
        context = format_backtest_context(results.get("results", {}), params)
    elif results:
        context = format_backtest_context(results, params)
    else:
        context = format_empty_context()

    # 工具
    tool_names = action_cfg.get("tools", [])
    if tool_names:
        all_tools = get_tool_definitions()
        tools = [t for t in all_tools if t["function"]["name"] in tool_names]
    else:
        tools = get_tool_definitions()

    client = LLMClient()

    # 会话管理
    if session_id:
        sess = get_session(session_id)
        if sess:
            history = sess["messages"]
    if not session_id:
        session_id = create_session()
        yield {"type": "meta", "session_id": session_id}

    # 执行循环，同时收集消息用于会话持久化
    loop_messages: list[dict] = []
    for event in agent_loop(
        client=client,
        system_prompt=system_prompt,
        user_context=context,
        tools=tools,
        history=history,
    ):
        yield event
        # 收集 assistant tool_calls、tool 结果、最终回复
        if event["type"] == "tool_call":
            pass  # 由 tool_result 补全
        elif event["type"] == "tool_result":
            loop_messages.append({"role": "tool", "content": f"{event['name']}: {event.get('result', {})}"})
        elif event["type"] == "done":
            loop_messages.append({"role": "assistant", "content": event["content"]})

    # 持久化会话历史
    if session_id and loop_messages:
        append_messages(session_id, loop_messages)
