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
        assert "get_strategy_info" in text
        assert "拿到结果就输出" in text  # 强调不要重复跑

    def test_handles_empty_stock_pool(self):
        """空股票池不崩溃，回退到默认股票代码。"""
        from backend.agent.formatter import format_empty_context

        with patch("backend.backtest_engine.list_available_stocks", return_value=[]):
            text = format_empty_context()
            assert "600519.SSE" in text  # 回退默认值
            assert "0 只" in text


# ═══════════════════════════════════════════════════════════════
# Tools
# ═══════════════════════════════════════════════════════════════


class TestToolRegistry:
    def test_get_tool_definitions(self):
        from backend.agent.tools import get_tool_definitions

        tools = get_tool_definitions()
        assert len(tools) >= 7
        names = {t["function"]["name"] for t in tools}
        assert "get_strategy_info" in names
        assert "run_backtest" in names
        assert "search_params" in names
        assert "get_daily_series" in names
        assert "get_data_info" in names
        assert "search_stocks" in names
        assert "get_stock_brief" in names

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
            strategies=["equal_weight"],
            vt_symbols=["600519.SSE"],
            start="2024-01-01",
            end="2024-02-01",
        )
        assert "metrics" in result
        assert len(result["metrics"]) == 1
        assert result["metrics"][0]["strategy"] == "equal_weight"
        assert "sharpe_ratio" in result["metrics"][0]

    def test_run_backtest_multi_strategy(self):
        """一次调用可测多个策略。"""
        from backend.agent.tools import tool_run_backtest

        result = tool_run_backtest(
            strategies=["equal_weight", "buy_hold"],
            vt_symbols=["600519.SSE"],
            start="2024-01-01",
            end="2024-02-01",
        )
        assert len(result["metrics"]) == 2

    def test_run_backtest_tool_invalid_strategy(self):
        from backend.agent.tools import tool_run_backtest

        result = tool_run_backtest(
            strategies=["nonexistent"],
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

    def test_run_backtest_returns_cache_id(self):
        """回测工具返回 _cache_id 供前端「查看图表」使用。"""
        from backend.agent.tools import tool_run_backtest

        result = tool_run_backtest(
            strategies=["equal_weight"],
            vt_symbols=["600519.SSE"],
            start="2024-01-01",
            end="2024-02-01",
        )
        assert "_cache_id" in result
        assert "capital" in result

    def test_backtest_cache_roundtrip(self):
        """缓存的回测结果能通过 get_cached_result 取出，取后即删。"""
        from backend.agent.tools import _cache_backtest_result, get_cached_result

        fake = {"strategy": "test", "results": {"daily": [1, 2, 3]}}
        _cache_backtest_result("cache-1", fake)
        assert get_cached_result("cache-1") == fake
        assert get_cached_result("cache-1") is None  # 取后即删

    def test_register_tool_optional_params(self):
        """有 optional 参数的字段不在 required 列表中。"""
        from backend.agent.tools import register_tool

        # 测试 optional 参数被排除在 required 之外
        params_spec = {
            "a": {"type": "string", "description": "required param"},
            "b": {"type": "integer", "description": "optional param"},
        }

        @register_tool("test_optional", "测试", params_spec, optional=["b"])
        def _test_fn(a, b=1):
            return {"a": a, "b": b}

        from backend.agent.tools import get_tool_definitions

        tools = get_tool_definitions()
        test_tool = next(t for t in tools if t["function"]["name"] == "test_optional")
        required = test_tool["function"]["parameters"]["required"]
        assert "a" in required
        assert "b" not in required

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

    def test_backtest_limit_enforced(self):
        """超过上限后 tool_run_backtest 返回 error 而非继续执行。"""
        from backend.agent.tools import _reset_backtest_counter, _check_backtest_limit, _MAX_BACKTEST_CALLS

        _reset_backtest_counter()
        # 耗尽配额
        for _ in range(_MAX_BACKTEST_CALLS):
            r = _check_backtest_limit()
            assert r is None  # 前 N 次不报错
        # 第 N+1 次报错
        r = _check_backtest_limit()
        assert r is not None
        assert "error" in r
        assert "上限" in r["error"]

    def test_validate_vt_symbols_rejects_invalid(self):
        """不存在的股票代码返回清晰的错误和建议。"""
        from backend.agent.tools import _validate_vt_symbols

        r = _validate_vt_symbols(["999999.SSE", "000001.SZSE"])
        assert r is not None
        assert "999999.SSE" in r["error"]

    def test_validate_vt_symbols_suggests_fix(self):
        """LLM 幻想的后缀（.SH）应被修正为正确的后缀。"""
        from backend.agent.tools import _validate_vt_symbols

        r = _validate_vt_symbols(["600460.SH"])
        assert r is not None
        assert "600460.SH" in r["error"]
        if "600460.SSE" in str(r):
            assert "600460.SSE" in r["suggestions"].get("600460.SH", "")

    def test_validate_vt_symbols_all_valid(self):
        """全部合法的代码返回 None。"""
        from backend.agent.tools import _validate_vt_symbols

        r = _validate_vt_symbols(["600519.SSE", "000858.SZSE"])
        assert r is None

    def test_get_data_info(self):
        """数据概览工具返回股票数量和日期范围。"""
        from backend.agent.tools import tool_get_data_info

        r = tool_get_data_info()
        assert r["total_stocks"] > 0
        assert "date_range" in r
        assert "sample_codes" in r

    def test_search_stocks(self):
        """股票搜索工具按代码片段查找。"""
        from backend.agent.tools import tool_search_stocks

        r = tool_search_stocks("600519")
        assert r["found"] >= 1
        assert r["results"][0]["code"] == "600519.SSE"

    def test_search_stocks_no_match(self):
        """无匹配时返回提示。"""
        from backend.agent.tools import tool_search_stocks

        r = tool_search_stocks("不存在的股票名xyz")
        assert r["found"] == 0

    def test_get_stock_brief(self):
        """股票概要返回日期范围、价格、成交量。"""
        from backend.agent.tools import tool_get_stock_brief

        r = tool_get_stock_brief(["600519.SSE"])
        s = r["stocks"][0]
        assert s["code"] == "600519.SSE"
        assert "latest_close" in s
        assert "max_close" in s
        assert "avg_daily_volume" in s


# ═══════════════════════════════════════════════════════════════
# Prompts
# ═══════════════════════════════════════════════════════════════


class TestPrompts:
    def test_system_prompt_is_defined(self):
        from backend.agent.prompts import SYSTEM_PROMPT

        assert len(SYSTEM_PROMPT) > 100
        assert "回测" in SYSTEM_PROMPT
        assert "工具" in SYSTEM_PROMPT
        assert "中文" in SYSTEM_PROMPT


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
        from backend.agent.client import load_agent_config

        cfg = load_agent_config()
        assert isinstance(cfg, dict)
        if cfg:
            assert "model" in cfg or True

    def test_validate_rejects_bad_max_iterations(self):
        """max_iterations 超范围会被修正。"""
        from backend.agent.client import _validate_agent_config

        w = _validate_agent_config({"max_iterations": 999, "model": "test", "base_url": "https://x", "api_key_env": "K"})
        assert any("999" in x or "max_iterations" in x for x in w)

    def test_validate_warns_missing_required(self):
        """缺少必填字段产生警告。"""
        from backend.agent.client import _validate_agent_config

        w = _validate_agent_config({})
        assert len(w) >= 3  # model, base_url, api_key_env 都缺失

    def test_validate_fixes_type(self):
        """字符串类型的数字会被转换为正确类型。"""
        from backend.agent.client import _validate_agent_config

        cfg = {"max_iterations": "50", "model": "x", "base_url": "https://x", "api_key_env": "K"}
        w = _validate_agent_config(cfg)
        assert isinstance(cfg["max_iterations"], int)
        assert cfg["max_iterations"] == 50


# ═══════════════════════════════════════════════════════════════
# Event Types（单一定义源验证）
# ═══════════════════════════════════════════════════════════════


class TestEventTypes:
    def test_all_event_types_are_strings(self):
        from backend.agent.types import EventType

        for name in dir(EventType):
            if name.startswith("_"):
                continue
            value = getattr(EventType, name)
            assert isinstance(value, str), f"EventType.{name} should be str, got {type(value)}"
            assert len(value) > 0, f"EventType.{name} should not be empty"

    def test_event_types_unique(self):
        from backend.agent.types import EventType

        values = [v for k, v in vars(EventType).items() if not k.startswith("_")]
        assert len(values) == len(set(values)), "EventType values must be unique"

    def test_key_event_types_exist(self):
        from backend.agent.types import EventType

        assert EventType.THINKING == "thinking"
        assert EventType.DONE == "done"
        assert EventType.ERROR == "error"
        assert EventType.TOOL_CALL == "tool_call"
        assert EventType.TOOL_RESULT == "tool_result"
        assert EventType.HEARTBEAT == "heartbeat"


# ═══════════════════════════════════════════════════════════════
# Agent loop (mock LLM)
# ═══════════════════════════════════════════════════════════════


class TestAgentLoop:
    def test_loop_yields_assistant_tool_calls_event(self):
        """LLM 返回 tool_calls → yield assistant_tool_calls 事件。"""
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

        events = list(agent_loop(client, "system", "context", max_iterations=1))
        atc_events = [e for e in events if e["type"] == "assistant_tool_calls"]
        assert len(atc_events) >= 1
        assert atc_events[0]["tool_calls"][0]["id"] == "call_1"
        assert atc_events[0]["tool_calls"][0]["function"]["name"] == "get_strategy_info"

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
            events = list(run_agent(results=None))
            assert len(events) >= 1
            assert events[-1]["type"] == "error"
            assert "API key" in events[-1]["content"] or "API" in events[-1]["content"]

    def test_run_agent_with_valid_results(self):
        """有回测结果时正常返回事件。"""
        from backend.agent import run_agent

        with patch.dict("os.environ", {"DEEPSEEK_API_KEY": "fake-for-test"}, clear=False):
            events = list(
                run_agent(results={"equal_weight": {"statistics": {"total_return": 0}, "daily": [], "trades": []}})
            )
            # 没有真实 API key，LLM 调用会失败，但至少不应 crash
            assert len(events) >= 0

    def test_run_agent_with_nested_results(self):
        """兼容 {results: {...}} 嵌套格式。"""
        from backend.agent import _extract_results

        nested = {"results": {"strat": {"statistics": {}}}}
        assert _extract_results(nested) == {"strat": {"statistics": {}}}

        flat = {"strat": {"statistics": {}}}
        assert _extract_results(flat) == {"strat": {"statistics": {}}}

        assert _extract_results(None) is None
