"""
Agent 核心循环 —— 与 LLM 进行 ReAct 式多轮对话，执行工具调用。

设计：
    - 零框架依赖，纯 while 循环 + OpenAI tool calling 协议
    - 通过生成器 yield 结构化事件，供 SSE 流式传输到前端
    - 工具通过注册器动态发现，新增工具无需修改本文件
    - 支持中途取消（客户端断开连接）
"""

from __future__ import annotations

import json
import time
from collections.abc import Generator
from typing import Any

from .client import LLMClient
from .tools import execute_tool, get_tool_definitions
from backend.log import logger


def agent_loop(
    client: LLMClient,
    system_prompt: str,
    user_context: str,
    tools: list[dict] | None = None,
    max_iterations: int = 8,
    timeout_per_step: float = 15.0,
    history: list[dict] | None = None,
) -> Generator[dict[str, Any], None, None]:
    """执行一次 Agent 任务。

    参数：
        client: LLM 客户端
        system_prompt: 系统指令
        user_context: 用户上下文（回测数据、具体问题等）
        tools: 工具定义列表，None 则自动获取全部已注册工具
        max_iterations: 最大循环轮数
        timeout_per_step: 单步 LLM 调用超时秒数

    Yields:
        dict 事件，type 取值为：
            "thinking"   — Agent 的思考文字
            "tool_call"  — 即将执行某个工具
            "tool_result"— 工具执行结果
            "done"       — 任务完成（含最终答案）
            "error"      — 出错
    """
    if tools is None:
        tools = get_tool_definitions()

    if history:
        # 追问模式：复用历史消息，追加新用户消息
        messages = list(history)
        # 替换 system prompt（可能已切换 action）
        if messages and messages[0].get("role") == "system":
            messages[0]["content"] = system_prompt
        else:
            messages.insert(0, {"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_context})
    else:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_context},
        ]

    for step in range(max_iterations):
        logger.info(f"Agent step {step + 1}/{max_iterations}")
        yield {"type": "thinking", "content": f"Step {step + 1}/{max_iterations}..."}

        try:
            response = client.chat(messages, tools, timeout=timeout_per_step)
        except Exception as e:
            logger.error(f"LLM call failed at step {step + 1}: {e}", exc_info=True)
            yield {"type": "error", "content": f"LLM 调用失败: {e}"}
            return

        choice = response.choices[0]
        msg = choice.message

        # 处理 tool calls
        if msg.tool_calls:
            tool_results = []
            for tc in msg.tool_calls:
                tool_name = tc.function.name
                try:
                    tool_args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    tool_args = {}

                yield {
                    "type": "tool_call",
                    "name": tool_name,
                    "arguments": tool_args,
                }

                start = time.time()
                try:
                    result = execute_tool(tool_name, **tool_args)
                except Exception as e:
                    result = {"error": str(e)}
                elapsed = time.time() - start

                yield {
                    "type": "tool_result",
                    "name": tool_name,
                    "result": result,
                    "elapsed_ms": round(elapsed * 1000),
                }

                tool_results.append(
                    {
                        "tool_call_id": tc.id,
                        "role": "tool",
                        "content": json.dumps(result, ensure_ascii=False, default=str),
                    }
                )

            # 注入 assistant + tool 消息到历史
            messages.append({"role": "assistant", "tool_calls": msg.tool_calls})
            messages.extend(tool_results)
            continue

        # 无 tool call —— 任务完成
        content = msg.content or ""
        logger.info(f"Agent done at step {step + 1}, response length: {len(content)}")
        yield {"type": "done", "content": content}
        return

    # 达到最大迭代次数
    yield {"type": "done", "content": "已达到最大分析步数，请缩小问题范围后重试。"}
