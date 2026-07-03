"""
Agent 工具注册与执行。

设计：
    - 装饰器 @register_tool 自动注册，新增工具只需一个函数 + 装饰器
    - 工具函数接收基本类型参数（str/int/float/list），不暴露内部对象
    - 返回纯 dict（JSON-safe），便于 LLM 消费
    - get_tool_definitions() 自动生成 OpenAI function calling 格式
"""

from __future__ import annotations

import uuid
from typing import Any

from backend.backtest_engine import run_backtest as _engine_run_backtest, list_available_stocks
from backend.strategy import list_strategies_metadata
from backend.log import logger

# ---------------------------------------------------------------------------
# 回测结果缓存（供前端「查看图表」直接取，避免重复跑回测）
# ---------------------------------------------------------------------------

_result_cache: dict[str, dict] = {}  # cache_id → {results, daily, trades}
_backtest_call_count: int = 0
_MAX_BACKTEST_CALLS = 30  # 每 session 最多跑 30 次回测，防止 LLM 死循环


def _reset_backtest_counter() -> None:
    """每个新 session 重置回测计数。"""
    global _backtest_call_count
    _backtest_call_count = 0


def _check_backtest_limit() -> dict | None:
    """检查回测次数上限，超限返回 error。"""
    global _backtest_call_count
    _backtest_call_count += 1
    if _backtest_call_count > _MAX_BACKTEST_CALLS:
        return {"error": f"回测次数已达上限（{_MAX_BACKTEST_CALLS}），请基于已有数据给出分析", "hint": "不要重复跑回测"}
    return None


def _cache_backtest_result(cache_id: str, result: dict) -> None:
    """缓存一次完整回测结果。"""
    _result_cache[cache_id] = result
    # 最多保留 50 条
    if len(_result_cache) > 50:
        oldest = next(iter(_result_cache))
        del _result_cache[oldest]


def get_cached_result(cache_id: str) -> dict | None:
    """获取缓存回测结果，取后即删（一次性使用）。"""
    return _result_cache.pop(cache_id, None)


# ---------------------------------------------------------------------------
# 注册器
# ---------------------------------------------------------------------------

_registry: dict[str, dict] = {}


def register_tool(name: str, description: str, parameters: dict, optional: list[str] | None = None):
    """装饰器：将函数注册为 Agent 可用工具。

    用法:
        @register_tool("run_backtest", "运行回测", {...}, optional=["capital"])
        def run_backtest(strategy: str, capital: int = 1_000_000): ...
    """
    _optional: list[str] = optional or []

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
                        "required": [k for k in parameters if k not in _optional],
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
# 股票代码校验（防止 LLM 幻想不存在的代码）
# ---------------------------------------------------------------------------


def _validate_vt_symbols(requested: list[str]) -> dict | None:
    """校验股票代码是否存在于数据目录中。

    返回 None 表示全部合法；否则返回 error dict，包含：
      - invalid: 无效代码列表
      - suggestions: 每个无效代码的修复建议（如 .SH → .SSE）
    """
    available = set(list_available_stocks())
    if not available:
        return None  # 无数据时放过，让引擎报错

    invalid: list[str] = []
    suggestions: dict[str, str] = {}

    for sym in requested:
        if sym in available:
            continue
        invalid.append(sym)
        # 尝试修复：取代码前缀（去掉 .后缀），在可用池里找匹配
        for suffix in (".SSE", ".SZSE"):
            # 把用户的后缀替换为目标后缀
            base = sym.rsplit(".", 1)[0] if "." in sym else sym
            candidate = f"{base}{suffix}"
            if candidate in available:
                suggestions[sym] = candidate
                break

    if not invalid:
        return None

    msg = f"以下 {len(invalid)} 个股票代码不存在：{', '.join(invalid)}。"
    if suggestions:
        msg += " 建议修正：" + "；".join(f"{k} → {v}" for k, v in suggestions.items()) + "。"
    msg += " 代码格式必须为 XXXXXX.SSE（沪市）或 XXXXXX.SZSE（深市）。"
    return {"error": msg, "invalid": invalid, "suggestions": suggestions}


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
    description="运行回测，strategies 可传一个或多个策略名（如 ['equal_weight'] 或 ['equal_weight', 'ma_cross']）。一次测多个比逐个调用更高效。",
    optional=["capital", "strategy_params"],
    parameters={
        "strategies": {
            "type": "array",
            "items": {"type": "string"},
            "description": "策略名列表，如 ['equal_weight'] 或 ['equal_weight', 'ma_cross']",
        },
        "strategy_params": {
            "type": "object",
            "description": "可选，各策略的参数，如 {'equal_weight': {'top_k': 5}, 'ma_cross': {'fast': 5}}。省略则用默认参数",
        },
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
    strategies: list[str],
    vt_symbols: list[str],
    start: str,
    end: str,
    strategy_params: dict | None = None,
    capital: int = 1_000_000,
) -> dict:
    """执行回测并返回所有策略的关键指标。"""
    # 硬性上限保护
    limit_hit = _check_backtest_limit()
    if limit_hit:
        return limit_hit

    # 股票代码校验
    vt_symbols = vt_symbols[:20]
    validation = _validate_vt_symbols(vt_symbols)
    if validation:
        return validation

    if not strategies:
        return {"error": "请至少指定一个策略"}
    if len(strategies) > 10:
        strategies = strategies[:10]
    strategy_params = strategy_params or {}

    try:
        result = _engine_run_backtest(
            {
                "vt_symbols": vt_symbols,
                "start": start,
                "end": end,
                "capital": capital,
                "strategies": strategies,
                "strategy_params": strategy_params,
            }
        )
    except Exception as e:
        logger.error(f"run_backtest tool failed: {e}", exc_info=True)
        return {"error": str(e)}

    # 缓存完整结果供前端「查看图表」
    cache_id = str(uuid.uuid4())[:12]
    _cache_backtest_result(
        cache_id,
        {
            "vt_symbols": vt_symbols,
            "start": start,
            "end": end,
            "capital": capital,
            "strategies": strategies,
            "strategy_params": strategy_params,
            "results": result["results"],
        },
    )

    # 返回每个策略的关键指标
    all_metrics: list[dict] = []
    for sn in strategies:
        strat_result = result["results"].get(sn, {})
        stats = strat_result.get("statistics", {})
        all_metrics.append(
            {
                "strategy": sn,
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
        )

    return {
        "strategies": strategies,
        "strategy_params": strategy_params,
        "vt_symbols": vt_symbols,
        "start": start,
        "end": end,
        "capital": capital,
        "_cache_id": cache_id,
        "metrics": all_metrics,
    }


# ---------------------------------------------------------------------------
# 工具 3: 网格搜索参数
# ---------------------------------------------------------------------------


@register_tool(
    name="search_params",
    description="批量网格搜索最优参数。一次可测试多个参数组合（最多 100 组）。返回所有组合的指标排序列表。适合在知道参数范围后粗搜或精搜。注意每只测一种策略。",
    optional=["capital"],
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
    validation = _validate_vt_symbols(vt_symbols)
    if validation:
        return validation
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
    validation = _validate_vt_symbols(vt_symbols)
    if validation:
        return validation
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


# ---------------------------------------------------------------------------
# 工具 5: 数据概览
# ---------------------------------------------------------------------------


@register_tool(
    name="get_data_info",
    description="获取数据概览：总共有多少只股票、数据覆盖的日期范围、示例股票代码。用于了解数据情况，跑回测前先调用。",
    parameters={},
)
def tool_get_data_info() -> dict:
    """返回数据集的基本信息。"""
    stocks = list_available_stocks()
    if not stocks:
        return {"error": "未找到数据文件"}

    # 抽样几只股票来确定日期范围
    import polars as pl
    from pathlib import Path

    DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "daily"
    min_date = None
    max_date = None
    for sym in stocks[:5]:
        try:
            df = pl.read_parquet(DATA_DIR / f"{sym}.parquet")
            dmin = str(df["datetime"].min())[:10]
            dmax = str(df["datetime"].max())[:10]
            if min_date is None or dmin < min_date:
                min_date = dmin
            if max_date is None or dmax > max_date:
                max_date = dmax
        except Exception:
            continue

    return {
        "total_stocks": len(stocks),
        "date_range": f"{min_date} ~ {max_date}" if min_date else "未知",
        "sample_codes": stocks[:10],
        "code_format": "XXXXXX.SSE (沪市) 或 XXXXXX.SZSE (深市)",
    }


# ---------------------------------------------------------------------------
# 工具 6: 搜索股票
# ---------------------------------------------------------------------------


@register_tool(
    name="search_stocks",
    description="按代码或名称搜索股票。keyword 支持代码片段（如 '600519'）或名称关键词。返回匹配的股票代码列表，最多 20 条。",
    parameters={
        "keyword": {"type": "string", "description": "搜索关键词，如 '600519'、'茅台'、'银行'"},
    },
)
def tool_search_stocks(keyword: str) -> dict:
    """搜索股票代码。"""
    stocks = list_available_stocks()
    if not keyword:
        return {"error": "请提供搜索关键词"}

    # 加载股票名称映射
    try:
        from backend.backtest_engine import get_stock_names

        name_map = get_stock_names()
    except Exception:
        name_map = {}

    kw = keyword.lower().strip()
    matches = []
    for sym in stocks:
        name = name_map.get(sym, "")
        if kw in sym.lower() or kw in name.lower():
            matches.append({"code": sym, "name": name})
        if len(matches) >= 20:
            break

    if not matches:
        return {
            "found": 0,
            "results": [],
            "hint": f"未找到匹配 '{keyword}' 的股票。试试代码片段如 '600' 或名称关键词。",
        }

    return {"found": len(matches), "results": matches}


# ---------------------------------------------------------------------------
# 工具 7: 股票基本信息
# ---------------------------------------------------------------------------


@register_tool(
    name="get_stock_brief",
    description="获取股票的基本面数据：日期范围、价格区间（最高/最低/最新收盘价）、成交量统计、交易日数。可一次查询多只股票（最多 10 只）。用于在跑回测前了解股票基本情况。",
    parameters={
        "symbols": {
            "type": "array",
            "items": {"type": "string"},
            "description": "股票代码列表，如 ['600519.SSE', '000858.SZSE']，最多 10 只",
        },
    },
)
def tool_get_stock_brief(symbols: list[str]) -> dict:
    """返回股票的 OHLCV 统计摘要。"""
    import polars as pl
    from pathlib import Path

    DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "daily"
    symbols = symbols[:10]
    validation = _validate_vt_symbols(symbols)
    if validation:
        return validation

    results = []
    for sym in symbols:
        try:
            df = pl.read_parquet(DATA_DIR / f"{sym}.parquet")
            close_series = df["close"]
            vol_series = df["volume"]
            results.append(
                {
                    "code": sym,
                    "trading_days": len(df),
                    "date_range": f"{str(df['datetime'].min())[:10]} ~ {str(df['datetime'].max())[:10]}",
                    "latest_close": round(float(close_series[-1]), 2),
                    "max_close": round(float(close_series.max()), 2),
                    "min_close": round(float(close_series.min()), 2),
                    "avg_daily_volume": int(vol_series.mean()),
                }
            )
        except Exception as e:
            results.append({"code": sym, "error": str(e)})

    return {"stocks": results}
