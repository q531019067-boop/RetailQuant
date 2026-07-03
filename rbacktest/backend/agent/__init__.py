"""
Agent 模块入口。

用法:
    from backend.agent import run_agent, EventType

    for event in run_agent(results, params, user_question="帮我分析"):
        send_to_frontend(event)

绝对不会 raise —— 所有异常转为 {"type": "error", ...} 事件。
"""

from __future__ import annotations

import json
from collections.abc import Generator
from typing import Any

from backend.log import logger

from .client import LLMClient, load_agent_config
from .formatter import format_backtest_context, format_empty_context
from .loop import agent_loop
from .prompts import SYSTEM_PROMPT
from .tools import get_tool_definitions
from .types import EventType


def _reset_session_state() -> None:
    """每次新会话时重置全局计数器。"""
    from .tools import _reset_backtest_counter

    _reset_backtest_counter()


def run_agent(
    results: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    user_question: str = "",
    session_id: str | None = None,
) -> Generator[dict[str, Any], None, None]:
    """执行一次 Agent 任务。顶层兜底，所有异常转 error 事件。"""
    try:
        yield from _impl(results, params, user_question, session_id)
    except Exception as e:
        logger.error(f"run_agent 未捕获异常: {e}", exc_info=True)
        yield {"type": "error", "content": f"Agent 内部错误: {e}"}


def _impl(
    results: dict[str, Any] | None,
    params: dict[str, Any] | None,
    user_question: str,
    session_id: str | None,
) -> Generator[dict[str, Any], None, None]:
    """Agent 核心实现。"""
    from .session import append_messages, create_session, get_session

    # 构建上下文：有回测数据就带上摘要，否则给可用资源
    if user_question:
        context_lines = [user_question]
        if results:
            extracted = _extract_results(results)
            if extracted:
                context_lines.append("\n## 当前回测数据")
                context_lines.append(format_backtest_context(extracted, params))
        context = "\n".join(context_lines)
    elif results:
        extracted = _extract_results(results)
        context = format_backtest_context(extracted, params) if extracted else format_empty_context()
    else:
        context = format_empty_context()

    tools = get_tool_definitions()
    client = LLMClient()

    # 会话管理：追问时从 session 加载历史
    history: list[dict] | None = None
    if session_id:
        sess = get_session(session_id)
        if sess:
            history = sess["messages"]
    if not session_id:
        _reset_session_state()
        session_id = create_session()
        yield {"type": EventType.META, "session_id": session_id}

    # 执行循环
    cfg = load_agent_config()
    max_iterations = int(cfg.get("max_iterations", 100))
    timeout_per_step = float(cfg.get("timeout_per_step", 15))
    loop_messages: list[dict] = []
    pending_tool_calls: list[dict] | None = None
    tool_result_cnt = 0
    for event in agent_loop(
        client=client,
        system_prompt=SYSTEM_PROMPT,
        user_context=context,
        tools=tools,
        max_iterations=max_iterations,
        timeout_per_step=timeout_per_step,
        history=history,
    ):
        yield event
        if event["type"] == EventType.ASSISTANT_TOOL_CALLS:
            pending_tool_calls = event.get("tool_calls", [])
            if pending_tool_calls:
                loop_messages.append({"role": "assistant", "tool_calls": pending_tool_calls})
            tool_result_cnt = 0
        elif event["type"] == EventType.TOOL_CALL:
            pass
        elif event["type"] == EventType.TOOL_RESULT:
            tc_id = ""
            if pending_tool_calls and tool_result_cnt < len(pending_tool_calls):
                tc_id = pending_tool_calls[tool_result_cnt].get("id", "")
            tool_result_cnt += 1
            msg: dict = {"role": "tool", "content": json.dumps(event.get("result", {}), ensure_ascii=False, default=str)}
            if tc_id:
                msg["tool_call_id"] = tc_id
            loop_messages.append(msg)
        elif event["type"] == EventType.DONE:
            loop_messages.append({"role": "assistant", "content": event["content"]})

    if session_id and loop_messages:
        append_messages(session_id, loop_messages)


def _extract_results(results: dict[str, Any] | None) -> dict[str, Any] | None:
    """从前端传来的 results 中提取策略结果字典。"""
    if not results:
        return None
    # 兼容两种格式：{results: {strat: ...}} 和 {strat: ...}
    if "results" in results:
        return results["results"]
    return results
