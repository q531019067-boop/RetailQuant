"""
Agent 工具注册与执行。

设计：
    - 装饰器 @register_tool 自动注册，新增工具只需一个函数 + 装饰器
    - 工具函数接收基本类型参数（str/int/float/list），不暴露内部对象
    - 返回纯 dict（JSON-safe），便于 LLM 消费
    - get_tool_definitions() 自动生成 OpenAI function calling 格式
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# 确保 backend 可导入
_PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(_PROJECT_DIR))

from backend.backtest_engine import run_backtest as _engine_run_backtest  # noqa: E402
from backend.strategy import list_strategies_metadata  # noqa: E402
from backend.log import logger  # noqa: E402

# ---------------------------------------------------------------------------
# 注册器
# ---------------------------------------------------------------------------

_registry: dict[str, dict] = {}


def register_tool(name: str, description: str, parameters: dict):
    """装饰器：将函数注册为 Agent 可用工具。

    用法:
        @register_tool("run_backtest", "运行回测", {...})
        def run_backtest(strategy: str, ...): ...
    """

    def decorator(fn):
        _registry[name] = {
            "function": fn,
            "definition": {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": {
                        "type": "object",
                        "properties": parameters,
                        "required": list(parameters.keys()),
                    },
                },
            },
        }
        return fn

    return decorator


def get_tool_definitions() -> list[dict]:
    """返回已注册工具的 OpenAI function calling 定义列表。"""
    return [t["definition"] for t in _registry.values()]


def execute_tool(name: str, **kwargs) -> dict[str, Any]:
    """执行已注册工具，返回 JSON-safe 结果。"""
    if name not in _registry:
        logger.warning(f"Agent 尝试调用未知工具: {name!r}，可用: {list(_registry.keys())}")
        return {"error": f"未知工具: {name!r}。可用: {list(_registry.keys())}"}
    logger.info(f"Agent 调用工具: {name}({_summarize_kwargs(kwargs)})")
    fn = _registry[name]["function"]
    try:
        result = fn(**kwargs)
        if "error" in result:
            logger.warning(f"工具 {name} 返回错误: {result['error']}")
        else:
            logger.debug(f"工具 {name} 执行成功，结果 keys: {list(result.keys())}")
        return result
    except Exception as e:
        logger.error(f"工具 {name} 执行失败: {e}", exc_info=True)
        return {"error": f"{name} 执行异常: {e}"}


def _summarize_kwargs(kwargs: dict) -> str:
    """压缩日志中的参数显示。"""
    parts = []
    for k, v in kwargs.items():
        if isinstance(v, list):
            parts.append(f"{k}=[{len(v)} items]")
        elif isinstance(v, dict):
            parts.append(f"{k}={{...{len(v)} keys}}")
        elif isinstance(v, str) and len(v) > 40:
            parts.append(f"{k}='{v[:40]}...'")
        else:
            parts.append(f"{k}={v!r}")
    return ", ".join(parts)


# ---------------------------------------------------------------------------
# 工具 1: 获取策略信息
# ---------------------------------------------------------------------------


@register_tool(
    name="get_strategy_info",
    description="获取某个策略的名称、描述、可调参数列表及取值范围。用于在优化前了解可调选项。如果 name 为空则返回全部策略列表。",
    parameters={
        "name": {
            "type": "string",
            "description": "策略名（如 equal_weight），传空字符串返回全部策略列表",
        },
    },
)
def get_strategy_info(name: str = "") -> dict:
    """返回策略元数据。"""
    all_meta = list_strategies_metadata()
    if not name:
        return {
            "count": len(all_meta),
            "strategies": [
                {
                    "name": s["name"],
                    "label": s["label"],
                    "description": s["description"],
                    "param_count": len(s["params"]),
                }
                for s in all_meta
            ],
        }
    for s in all_meta:
        if s["name"] == name:
            return s
    return {"error": f"未找到策略: {name!r}", "available": [s["name"] for s in all_meta]}


# ---------------------------------------------------------------------------
# 工具 2: 单次回测
# ---------------------------------------------------------------------------


@register_tool(
    name="run_backtest",
    description="运行单次回测，返回详细统计指标。用于验证某个具体的参数组合。每次只测一个策略。",
    parameters={
        "strategy": {"type": "string", "description": "策略名，如 equal_weight"},
        "params": {"type": "object", "description": "策略参数字典，如 {'top_k': 5, 'lookback': 20}"},
        "vt_symbols": {
            "type": "array",
            "items": {"type": "string"},
            "description": "股票代码列表，如 ['600519.SSE', '000858.SZSE']，最多 20 只",
        },
        "start": {"type": "string", "description": "起始日期，格式 YYYY-MM-DD"},
        "end": {"type": "string", "description": "结束日期，格式 YYYY-MM-DD"},
        "capital": {"type": "integer", "description": "初始资金，默认 1000000"},
    },
)
def tool_run_backtest(
    strategy: str,
    params: dict,
    vt_symbols: list[str],
    start: str,
    end: str,
    capital: int = 1_000_000,
) -> dict:
    """执行单次回测并压缩返回关键指标。"""
    # 安全限制
    vt_symbols = vt_symbols[:20]
    try:
        result = _engine_run_backtest(
            {
                "vt_symbols": vt_symbols,
                "start": start,
                "end": end,
                "capital": capital,
                "strategies": [strategy],
                "strategy_params": {strategy: params},
            }
        )
    except Exception as e:
        logger.error(f"run_backtest tool failed: {e}", exc_info=True)
        return {"error": str(e)}

    strat_result = result["results"].get(strategy, {})
    stats = strat_result.get("statistics", {})

    # 只返回 Agent 关心的关键指标
    key_metrics = {
        "strategy": strategy,
        "params": params,
        "vt_symbols": vt_symbols,
        "start": start,
        "end": end,
        "total_return": stats.get("total_return", 0),
        "annual_return": stats.get("annual_return", 0),
        "sharpe_ratio": stats.get("sharpe_ratio", 0),
        "sortino_ratio": stats.get("sortino_ratio", 0),
        "calmar_ratio": stats.get("calmar_ratio", 0),
        "max_ddpercent": stats.get("max_ddpercent", 0),
        "win_rate": stats.get("win_rate", 0),
        "profit_factor": stats.get("profit_factor", 0),
        "total_trade_count": stats.get("total_trade_count", 0),
        "total_days": stats.get("total_days", 0),
    }
    return key_metrics


# ---------------------------------------------------------------------------
# 工具 3: 网格搜索参数
# ---------------------------------------------------------------------------


@register_tool(
    name="search_params",
    description="批量网格搜索最优参数。一次可测试多个参数组合（最多 100 组）。返回所有组合的指标排序列表。适合在知道参数范围后粗搜或精搜。注意每只测一种策略。",
    parameters={
        "strategy": {"type": "string", "description": "策略名"},
        "param_grid": {
            "type": "object",
            "description": "参数字典，值为数组。如 {'top_k': [1,3,5], 'lookback': [10,20,40]}",
        },
        "vt_symbols": {
            "type": "array",
            "items": {"type": "string"},
            "description": "股票列表，最多 20 只",
        },
        "start": {"type": "string", "description": "起始日期 YYYY-MM-DD"},
        "end": {"type": "string", "description": "结束日期 YYYY-MM-DD"},
        "capital": {"type": "integer", "description": "初始资金"},
    },
)
def tool_search_params(
    strategy: str,
    param_grid: dict[str, list],
    vt_symbols: list[str],
    start: str,
    end: str,
    capital: int = 1_000_000,
) -> dict:
    """批量网格搜索。"""
    from itertools import product

    vt_symbols = vt_symbols[:20]
    keys = list(param_grid.keys())
    values = list(param_grid.values())
    combinations = list(product(*values))

    # 限制组合数
    if len(combinations) > 100:
        return {
            "error": f"参数组合过多（{len(combinations)}），请缩减网格。最多 100 组",
            "hint": "缩小每维的取值数量",
        }

    results = []
    for combo in combinations:
        strat_params = dict(zip(keys, combo))
        try:
            r = _engine_run_backtest(
                {
                    "vt_symbols": vt_symbols,
                    "start": start,
                    "end": end,
                    "capital": capital,
                    "strategies": [strategy],
                    "strategy_params": {strategy: strat_params},
                }
            )
            stats = r["results"].get(strategy, {}).get("statistics", {})
            results.append(
                {
                    "params": strat_params,
                    "sharpe": stats.get("sharpe_ratio", 0),
                    "annual_return": stats.get("annual_return", 0),
                    "max_ddpercent": stats.get("max_ddpercent", 0),
                    "sortino": stats.get("sortino_ratio", 0),
                    "calmar": stats.get("calmar_ratio", 0),
                    "win_rate": stats.get("win_rate", 0),
                    "total_return": stats.get("total_return", 0),
                }
            )
        except Exception as e:
            logger.error(f"search_params combo failed: {strat_params}: {e}", exc_info=True)
            results.append({"params": strat_params, "error": str(e)})

    # 按 Sharpe 降序排列
    results.sort(key=lambda x: x.get("sharpe", -999), reverse=True)

    return {
        "strategy": strategy,
        "total_combinations": len(combinations),
        "top_5": results[:5],
        "bottom_5": results[-5:] if len(results) > 5 else [],
        "summary": f"共测试 {len(combinations)} 组参数。最优 Sharpe: {results[0].get('sharpe', 'N/A')}，参数: {results[0].get('params')}",
    }


# ---------------------------------------------------------------------------
# 工具 4: 获取每日序列摘要
# ---------------------------------------------------------------------------


@register_tool(
    name="get_daily_series",
    description="获取某次回测的每日收益/回撤摘要。用于分析回撤形态、波动聚集、最大回撤区间。返回压缩后的关键数据点而不是全部每天数据。",
    parameters={
        "strategy": {"type": "string", "description": "策略名"},
        "params": {"type": "object", "description": "策略参数"},
        "vt_symbols": {
            "type": "array",
            "items": {"type": "string"},
            "description": "股票列表，最多 20 只",
        },
        "start": {"type": "string", "description": "起始日期 YYYY-MM-DD"},
        "end": {"type": "string", "description": "结束日期 YYYY-MM-DD"},
    },
)
def tool_get_daily_series(
    strategy: str,
    params: dict,
    vt_symbols: list[str],
    start: str,
    end: str,
) -> dict:
    """获取压缩版每日序列。"""
    vt_symbols = vt_symbols[:20]
    try:
        result = _engine_run_backtest(
            {
                "vt_symbols": vt_symbols,
                "start": start,
                "end": end,
                "capital": 1_000_000,
                "strategies": [strategy],
                "strategy_params": {strategy: params},
            }
        )
    except Exception as e:
        logger.error(f"get_daily_series failed: {e}", exc_info=True)
        return {"error": str(e)}

    daily = result["results"].get(strategy, {}).get("daily", [])
    if not daily:
        return {"error": "无每日数据"}

    total = len(daily)
    # 压缩策略：首尾 + 每 20 个取一个 + 最大回撤日 + 最高收益日
    max_dd_day = min(daily, key=lambda d: d.get("ddpercent", 0))
    max_return_day = max(daily, key=lambda d: d.get("return", 0))
    sampled = [daily[0]]
    for i in range(1, total - 1, max(1, total // 15)):
        sampled.append(daily[i])
    sampled.append(daily[-1])

    return {
        "total_days": total,
        "start_date": str(daily[0].get("date", ""))[:10],
        "end_date": str(daily[-1].get("date", ""))[:10],
        "start_balance": daily[0].get("balance", 0),
        "end_balance": daily[-1].get("balance", 0),
        "max_dd_day": {"date": str(max_dd_day.get("date", ""))[:10], "ddpercent": max_dd_day.get("ddpercent", 0)},
        "max_return_day": {"date": str(max_return_day.get("date", ""))[:10], "return": max_return_day.get("return", 0)},
        "sampled_days": [
            {"date": str(d.get("date", ""))[:10], "balance": d.get("balance", 0), "ddpercent": d.get("ddpercent", 0)}
            for d in sampled
        ],
    }
