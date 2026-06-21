"""
rquant.research.workflow — 板块选池、多策略评分和组合模拟。

所有决策均使用 as-of 切片：策略只接收 `date <= decision_date` 的 K 线，
不使用当前 K 线之后的任何价格或成交量。
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from rquant.backtest import BrokerConfig
from rquant.business import data as business_data
from rquant.data_source import parquet_store
from rquant.strategy import get
from rquant.strategy.factor.multi_factor import MultiFactor

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BOARDS_DIR = PROJECT_ROOT / "data" / "boards"
DEFAULT_STRATEGIES = ("MovingAverageCross", "RsiMeanReversion", "GridMartingale", "MultiFactor")


@dataclass
class StockMetric:
    code: str
    name: str
    market: str
    board_code: str
    board_name: str
    board_type: str
    avg_amount_20d: float
    volatility_20d: float
    momentum_20d: float
    volume_ratio_5d: float
    hot_score: float
    score: float
    data_rows: int


@dataclass
class BoardMetric:
    board_code: str
    board_name: str
    board_type: str
    stock_count: int
    covered_stocks: int
    avg_amount_20d: float
    volatility_20d: float
    hot_score: float
    score: float


@dataclass
class PoolSelection:
    as_of: str
    board_limit: int
    stocks_per_board: int
    boards: list[dict[str, Any]]
    stocks: list[dict[str, Any]]
    skipped: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class StrategyScore:
    code: str
    name: str
    as_of: str
    strategy: str
    category: str
    score: float
    action: str
    confidence: float
    reason: str
    buy_signal: dict[str, Any] | None = None
    sell_signal: dict[str, Any] | None = None
    detail: dict[str, Any] = field(default_factory=dict)


def read_tab(path: Path) -> list[dict[str, str]]:
    """安全读取 tab 文件，按 UTF-8/GBK 顺序尝试。"""
    raw = path.read_bytes()
    text = None
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        text = raw.decode("utf-8", errors="replace")
    return list(csv.DictReader(text.splitlines(), delimiter="\t"))


def load_boards(
    boards_dir: Path = BOARDS_DIR,
) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, dict[str, str]]]:
    boards = read_tab(boards_dir / "Boards.tab")
    rels = read_tab(boards_dir / "StockBoardRel.tab")
    stocks = {row["code"]: row for row in read_tab(boards_dir / "Stocks.tab")}
    return boards, rels, stocks


def load_kline(code: str, days: int = 5000, allow_fetch: bool = True) -> pd.DataFrame:
    df = parquet_store.read(code)
    if df is not None and not df.empty:
        return _normalize_kline(df)
    if not allow_fetch:
        return pd.DataFrame()
    return _normalize_kline(business_data.fetch_kline(code, days))


def asof_kline(
    code: str,
    as_of: str,
    lookback_days: int = 365,
    days: int = 5000,
    allow_fetch: bool = True,
) -> pd.DataFrame:
    df = load_kline(code, days, allow_fetch=allow_fetch)
    if df.empty:
        return df
    asof_ts = pd.Timestamp(as_of)
    start_ts = asof_ts - pd.Timedelta(days=lookback_days)
    sliced = df[(df["date"] >= start_ts) & (df["date"] <= asof_ts)].copy()
    if not sliced.empty and sliced["date"].max() > asof_ts:
        raise RuntimeError(f"{code} as-of 切片包含未来数据")
    return sliced.reset_index(drop=True)


def select_liquid_board_pool(
    as_of: str,
    board_limit: int = 20,
    stocks_per_board: int = 6,
    board_type: str = "sector",
    board_keywords: Iterable[str] | None = None,
    board_codes: Iterable[str] | None = None,
    min_history: int = 60,
    metric_window: int = 20,
    boards_dir: Path = BOARDS_DIR,
) -> PoolSelection:
    boards, rels, stock_map = load_boards(boards_dir)
    keyword_list = [x for x in (board_keywords or []) if x]
    code_set = {x.upper() for x in (board_codes or []) if x}

    board_meta = {
        row["board_code"]: row
        for row in boards
        if row.get("board_type") == board_type
        and (not code_set or row.get("board_code", "").upper() in code_set)
        and (not keyword_list or any(k in row.get("board_name", "") for k in keyword_list))
    }
    members: dict[str, list[dict[str, str]]] = {code: [] for code in board_meta}
    for rel in rels:
        bcode = rel.get("board_code", "")
        if bcode in members:
            members[bcode].append(rel)

    skipped: list[dict[str, Any]] = []
    stock_metrics_by_board: dict[str, list[StockMetric]] = {}
    board_metrics: list[BoardMetric] = []
    for bcode, rows in members.items():
        stock_metrics: list[StockMetric] = []
        for rel in rows:
            code = rel.get("stock_code", "")
            stock_row = stock_map.get(code, {})
            name = rel.get("stock_name") or stock_row.get("name", code)
            market = rel.get("market") or stock_row.get("market", "")
            if _is_untradable_name(name) or market in {"bj", "other"}:
                continue
            df = asof_kline(code, as_of, lookback_days=420, allow_fetch=False)
            metric = _calc_stock_metric(rel, df, min_history=min_history, metric_window=metric_window)
            if metric is None:
                skipped.append({"code": code, "name": name, "board_code": bcode, "reason": "历史数据不足或无缓存"})
                continue
            stock_metrics.append(metric)
        if not stock_metrics:
            continue
        stock_metrics.sort(key=lambda x: x.score, reverse=True)
        stock_metrics_by_board[bcode] = stock_metrics
        meta = board_meta[bcode]
        board_metrics.append(
            BoardMetric(
                board_code=bcode,
                board_name=meta.get("board_name", bcode),
                board_type=meta.get("board_type", board_type),
                stock_count=int(meta.get("stock_count") or len(rows)),
                covered_stocks=len(stock_metrics),
                avg_amount_20d=float(pd.Series([m.avg_amount_20d for m in stock_metrics]).mean()),
                volatility_20d=float(pd.Series([m.volatility_20d for m in stock_metrics]).mean()),
                hot_score=float(pd.Series([m.hot_score for m in stock_metrics]).mean()),
                score=0.0,
            )
        )

    board_metrics = _rank_boards(board_metrics)
    selected_boards = board_metrics[:board_limit]
    selected_stocks: list[StockMetric] = []
    seen: set[str] = set()
    for board in selected_boards:
        for metric in stock_metrics_by_board.get(board.board_code, [])[: stocks_per_board * 2]:
            if metric.code in seen:
                continue
            selected_stocks.append(metric)
            seen.add(metric.code)
            if sum(1 for m in selected_stocks if m.board_code == board.board_code) >= stocks_per_board:
                break

    return PoolSelection(
        as_of=as_of,
        board_limit=board_limit,
        stocks_per_board=stocks_per_board,
        boards=[asdict(x) for x in selected_boards],
        stocks=[asdict(x) for x in selected_stocks],
        skipped=skipped,
    )


def score_stock_strategies(
    code: str,
    as_of: str,
    lookback_days: int = 365,
    strategies: Iterable[str] = DEFAULT_STRATEGIES,
    name: str | None = None,
    sector: str = "",
    position: dict[str, Any] | None = None,
    allow_fetch: bool = False,
) -> list[StrategyScore]:
    df = asof_kline(code, as_of, lookback_days=lookback_days, allow_fetch=allow_fetch)
    if df.empty:
        raise RuntimeError(f"{code} 在 {as_of} 前无可用 K 线")
    if df["date"].max() > pd.Timestamp(as_of):
        raise RuntimeError("策略评分输入包含未来数据")

    stock_name = name or code
    results: list[StrategyScore] = []
    for strategy_name in strategies:
        strategy = get(strategy_name)
        if strategy is None:
            raise RuntimeError(f"策略未注册: {strategy_name}")

        if strategy_name == "MultiFactor" and isinstance(strategy, MultiFactor):
            score, detail = strategy.score(df, name=stock_name, code=code)
            filtered = detail.get("filtered", False)
            action = "HOLD"
            if score != float("-inf") and score >= strategy.SCORE_BUY:
                action = "BUY"
            results.append(
                StrategyScore(
                    code=code,
                    name=stock_name,
                    as_of=as_of,
                    strategy=strategy.name,
                    category=strategy.category,
                    score=0.0 if score == float("-inf") else round(float(score), 4),
                    action="FILTERED" if filtered else action,
                    confidence=0.0 if filtered else round(max(0.0, min(100.0, 50 + float(score) * 50)), 2),
                    reason="; ".join(detail.get("reasons", [])) if filtered else "MultiFactor score",
                    detail=detail,
                )
            )
            continue

        buy_signal = strategy.signal_buy(code, stock_name, sector, df)
        sell_signal = strategy.signal_sell(position or {}, df)
        action = "HOLD"
        score = 0.0
        confidence = 0.0
        reason = "无信号"
        if sell_signal is not None:
            action = "SELL"
            score = -1.0 if sell_signal.get("urgency") == "urgent" else -0.6
            confidence = 80.0 if sell_signal.get("urgency") == "urgent" else 65.0
            reason = str(sell_signal.get("reason", "策略卖出"))
        elif buy_signal is not None:
            action = "BUY"
            confidence = float(buy_signal.confidence)
            score = round(confidence / 100, 4)
            reason = buy_signal.reason

        results.append(
            StrategyScore(
                code=code,
                name=stock_name,
                as_of=as_of,
                strategy=strategy.name,
                category=strategy.category,
                score=score,
                action=action,
                confidence=confidence,
                reason=reason,
                buy_signal=asdict(buy_signal) if buy_signal is not None else None,
                sell_signal=sell_signal,
            )
        )
    return results


def simulate_strategy_pool(
    pool: list[dict[str, Any]],
    start: str,
    end: str,
    strategy_name: str,
    capital: float = 100_000.0,
    lookback_days: int = 365,
    max_positions: int = 5,
    broker: BrokerConfig | None = None,
) -> dict[str, Any]:
    broker = broker or BrokerConfig()
    strategy = get(strategy_name)
    if strategy is None:
        raise RuntimeError(f"策略未注册: {strategy_name}")

    kline_map = {row["code"]: load_kline(row["code"], allow_fetch=False) for row in pool}
    kline_map = {code: df for code, df in kline_map.items() if df is not None and not df.empty}
    if not kline_map:
        raise RuntimeError("候选池没有可用 K 线")

    dates = sorted(
        {
            str(d.date())
            for df in kline_map.values()
            for d in pd.to_datetime(df["date"])
            if pd.Timestamp(start) <= d <= pd.Timestamp(end)
        }
    )
    if len(dates) < 2:
        raise RuntimeError("交易窗口内可用交易日不足 2 天")

    names = {row["code"]: row.get("name", row["code"]) for row in pool}
    sectors = {row["code"]: row.get("board_name") or row.get("sector", "") for row in pool}
    cash = capital
    positions: dict[str, dict[str, Any]] = {}
    pending: list[dict[str, Any]] = []
    trades: list[dict[str, Any]] = []
    equity_curve: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for i, dt in enumerate(dates):
        # 执行上一个决策日排队到今天开盘的订单。
        today_orders = [x for x in pending if x["trade_date"] == dt]
        pending = [x for x in pending if x["trade_date"] != dt]
        for order in today_orders:
            cash, trade, skip = _execute_pool_order(order, cash, positions, kline_map, broker)
            if trade:
                trades.append(trade)
            if skip:
                skipped.append(skip)

        close_prices = {code: _price_on(df, dt, "close") for code, df in kline_map.items()}
        position_value = sum(pos["shares"] * close_prices.get(code, 0.0) for code, pos in positions.items())
        equity_curve.append(
            {
                "date": dt,
                "equity": round(cash + position_value, 2),
                "cash": round(cash, 2),
                "position_value": round(position_value, 2),
                "positions": len(positions),
            }
        )

        if i >= len(dates) - 1:
            continue
        next_dt = dates[i + 1]

        # 卖出优先。
        for code, pos in list(positions.items()):
            df_until = _decision_df(kline_map[code], dt, lookback_days)
            if df_until.empty:
                continue
            sell_signal = strategy.signal_sell(_position_for_strategy(pos, dt), df_until)
            if sell_signal is not None:
                pending.append(
                    {
                        "side": "SELL",
                        "code": code,
                        "name": names.get(code, code),
                        "trade_date": next_dt,
                        "reason": sell_signal.get("reason", "策略卖出"),
                        "sell_all": sell_signal.get("sell_all", True),
                    }
                )

        # 横截面买入候选：同一策略对所有未持仓股票打分，按信心/score 排序。
        if len(positions) >= max_positions:
            continue
        buy_candidates: list[dict[str, Any]] = []
        for code in kline_map:
            if code in positions:
                continue
            df_until = _decision_df(kline_map[code], dt, lookback_days)
            if df_until.empty:
                continue
            if df_until["date"].max() > pd.Timestamp(dt):
                raise RuntimeError(f"{strategy_name} 在 {dt} 看到了未来数据")
            score = _score_one_for_sim(strategy, code, names.get(code, code), sectors.get(code, ""), df_until)
            if score and score["action"] == "BUY":
                buy_candidates.append(score)
        buy_candidates.sort(key=lambda x: x["score"], reverse=True)
        slots = max_positions - len(positions)
        for cand in buy_candidates[:slots]:
            pending.append(
                {
                    "side": "BUY",
                    "code": cand["code"],
                    "name": cand["name"],
                    "trade_date": next_dt,
                    "reason": cand["reason"],
                    "score": cand["score"],
                    "cash_pct": min(0.95 / max_positions, cand.get("cash_pct", 0.95 / max_positions)),
                }
            )

    # 末日强平。
    last_dt = dates[-1]
    for code in list(positions):
        cash, trade, skip = _execute_pool_order(
            {
                "side": "SELL",
                "code": code,
                "name": names.get(code, code),
                "trade_date": last_dt,
                "reason": "回测结束强平",
            },
            cash,
            positions,
            kline_map,
            broker,
            force=True,
        )
        if trade:
            trades.append(trade)
        if skip:
            skipped.append(skip)
    if equity_curve:
        equity_curve[-1]["cash"] = round(cash, 2)
        equity_curve[-1]["position_value"] = 0.0
        equity_curve[-1]["equity"] = round(cash, 2)
        equity_curve[-1]["positions"] = 0

    metrics = _portfolio_metrics(equity_curve, trades, capital, broker.risk_free_rate)
    return {
        "strategy": strategy_name,
        "start_date": dates[0],
        "end_date": dates[-1],
        "initial_capital": capital,
        **metrics,
        "trades": trades,
        "equity_curve": equity_curve,
        "skipped": skipped,
    }


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _normalize_kline(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    data = df.copy()
    data["date"] = pd.to_datetime(data["date"])
    for col in ("open", "high", "low", "close", "volume"):
        if col not in data.columns:
            return pd.DataFrame()
        data[col] = pd.to_numeric(data[col], errors="coerce")
    return data.dropna(subset=["date", "open", "high", "low", "close"]).sort_values("date").reset_index(drop=True)


def _is_untradable_name(name: str) -> bool:
    upper = (name or "").upper()
    return "ST" in upper or "退" in (name or "")


def _calc_stock_metric(
    rel: dict[str, str],
    df: pd.DataFrame,
    min_history: int,
    metric_window: int,
) -> StockMetric | None:
    if df is None or len(df) < max(min_history, metric_window + 1):
        return None
    tail = df.tail(metric_window + 1)
    amount = tail["close"] * tail["volume"]
    ret = tail["close"].pct_change().dropna()
    if ret.empty:
        return None
    avg_amount = float(amount.tail(metric_window).mean())
    volatility = float(ret.tail(metric_window).std() * math.sqrt(250))
    momentum = float(tail["close"].iloc[-1] / tail["close"].iloc[-(metric_window + 1)] - 1)
    avg_vol = float(tail["volume"].iloc[-6:-1].mean()) if len(tail) >= 6 else 0.0
    volume_ratio = float(tail["volume"].iloc[-1] / avg_vol) if avg_vol > 0 else 1.0
    hot_score = abs(momentum) * 0.4 + volatility * 0.4 + max(0.0, volume_ratio - 1.0) * 0.2
    score = math.log1p(max(0.0, avg_amount)) * 0.55 + volatility * 10 * 0.25 + hot_score * 10 * 0.20
    return StockMetric(
        code=rel.get("stock_code", ""),
        name=rel.get("stock_name", ""),
        market=rel.get("market", ""),
        board_code=rel.get("board_code", ""),
        board_name=rel.get("board_name", ""),
        board_type=rel.get("board_type", ""),
        avg_amount_20d=round(avg_amount, 2),
        volatility_20d=round(volatility, 4),
        momentum_20d=round(momentum, 4),
        volume_ratio_5d=round(volume_ratio, 4),
        hot_score=round(hot_score, 4),
        score=round(score, 4),
        data_rows=len(df),
    )


def _rank_boards(boards: list[BoardMetric]) -> list[BoardMetric]:
    if not boards:
        return boards
    amount = pd.Series([b.avg_amount_20d for b in boards])
    vol = pd.Series([b.volatility_20d for b in boards])
    hot = pd.Series([b.hot_score for b in boards])
    coverage = pd.Series([b.covered_stocks for b in boards])
    for i, board in enumerate(boards):
        board.score = round(
            _pct_rank(amount, i) * 0.45
            + _pct_rank(vol, i) * 0.25
            + _pct_rank(hot, i) * 0.20
            + _pct_rank(coverage, i) * 0.10,
            4,
        )
    return sorted(boards, key=lambda x: x.score, reverse=True)


def _pct_rank(series: pd.Series, i: int) -> float:
    if len(series) <= 1:
        return 1.0
    return float(series.rank(pct=True).iloc[i])


def _decision_df(df: pd.DataFrame, dt: str, lookback_days: int) -> pd.DataFrame:
    end = pd.Timestamp(dt)
    start = end - pd.Timedelta(days=lookback_days)
    return df[(df["date"] >= start) & (df["date"] <= end)].reset_index(drop=True)


def _score_one_for_sim(strategy: Any, code: str, name: str, sector: str, df: pd.DataFrame) -> dict[str, Any] | None:
    if strategy.name == "MultiFactor" and isinstance(strategy, MultiFactor):
        score, detail = strategy.score(df, name=name, code=code)
        if score == float("-inf") or score < strategy.SCORE_BUY:
            return None
        return {"code": code, "name": name, "action": "BUY", "score": float(score), "reason": "MultiFactor score"}
    sig = strategy.signal_buy(code, name, sector, df)
    if sig is None:
        return None
    return {
        "code": code,
        "name": name,
        "action": "BUY",
        "score": float(sig.confidence) / 100,
        "reason": sig.reason,
        "cash_pct": sig.extra.get("cash_pct", 0.19),
    }


def _price_on(df: pd.DataFrame, dt: str, col: str) -> float:
    row = df[df["date"] == pd.Timestamp(dt)]
    if row.empty:
        return 0.0
    return float(row[col].iloc[0])


def _position_for_strategy(pos: dict[str, Any], dt: str) -> dict[str, Any]:
    return {
        "shares": pos["shares"],
        "avg_cost": pos["cost"] / pos["shares"] if pos["shares"] else 0.0,
        "cost": pos["cost"],
        "available_shares": pos["shares"] if pos["available_from"] <= dt else 0,
        "hold_days": max(0, len([d for d in pos.get("held_dates", []) if d <= dt])),
    }


def _execute_pool_order(
    order: dict[str, Any],
    cash: float,
    positions: dict[str, dict[str, Any]],
    kline_map: dict[str, pd.DataFrame],
    broker: BrokerConfig,
    force: bool = False,
) -> tuple[float, dict[str, Any] | None, dict[str, Any] | None]:
    code = order["code"]
    dt = order["trade_date"]
    df = kline_map.get(code)
    if df is None:
        return cash, None, {"date": dt, "code": code, "reason": "无 K 线"}
    raw_open = _price_on(df, dt, "open")
    if raw_open <= 0:
        return cash, None, {"date": dt, "code": code, "reason": "无有效开盘价"}

    if order["side"] == "BUY":
        price = raw_open * (1 + broker.slippage_bp / 10_000) + broker.slippage_per_share
        budget = cash * float(order.get("cash_pct", 0.19))
        shares = int(budget / price) // broker.lot_size * broker.lot_size
        if shares < broker.lot_size:
            return cash, None, {"date": dt, "code": code, "reason": "现金不足一手"}
        gross = shares * price
        commission = max(gross * broker.commission_rate, broker.min_commission)
        if cash < gross + commission:
            return cash, None, {"date": dt, "code": code, "reason": "现金不足"}
        cash -= gross + commission
        pos = positions.setdefault(code, {"shares": 0, "cost": 0.0, "available_from": f"{dt}~", "held_dates": []})
        pos["shares"] += shares
        pos["cost"] += gross + commission
        pos["available_from"] = min(str(pos.get("available_from", f"{dt}~")), f"{dt}~")
        pos["held_dates"].append(dt)
        return (
            cash,
            _trade(order, price, raw_open, shares, gross, commission, 0.0, cash, reason=order.get("reason", "")),
            None,
        )

    pos = positions.get(code)
    if not pos:
        return cash, None, {"date": dt, "code": code, "reason": "无持仓可卖"}
    if not force and pos["available_from"] > dt:
        return cash, None, {"date": dt, "code": code, "reason": "T+1 锁仓"}
    shares = int(pos["shares"])
    price = max(0.01, raw_open * (1 - broker.slippage_bp / 10_000) - broker.slippage_per_share)
    gross = shares * price
    commission = max(gross * broker.commission_rate, broker.min_commission)
    stamp = gross * broker.stamp_tax_rate
    cash += gross - commission - stamp
    released = float(pos["cost"])
    pnl = gross - commission - stamp - released
    del positions[code]
    trade = _trade(
        order, price, raw_open, shares, gross, commission, stamp, cash, pnl=pnl, reason=order.get("reason", "")
    )
    return cash, trade, None


def _trade(
    order: dict[str, Any],
    price: float,
    raw_open: float,
    shares: int,
    gross: float,
    commission: float,
    stamp: float,
    cash: float,
    pnl: float = 0.0,
    reason: str = "",
) -> dict[str, Any]:
    return {
        "date": order["trade_date"],
        "side": order["side"],
        "code": order["code"],
        "name": order.get("name", order["code"]),
        "price": round(price, 4),
        "raw_open": round(raw_open, 4),
        "shares": shares,
        "gross_amount": round(gross, 2),
        "commission": round(commission, 2),
        "stamp_tax": round(stamp, 2),
        "total_cost": round(commission + stamp, 2),
        "cash_after": round(cash, 2),
        "pnl": round(pnl, 2),
        "reason": reason,
    }


def _portfolio_metrics(
    equity_curve: list[dict[str, Any]],
    trades: list[dict[str, Any]],
    capital: float,
    risk_free_rate: float,
) -> dict[str, Any]:
    equities = pd.Series([x["equity"] for x in equity_curve], dtype="float64")
    final = float(equities.iloc[-1]) if not equities.empty else capital
    total_return = final / capital - 1
    annual = (final / capital) ** (250 / max(1, len(equities))) - 1 if capital > 0 else 0.0
    dd = equities / equities.cummax() - 1 if not equities.empty else pd.Series([0.0])
    returns = equities.pct_change().dropna()
    sharpe = 0.0
    if not returns.empty and float(returns.std()) > 0:
        sharpe = float((returns.mean() - risk_free_rate / 250) / returns.std() * math.sqrt(250))
    sells = [t for t in trades if t["side"] == "SELL"]
    wins = sum(1 for t in sells if t.get("pnl", 0) > 0)
    return {
        "final_equity": round(final, 2),
        "total_return_pct": round(total_return * 100, 2),
        "annual_return_pct": round(annual * 100, 2),
        "max_drawdown_pct": round(float(dd.min()) * 100, 2),
        "sharpe": round(sharpe, 3),
        "win_rate_pct": round(wins / len(sells) * 100, 2) if sells else 0.0,
        "trade_count": len(trades),
        "total_cost": round(sum(float(t.get("total_cost", 0.0)) for t in trades), 2),
    }
