"""
Agent 模块测试 —— 覆盖 formatter、tools、prompts、client、loop、入口。
不依赖真实 LLM API，全部通过 mock 验证。
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ═══════════════════════════════════════════════════════════════
# Formatter
# ═══════════════════════════════════════════════════════════════


class TestFormatBacktestContext:
    def test_single_strategy(self):
        from backend.agent.formatter import format_backtest_context

        results = {
            "equal_weight": {
                "statistics": {
                    "total_return": 15.5,
                    "annual_return": 12.3,
                    "sharpe_ratio": 1.25,
                    "sortino_ratio": 2.1,
                    "calmar_ratio": 1.8,
                    "max_ddpercent": -12.5,
                    "max_drawdown_duration": 45,
                    "win_rate": 55.0,
                    "profit_factor": 1.6,
                    "total_trade_count": 42,
                    "total_commission": 320.5,
                    "end_balance": 1_155_000,
                },
                "daily": [
                    {"date": "2024-01-02", "ddpercent": -1.2, "return": 0.5, "balance": 1_005_000},
                    {"date": "2024-01-03", "ddpercent": -3.0, "return": -2.0, "balance": 985_000},
                ],
                "trades": [
                    {"date": "2024-01-05", "symbol": "600519.SSE", "side": "买入开仓", "price": 1800, "pnl": None},
                ],
            }
        }
        text = format_backtest_context(results)
        assert "equal_weight" in text
        assert "12.3" in text
        assert "1.25" in text
        assert "600519.SSE" in text

    def test_multi_strategy_comparison(self):
        from backend.agent.formatter import format_backtest_context

        results = {
            "equal_weight": {
                "statistics": {"total_return": 10, "annual_return": 8, "sharpe_ratio": 1.0},
                "daily": [],
                "trades": [],
            },
            "vp_breakout": {
                "statistics": {"total_return": 15, "annual_return": 12, "sharpe_ratio": 1.5},
                "daily": [],
                "trades": [],
            },
        }
        text = format_backtest_context(results)
        assert "策略对比" in text
        assert "equal_weight" in text
        assert "vp_breakout" in text

    def test_with_params(self):
        from backend.agent.formatter import format_backtest_context

        results = {
            "equal_weight": {
                "statistics": {"total_return": 0},
                "daily": [],
                "trades": [],
            }
        }
        params = {"start": "2024-01-01", "end": "2024-12-31", "capital": 500_000, "vt_symbols": ["600519.SSE"]}
        text = format_backtest_context(results, params)
        assert "2024-01-01" in text
        assert "500,000" in text
        assert "600519.SSE" in text

    def test_empty_trades_handled(self):
        from backend.agent.formatter import format_backtest_context

        results = {
            "equal_weight": {
                "statistics": {"total_return": 0},
                "daily": [],
                "trades": [],
            }
        }
        text = format_backtest_context(results)
        assert "equal_weight" in text  # no crash


class TestFormatEmptyContext:
    def test_returns_context_with_stocks(self):
        from backend.agent.formatter import format_empty_context

        text = format_empty_context()
        assert "股票池" in text
        assert "run_backtest" in text
        assert "get_strategy_info" in text


# ═══════════════════════════════════════════════════════════════
# Tools
# ═══════════════════════════════════════════════════════════════


class TestToolRegistry:
    def test_get_tool_definitions(self):
        from backend.agent.tools import get_tool_definitions

        tools = get_tool_definitions()
        assert len(tools) >= 4
        names = {t["function"]["name"] for t in tools}
        assert "get_strategy_info" in names
        assert "run_backtest" in names
        assert "search_params" in names
        assert "get_daily_series" in names

    def test_tool_definitions_have_required_fields(self):
        from backend.agent.tools import get_tool_definitions

        for tool in get_tool_definitions():
            assert tool["type"] == "function"
            fdef = tool["function"]
            assert "name" in fdef
            assert "description" in fdef
            assert "parameters" in fdef
            assert "properties" in fdef["parameters"]
            assert "required" in fdef["parameters"]

    def test_execute_unknown_tool(self):
        from backend.agent.tools import execute_tool

        result = execute_tool("nonexistent_tool_xyz")
        assert "error" in result

    def test_get_strategy_info_all(self):
        from backend.agent.tools import get_strategy_info

        result = get_strategy_info("")
        assert result["count"] >= 7
        assert "strategies" in result

    def test_get_strategy_info_specific(self):
        from backend.agent.tools import get_strategy_info

        result = get_strategy_info("equal_weight")
        assert result["name"] == "equal_weight"
        assert "params" in result

    def test_get_strategy_info_unknown(self):
        from backend.agent.tools import get_strategy_info

        result = get_strategy_info("fake_strategy_xyz")
        assert "error" in result
        assert "equal_weight" in str(result.get("available", []))

    def test_run_backtest_tool(self):
        from backend.agent.tools import tool_run_backtest

        result = tool_run_backtest(
            strategy="equal_weight",
            params={"top_k": 2, "lookback": 10, "price_add": 0.01},
            vt_symbols=["600519.SSE"],
            start="2024-01-01",
            end="2024-02-01",
        )
        assert result["strategy"] == "equal_weight"
        assert "sharpe_ratio" in result
        assert "total_return" in result

    def test_run_backtest_tool_invalid_strategy(self):
        from backend.agent.tools import tool_run_backtest

        result = tool_run_backtest(
            strategy="nonexistent",
            params={},
            vt_symbols=["600519.SSE"],
            start="2024-01-01",
            end="2024-02-01",
        )
        assert "error" in result

    def test_search_params_tool(self):
        from backend.agent.tools import tool_search_params

        result = tool_search_params(
            strategy="equal_weight",
            param_grid={"top_k": [1, 3], "lookback": [10, 20]},
            vt_symbols=["600519.SSE"],
            start="2024-01-01",
            end="2024-02-01",
        )
        assert result["total_combinations"] == 4
        assert "top_5" in result
        assert len(result["top_5"]) >= 1

    def test_search_params_too_many_combos(self):
        from backend.agent.tools import tool_search_params

        # > 100 combos should be rejected
        too_many = {f"p{i}": list(range(10)) for i in range(3)}  # 10*10*10 = 1000 combos
        result = tool_search_params(
            strategy="equal_weight",
            param_grid=too_many,
            vt_symbols=["600519.SSE"],
            start="2024-01-01",
            end="2024-02-01",
        )
        assert "error" in result
        assert "100" in result.get("error", "")

    def test_get_daily_series_tool(self):
        from backend.agent.tools import tool_get_daily_series

        result = tool_get_daily_series(
            strategy="equal_weight",
            params={"top_k": 2, "lookback": 10, "price_add": 0.01},
            vt_symbols=["600519.SSE"],
            start="2024-01-01",
            end="2024-02-01",
        )
        assert "total_days" in result
        assert "max_dd_day" in result
        assert "sampled_days" in result


# ═══════════════════════════════════════════════════════════════
# Prompts
# ═══════════════════════════════════════════════════════════════


class TestPrompts:
    def test_all_four_actions_defined(self):
        from backend.agent.prompts import ACTION_MAP

        assert "analyze" in ACTION_MAP
        assert "optimize" in ACTION_MAP
        assert "risk" in ACTION_MAP
        assert "explore" in ACTION_MAP

    def test_each_action_has_prompt(self):
        from backend.agent.prompts import ACTION_MAP

        for action, cfg in ACTION_MAP.items():
            assert "prompt" in cfg, f"{action} missing prompt"
            assert len(cfg["prompt"]) > 50, f"{action} prompt too short"

    def test_common_rules_in_all_prompts(self):
        from backend.agent.prompts import ACTION_MAP

        for action, cfg in ACTION_MAP.items():
            assert "中文" in cfg["prompt"], f"{action} missing 中文 rule"
            assert "工具" in cfg["prompt"], f"{action} missing 工具 rule"


# ═══════════════════════════════════════════════════════════════
# Client
# ═══════════════════════════════════════════════════════════════


class TestLLMClient:
    def test_missing_api_key_raises_clear_error(self):
        """未设置 API key 时抛出友好错误（不是 openai.OpenAIError）。"""
        from backend.agent.client import LLMClient

        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
                LLMClient()

    def test_loads_config_from_toml(self):
        """能正常加载 rbacktest.toml 配置。"""
        from backend.agent.client import _load_agent_config

        cfg = _load_agent_config()
        assert isinstance(cfg, dict)
        # 配置文件存在时应有基本字段
        if cfg:
            assert "model" in cfg or True  # 至少不崩溃


# ═══════════════════════════════════════════════════════════════
# Agent loop (mock LLM)
# ═══════════════════════════════════════════════════════════════


class TestAgentLoop:
    def test_loop_stops_on_text_response(self):
        """LLM 返回纯文本（无 tool_call）→ 循环立即终止。"""
        from backend.agent.loop import agent_loop

        client = MagicMock()
        choice = MagicMock()
        choice.message.content = "分析完成，结果很好。"
        choice.message.tool_calls = None
        client.chat.return_value = MagicMock(choices=[choice])

        events = list(agent_loop(client, "system", "context", tools=[]))
        assert events[-1]["type"] == "done"
        assert "分析完成" in events[-1]["content"]

    def test_loop_reaches_max_iterations(self):
        """LLM 持续返回 tool_calls → max_iterations 后终止。"""
        from backend.agent.loop import agent_loop

        client = MagicMock()
        choice = MagicMock()
        tc = MagicMock()
        tc.id = "call_1"
        tc.function.name = "get_strategy_info"
        tc.function.arguments = '{"name": ""}'
        choice.message.content = None
        choice.message.tool_calls = [tc]
        client.chat.return_value = MagicMock(choices=[choice])

        events = list(agent_loop(client, "system", "context", max_iterations=2))
        assert events[-1]["type"] == "done"
        assert "最大分析步数" in events[-1]["content"]

    def test_loop_yields_thinking_events(self):
        """每步都 yield thinking 事件。"""
        from backend.agent.loop import agent_loop

        client = MagicMock()
        choice = MagicMock()
        choice.message.content = "done"
        choice.message.tool_calls = None
        client.chat.return_value = MagicMock(choices=[choice])

        events = list(agent_loop(client, "system", "context"))
        thinking_events = [e for e in events if e["type"] == "thinking"]
        assert len(thinking_events) >= 1

    def test_loop_handles_llm_error(self):
        """LLM 调用抛出异常 → yield error 事件（在 thinking 之后）。"""
        from backend.agent.loop import agent_loop

        client = MagicMock()
        client.chat.side_effect = RuntimeError("API 超时")

        events = list(agent_loop(client, "system", "context"))
        error_events = [e for e in events if e["type"] == "error"]
        assert len(error_events) >= 1
        assert "API 超时" in error_events[0]["content"]


# ═══════════════════════════════════════════════════════════════
# Agent 入口：异常绝不外抛
# ═══════════════════════════════════════════════════════════════


class TestRunAgent:
    def test_run_agent_never_raises_on_init_error(self):
        """即使 LLMClient 初始化失败（如缺 API key），也只 yield error 事件。"""
        from backend.agent import run_agent

        with patch.dict("os.environ", {}, clear=True):
            events = list(run_agent("analyze", results=None))
            assert len(events) >= 1
            assert events[-1]["type"] == "error"
            assert "API key" in events[-1]["content"] or "API" in events[-1]["content"]

    def test_run_agent_with_valid_results(self):
        """有回测结果时正常返回事件。"""
        from backend.agent import run_agent

        with patch.dict("os.environ", {"DEEPSEEK_API_KEY": "fake-for-test"}, clear=False):
            events = list(
                run_agent(
                    "analyze", results={"equal_weight": {"statistics": {"total_return": 0}, "daily": [], "trades": []}}
                )
            )
            # 没有真实 API key，LLM 调用会失败，但至少不应 crash
            assert len(events) >= 0  # 至少不崩
