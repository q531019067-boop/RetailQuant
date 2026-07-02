"""
回测引擎 —— 封装 VNPY Alpha 回测流程，供 Flask API 调用。

Exposes:
    list_available_stocks()     — 扫描 data/daily/ 中的 parquet 文件
    load_benchmark(code,start,end) — 加载基准（如沪深300）的日线净值
    run_backtest(params)        — 执行回测，返回 JSON-safe 结果（含扩展指标 + 交易明细）
"""

from __future__ import annotations

import json
import math
import uuid
from datetime import datetime, date
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

from vnpy.alpha import AlphaLab, BacktestingEngine
from vnpy.trader.constant import Interval

try:
    from .strategy import all_strategies, get_strategy
except ImportError:
    from backend.strategy import all_strategies, get_strategy

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
NAME_CACHE = DATA_DIR / "stock_names.json"
RISK_FREE_RATE = 0.02  # 年化无风险利率，用于 Sharpe / Sortino 计算

# 启动时加载股票名称缓存（幂等，缺失不影响回测）
_stock_names: dict[str, str] = {}


def _load_names() -> dict[str, str]:
    """加载股票名称缓存，失败返回空 dict。"""
    global _stock_names
    if _stock_names:
        return _stock_names
    if not NAME_CACHE.exists():
        return {}
    try:
        data = json.loads(NAME_CACHE.read_text(encoding="utf-8"))
        _stock_names = data.get("names", {})
    except Exception:
        pass
    return _stock_names


def get_stock_names() -> dict[str, str]:
    """返回 {code: name} 映射，供 API 使用。"""
    return dict(_load_names())


def get_stock_name(code: str) -> str:
    """返回单只股票的中文名，无缓存则返回空字符串。"""
    return _load_names().get(code, "")


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def list_available_stocks() -> list[str]:
    """返回 data/daily/ 中所有 parquet 文件的股票代码（需以 .SSE/.SZSE 结尾）。"""
    daily_dir = DATA_DIR / "daily"
    if not daily_dir.exists():
        return []
    stocks: list[str] = []
    for f in sorted(daily_dir.glob("*.parquet")):
        symbol = f.stem
        if symbol.endswith((".SSE", ".SZSE")):
            stocks.append(symbol)
    return stocks


def load_benchmark(code: str, start: str, end: str) -> dict[str, object] | None:
    """加载基准标的的日线数据，返回日期→净值的映射。

    Returns:
        {"dates": [...], "nav": [...], "code": str} 或 None
    """
    bench_path = DATA_DIR / "daily" / f"{code}.parquet"
    if not bench_path.exists():
        return None
    try:
        df = pl.read_parquet(bench_path)
        df = df.filter(
            (pl.col("datetime") >= pl.lit(start).str.strptime(pl.Date, "%Y-%m-%d"))
            & (pl.col("datetime") <= pl.lit(end).str.strptime(pl.Date, "%Y-%m-%d"))
        ).sort("datetime")
        if df.is_empty():
            return None
        first_close = float(df["close"][0])
        if first_close <= 0:
            return None
        dates = [str(d)[:10] for d in df["datetime"].to_list()]
        nav = [float(c) / first_close for c in df["close"].to_list()]
        return {"code": code, "dates": dates, "nav": nav}
    except Exception:
        return None


# ---------------------------------------------------------------------------
# JSON 序列化
# ---------------------------------------------------------------------------


def _serialize(obj: Any) -> Any:
    """递归转换 NumPy / datetime 类型为 JSON-safe Python 类型。"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


def _empty_statistics(capital: int) -> dict:
    """无成交时的零值统计（含扩展指标）。"""
    return {
        "start_date": "",
        "end_date": "",
        "total_days": 0,
        "profit_days": 0,
        "loss_days": 0,
        "capital": capital,
        "end_balance": capital,
        "max_drawdown": 0,
        "max_ddpercent": 0,
        "max_drawdown_duration": 0,
        "total_net_pnl": 0,
        "daily_net_pnl": 0,
        "total_commission": 0,
        "daily_commission": 0,
        "total_turnover": 0,
        "daily_turnover": 0,
        "total_trade_count": 0,
        "daily_trade_count": 0,
        "total_return": 0,
        "annual_return": 0,
        "daily_return": 0,
        "return_std": 0,
        "sharpe_ratio": 0,
        "return_drawdown_ratio": 0,
        # ---- 扩展指标 ----
        "sortino_ratio": 0,
        "calmar_ratio": 0,
        "win_rate": 0,
        "profit_factor": 0,
        "avg_win": 0,
        "avg_loss": 0,
        "max_consecutive_wins": 0,
        "max_consecutive_losses": 0,
    }


def _empty_daily(dates: list[str | object], capital: int) -> list[dict[str, object]]:
    """无成交时的每日零值记录。"""
    return [
        {
            "date": d.isoformat() if hasattr(d, "isoformat") else str(d),
            "trade_count": 0,
            "turnover": 0,
            "commission": 0,
            "trading_pnl": 0,
            "holding_pnl": 0,
            "total_pnl": 0,
            "net_pnl": 0,
            "balance": capital,
            "return": 0,
            "highlevel": capital,
            "drawdown": 0,
            "ddpercent": 0,
        }
        for d in dates
    ]


# ---------------------------------------------------------------------------
# 扩展指标计算 —— 基于 VNPY 输出的 daily_df / result_df 做二次计算
# ---------------------------------------------------------------------------


def _calc_extended_metrics(daily_records: list[dict]) -> dict:
    """基于日频数据计算 VNPY 未提供的业界标准指标。

    所有计算仅依赖 daily_records（逐日权益），不依赖交易明细。
    Returns 增加的字段（会被合并到 statistics 中）。
    """
    if not daily_records:
        return {}

    # 从每日记录提取收益率序列（VNPY 的 daily.return 是百分比）
    returns = [d.get("return", 0) for d in daily_records]
    returns_series = np.array([r for r in returns if r is not None], dtype=np.float64)

    # ---- Sortino ratio（只对下行波动率做惩罚） ----
    downside_returns = returns_series[returns_series < 0]
    if len(downside_returns) > 1 and float(downside_returns.std()) > 0:
        downside_std = float(downside_returns.std())
        daily_rf = RISK_FREE_RATE / 250
        excess_daily = float(returns_series.mean()) - daily_rf
        sortino = float(excess_daily / downside_std * math.sqrt(250))
    else:
        sortino = 0.0

    # ---- Calmar ratio（年化收益 / 最大回撤绝对值） ----
    max_dd = min(d.get("ddpercent", 0) for d in daily_records) if daily_records else 0
    annual_ret = 0.0
    if len(daily_records) >= 2:
        first_bal = daily_records[0].get("balance", 1)
        last_bal = daily_records[-1].get("balance", 1)
        if first_bal > 0:
            annual_ret = (last_bal / first_bal) ** (250 / len(daily_records)) - 1
    calmar = float(annual_ret / abs(max_dd / 100)) if max_dd != 0 else 0.0

    # ---- Win rate / Profit factor / Avg win-loss（基于交易日） ----
    win_days = sum(1 for r in returns_series if r > 0)
    loss_days = sum(1 for r in returns_series if r < 0)
    total_days = len(returns_series)
    win_rate = round(win_days / total_days * 100, 2) if total_days > 0 else 0.0

    gross_profit = float(returns_series[returns_series > 0].sum()) if win_days > 0 else 0.0
    gross_loss = abs(float(returns_series[returns_series < 0].sum())) if loss_days > 0 else 0.0
    # 无亏损日时 profit_factor 无意义，置 0；无盈利日同理
    if gross_loss > 0 and gross_profit > 0:
        profit_factor = round(gross_profit / gross_loss, 2)
    else:
        profit_factor = 0.0

    avg_win = round(float(returns_series[returns_series > 0].mean()) * 100, 4) if win_days > 0 else 0.0
    avg_loss = round(float(returns_series[returns_series < 0].mean()) * 100, 4) if loss_days > 0 else 0.0

    # ---- Max consecutive wins / losses ----
    max_con_wins = 0
    max_con_losses = 0
    cur_wins = 0
    cur_losses = 0
    for r in returns_series:
        if r > 0:
            cur_wins += 1
            cur_losses = 0
            max_con_wins = max(max_con_wins, cur_wins)
        elif r < 0:
            cur_losses += 1
            cur_wins = 0
            max_con_losses = max(max_con_losses, cur_losses)

    return {
        "sortino_ratio": round(sortino, 2),
        "calmar_ratio": round(calmar, 2),
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "max_consecutive_wins": max_con_wins,
        "max_consecutive_losses": max_con_losses,
    }


def _extract_trades(engine: BacktestingEngine) -> list[dict]:
    """从 VNPY 引擎提取逐笔成交明细，含 FIFO 匹配的盈亏。

    VNPY 的 TradeData 不含 PnL 字段（盈亏在组合层面计算），
    这里通过 FIFO 队列重建每笔卖出的成本基础：
      - 买入时：记录 (symbol, shares, price) 到队列
      - 卖出时：从该 symbol 最早的买入批次扣减，计算 PnL
    """
    try:
        raw_trades = engine.get_all_trades()
    except Exception:
        return []
    if not raw_trades:
        return []

    # FIFO 持仓队列：{symbol: [(shares, price), ...]}
    positions: dict[str, list[tuple[float, float]]] = {}
    trades: list[dict] = []

    for t in raw_trades:
        try:
            sym = str(getattr(t, "vt_symbol", ""))
            price = float(getattr(t, "price", 0))
            shares = float(getattr(t, "volume", 0))
            side_raw = str(getattr(t, "direction", ""))
            offset_raw = str(getattr(t, "offset", ""))

            is_buy = "LONG" in side_raw or "Long" in side_raw or "多" in side_raw
            is_open = "OPEN" in offset_raw or "开" in offset_raw
            is_close = "CLOSE" in offset_raw or "平" in offset_raw

            entry_price = None
            trade_pnl = None
            trade_pnl_pct = None

            if is_buy:
                side = "买入开仓" if is_open else "买入"
                # 记录到 FIFO 队列
                if sym not in positions:
                    positions[sym] = []
                positions[sym].append((shares, price))
            else:
                side = "卖出平仓" if is_close else "卖出"
                # FIFO 匹配：从最早的买入批次中扣减
                if sym in positions and positions[sym]:
                    remaining = shares
                    total_cost = 0.0
                    matched_shares = 0.0
                    new_queue: list[tuple[float, float]] = []
                    for lot_shares, lot_price in positions[sym]:
                        if remaining <= 0:
                            new_queue.append((lot_shares, lot_price))
                            continue
                        take = min(lot_shares, remaining)
                        total_cost += take * lot_price
                        matched_shares += take
                        remaining -= take
                        if lot_shares > take:
                            new_queue.append((lot_shares - take, lot_price))
                    positions[sym] = new_queue
                    if matched_shares > 0:
                        entry_price = round(total_cost / matched_shares, 4)
                        proceeds = matched_shares * price
                        trade_pnl = round(proceeds - total_cost, 2)
                        trade_pnl_pct = round((price / (total_cost / matched_shares) - 1) * 100, 2)

            trades.append(
                {
                    "date": _serialize(getattr(t, "datetime", None)),
                    "symbol": sym,
                    "side": side,
                    "price": _serialize(price),
                    "shares": _serialize(shares),
                    "entry_price": entry_price,
                    "pnl": trade_pnl,
                    "pnl_pct": trade_pnl_pct,
                }
            )
        except Exception:
            continue
    return trades


# ---------------------------------------------------------------------------
# 回测入口
# ---------------------------------------------------------------------------


def run_backtest(params: dict) -> dict:
    """执行一个或多个策略的回测。

    Returns:
        {"task_id": str,
         "results": {strategy_name: {
             "statistics": {...},    # VNPY 原生 + 扩展指标
             "daily": [...],         # 逐日权益
             "trades": [...],        # 逐笔交易明细（新增）
         }}}
    """
    vt_symbols: list[str] = params["vt_symbols"]
    start = datetime.strptime(params["start"], "%Y-%m-%d")
    end = datetime.strptime(params["end"], "%Y-%m-%d")
    capital = int(params.get("capital", 1_000_000))
    strategy_names: list[str] = params.get("strategies", ["equal_weight"])

    all_results: dict[str, dict] = {}

    for strategy_name in strategy_names:
        strategy_cls = get_strategy(strategy_name)
        if strategy_cls is None:
            raise ValueError(f"未知策略: {strategy_name!r}，可用: {[s.name for s in all_strategies()]}")

        flat_params = {k: v for k, v in params.items() if k in strategy_cls.param_schema()}
        per_strat = params.get("strategy_params", {}).get(strategy_name, {})
        strategy_params = {**flat_params, **per_strat}

        lab = AlphaLab(str(DATA_DIR))
        engine = BacktestingEngine(lab)
        engine.set_parameters(
            vt_symbols=vt_symbols,
            interval=Interval.DAILY,
            start=start,
            end=end,
            capital=capital,
        )
        engine.add_strategy(
            strategy_cls,
            strategy_params,
            signal_df=pl.DataFrame({"datetime": [], "vt_symbol": [], "signal": []}),
        )
        engine.load_data()
        engine.run_backtesting()
        result_df = engine.calculate_result()

        if result_df is not None and not result_df.is_empty():
            stats_raw = engine.calculate_statistics()
            daily_df = engine.daily_df
            daily_records = (
                [{k: _serialize(v) for k, v in row.items()} for row in daily_df.iter_rows(named=True)]
                if daily_df is not None
                else []
            )
            stats = {k: _serialize(v) for k, v in stats_raw.items()}
            trades = _extract_trades(engine)
        else:
            all_dates = sorted(engine.daily_results.keys())
            daily_records = _empty_daily(all_dates, capital)
            stats = _empty_statistics(capital)
            trades = []
            if all_dates:
                stats["start_date"] = str(all_dates[0])
                stats["end_date"] = str(all_dates[-1])
                stats["total_days"] = len(all_dates)

        # 合并扩展指标（仅依赖 daily_records，不依赖 trades）
        extended = _calc_extended_metrics(daily_records)
        stats.update(extended)

        all_results[strategy_name] = {
            "statistics": stats,
            "daily": daily_records,
            "trades": trades,
        }

    return {"task_id": str(uuid.uuid4()), "results": all_results}
