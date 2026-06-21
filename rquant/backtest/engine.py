"""
rquant.backtest.engine — A 股 T+1 回测引擎。

策略只产生信号；本模块负责真实交易约束：
- 买入按 100 股整数手，卖出清仓允许零股一次性卖出
- T+1 可卖，成交日为信号日的下一交易日
- 佣金、印花税、滑点统一从账户现金和成交明细中扣除
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

import pandas as pd

from rquant.strategy.base import Signal, Strategy

Side = Literal["BUY", "SELL"]


@dataclass
class BrokerConfig:
    """A 股撮合与费用参数。"""

    lot_size: int = 100
    commission_rate: float = 0.00025
    min_commission: float = 5.0
    stamp_tax_rate: float = 0.0005
    slippage_bp: float = 1.0
    slippage_per_share: float = 0.0
    default_position_pct: float = 0.95
    risk_free_rate: float = 0.02


@dataclass
class Order:
    """由决策日信号生成、下一交易日开盘撮合的订单。"""

    side: Side
    code: str
    name: str
    signal_date: str
    trade_date: str
    reason: str
    cash_pct: float | None = None
    position_cap_pct: float | None = None
    sell_fraction: float | None = None
    sell_all: bool = False


@dataclass
class Fill:
    """真实成交记录。"""

    date: str
    side: Side
    code: str
    name: str
    strategy: str
    price: float
    raw_open: float
    shares: int
    gross_amount: float
    commission: float
    stamp_tax: float
    slippage_cost: float
    total_cost: float
    cash_after: float
    pnl: float = 0.0
    pnl_pct: float = 0.0
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PositionLot:
    """持仓批次，用于表达 T+1 可卖状态。"""

    shares: int
    cost: float
    available_from: str


@dataclass
class Position:
    code: str
    name: str
    lots: list[PositionLot] = field(default_factory=list)

    @property
    def shares(self) -> int:
        return sum(lot.shares for lot in self.lots)

    @property
    def cost(self) -> float:
        return sum(lot.cost for lot in self.lots)

    @property
    def avg_cost(self) -> float:
        return self.cost / self.shares if self.shares > 0 else 0.0

    def available_shares(self, trade_date: str) -> int:
        return sum(lot.shares for lot in self.lots if lot.available_from <= trade_date)

    def add_lot(self, shares: int, cost: float, available_from: str) -> None:
        self.lots.append(PositionLot(shares=shares, cost=cost, available_from=available_from))

    def remove_shares(self, shares: int, trade_date: str, ignore_availability: bool = False) -> float:
        """按 FIFO 移除可卖批次，返回释放的持仓成本。"""
        remaining = shares
        released_cost = 0.0
        new_lots: list[PositionLot] = []
        for lot in self.lots:
            if remaining <= 0 or (lot.available_from > trade_date and not ignore_availability):
                new_lots.append(lot)
                continue
            take = min(lot.shares, remaining)
            released_cost += lot.cost * (take / lot.shares)
            lot.shares -= take
            lot.cost -= lot.cost * (take / (lot.shares + take))
            remaining -= take
            if lot.shares > 0:
                new_lots.append(lot)
        self.lots = new_lots
        if remaining > 0:
            raise ValueError(f"可卖数量不足，还差 {remaining} 股")
        return released_cost


@dataclass
class BacktestResult:
    strategy: str
    code: str
    name: str
    start_date: str
    end_date: str
    initial_capital: float
    final_equity: float
    total_return_pct: float
    annual_return_pct: float
    max_drawdown_pct: float
    sharpe: float
    win_rate_pct: float
    trade_count: int
    total_cost: float
    fills: list[dict[str, Any]]
    equity_curve: list[dict[str, Any]]
    skipped: list[dict[str, Any]] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("fills", None)
        data.pop("equity_curve", None)
        data.pop("skipped", None)
        return data


class BacktestEngine:
    """单标的、多策略可复用的 A 股日频回测引擎。"""

    def __init__(
        self,
        initial_capital: float = 100_000.0,
        broker: BrokerConfig | None = None,
    ) -> None:
        self.initial_capital = initial_capital
        self.broker = broker or BrokerConfig()

    def run(
        self,
        strategy: Strategy,
        code: str,
        name: str,
        sector: str,
        df: pd.DataFrame,
        start_date: str,
        end_date: str,
    ) -> BacktestResult:
        """按日回放。信号在 dt 收盘产生，订单在 next_dt 开盘撮合。"""
        data = _prepare_kline(df, end_date)
        trade_data = data[(data["date"] >= pd.Timestamp(start_date)) & (data["date"] <= pd.Timestamp(end_date))]
        trade_data = trade_data.reset_index(drop=True)
        if len(trade_data) < 2:
            raise ValueError("至少需要 2 个交易日才能执行 T+1 回测")

        cash = self.initial_capital
        position: Position | None = None
        pending: list[Order] = []
        fills: list[Fill] = []
        skipped: list[dict[str, Any]] = []
        equity_curve: list[dict[str, Any]] = []

        dates = [str(d.date()) for d in trade_data["date"]]

        for i, dt in enumerate(dates):
            row = trade_data.iloc[i]
            open_price = float(row["open"])
            close_price = float(row["close"])

            # 1) 先执行昨天收盘后排队到今天开盘的订单。
            today_orders = [order for order in pending if order.trade_date == dt]
            pending = [order for order in pending if order.trade_date != dt]
            for order in today_orders:
                cash, position, fill, skip = self._execute_order(
                    strategy=strategy,
                    order=order,
                    cash=cash,
                    position=position,
                    open_price=open_price,
                    close_price=close_price,
                )
                if fill is not None:
                    fills.append(fill)
                if skip is not None:
                    skipped.append(skip)

            # 2) 收盘估值。
            shares = position.shares if position is not None else 0
            position_value = shares * close_price
            equity = cash + position_value
            equity_curve.append(
                {
                    "date": dt,
                    "equity": round(equity, 2),
                    "cash": round(cash, 2),
                    "position_value": round(position_value, 2),
                    "shares": shares,
                }
            )

            # 最后一日只估值，不再生成无法成交的订单。
            if i >= len(dates) - 1:
                continue

            decision_df = data[data["date"] <= row["date"]].reset_index(drop=True)
            if decision_df["date"].max() > row["date"]:
                raise RuntimeError("未来函数防线失效：策略输入包含决策日之后的数据")
            next_dt = dates[i + 1]

            # 3) 先卖后买。卖出信号只对已有持仓生成。
            position_dict = _position_to_strategy_dict(position, close_price, dt, dates)
            if position is not None and position.shares > 0:
                sell_signal = strategy.signal_sell(position_dict, decision_df)
                if sell_signal is not None:
                    pending.append(
                        _sell_order_from_signal(
                            code=code,
                            name=name,
                            signal_date=dt,
                            trade_date=next_dt,
                            signal=sell_signal,
                        )
                    )

            buy_signal = strategy.signal_buy(code, name, sector, decision_df)
            if buy_signal is not None:
                pending.append(
                    _buy_order_from_signal(
                        code=code,
                        name=name,
                        signal_date=dt,
                        trade_date=next_dt,
                        signal=buy_signal,
                    )
                )

        # 3) 若末日仍有可卖持仓，用末日收盘价强平，避免指标残留账面持仓。
        last_dt = dates[-1]
        last_close = float(trade_data.iloc[-1]["close"])
        if position is not None and position.shares > 0:
            force_order = Order(
                side="SELL",
                code=code,
                name=name,
                signal_date=last_dt,
                trade_date=last_dt,
                reason="回测结束强平",
                sell_all=True,
            )
            cash, position, fill, skip = self._execute_order(
                strategy=strategy,
                order=force_order,
                cash=cash,
                position=position,
                open_price=last_close,
                close_price=last_close,
                allow_same_day_exit=True,
            )
            if fill is not None:
                fills.append(fill)
            if skip is not None:
                skipped.append(skip)
            equity_curve[-1]["equity"] = round(cash, 2)
            equity_curve[-1]["cash"] = round(cash, 2)
            equity_curve[-1]["position_value"] = 0.0
            equity_curve[-1]["shares"] = 0

        metrics = _calc_metrics(equity_curve, fills, self.initial_capital, self.broker.risk_free_rate)
        return BacktestResult(
            strategy=strategy.name,
            code=code,
            name=name,
            start_date=dates[0],
            end_date=dates[-1],
            initial_capital=self.initial_capital,
            final_equity=round(equity_curve[-1]["equity"], 2),
            total_return_pct=metrics["total_return_pct"],
            annual_return_pct=metrics["annual_return_pct"],
            max_drawdown_pct=metrics["max_drawdown_pct"],
            sharpe=metrics["sharpe"],
            win_rate_pct=metrics["win_rate_pct"],
            trade_count=len(fills),
            total_cost=metrics["total_cost"],
            fills=[fill.to_dict() for fill in fills],
            equity_curve=equity_curve,
            skipped=skipped,
        )

    def _execute_order(
        self,
        strategy: Strategy,
        order: Order,
        cash: float,
        position: Position | None,
        open_price: float,
        close_price: float,
        allow_same_day_exit: bool = False,
    ) -> tuple[float, Position | None, Fill | None, dict[str, Any] | None]:
        if open_price <= 0 or math.isnan(open_price):
            return cash, position, None, {"date": order.trade_date, "reason": "无有效开盘价", "order": asdict(order)}
        if order.side == "BUY":
            return self._execute_buy(strategy, order, cash, position, open_price, close_price)
        return self._execute_sell(strategy, order, cash, position, open_price, allow_same_day_exit)

    def _execute_buy(
        self,
        strategy: Strategy,
        order: Order,
        cash: float,
        position: Position | None,
        open_price: float,
        close_price: float,
    ) -> tuple[float, Position | None, Fill | None, dict[str, Any] | None]:
        price, slippage_cost_per_share = self._slipped_price("BUY", open_price)
        current_value = (position.shares * close_price) if position is not None else 0.0
        equity = cash + current_value

        cap_pct = order.position_cap_pct if order.position_cap_pct is not None else self.broker.default_position_pct
        cap_value = max(0.0, equity * cap_pct - current_value)
        cash_pct = order.cash_pct if order.cash_pct is not None else self.broker.default_position_pct
        budget = min(cash * cash_pct, cap_value, cash)
        shares = int(budget / price) // self.broker.lot_size * self.broker.lot_size

        while shares >= self.broker.lot_size:
            gross = shares * price
            commission = self._commission(gross)
            if cash >= gross + commission:
                break
            shares -= self.broker.lot_size

        if shares < self.broker.lot_size:
            return (
                cash,
                position,
                None,
                {"date": order.trade_date, "reason": "现金不足或仓位上限不足", "order": asdict(order)},
            )

        gross = shares * price
        commission = self._commission(gross)
        slippage_cost = slippage_cost_per_share * shares
        total_cost = commission + slippage_cost
        cash -= gross + commission
        if position is None:
            position = Position(code=order.code, name=order.name)
        position.add_lot(shares=shares, cost=gross + commission, available_from=_next_date_marker(order.trade_date))

        fill = Fill(
            date=order.trade_date,
            side="BUY",
            code=order.code,
            name=order.name,
            strategy=strategy.name,
            price=round(price, 4),
            raw_open=round(open_price, 4),
            shares=shares,
            gross_amount=round(gross, 2),
            commission=round(commission, 2),
            stamp_tax=0.0,
            slippage_cost=round(slippage_cost, 2),
            total_cost=round(total_cost, 2),
            cash_after=round(cash, 2),
            reason=order.reason,
        )
        return cash, position, fill, None

    def _execute_sell(
        self,
        strategy: Strategy,
        order: Order,
        cash: float,
        position: Position | None,
        open_price: float,
        allow_same_day_exit: bool = False,
    ) -> tuple[float, Position | None, Fill | None, dict[str, Any] | None]:
        if position is None or position.shares <= 0:
            return cash, position, None, {"date": order.trade_date, "reason": "无持仓可卖", "order": asdict(order)}

        available = position.shares if allow_same_day_exit else position.available_shares(order.trade_date)
        if available <= 0:
            return (
                cash,
                position,
                None,
                {"date": order.trade_date, "reason": "T+1 锁仓，暂无可卖股数", "order": asdict(order)},
            )

        if order.sell_all:
            shares = available
        else:
            fraction = order.sell_fraction if order.sell_fraction is not None else 1.0
            shares = int(available * fraction)
            if shares < available:
                shares = shares // self.broker.lot_size * self.broker.lot_size
            if shares <= 0:
                return (
                    cash,
                    position,
                    None,
                    {"date": order.trade_date, "reason": "卖出数量不足一手", "order": asdict(order)},
                )

        price, slippage_cost_per_share = self._slipped_price("SELL", open_price)
        gross = shares * price
        commission = self._commission(gross)
        stamp_tax = gross * self.broker.stamp_tax_rate
        slippage_cost = slippage_cost_per_share * shares
        total_cost = commission + stamp_tax + slippage_cost
        released_cost = position.remove_shares(shares, order.trade_date, ignore_availability=allow_same_day_exit)
        net = gross - commission - stamp_tax
        cash += net
        pnl = net - released_cost
        pnl_pct = pnl / released_cost * 100 if released_cost > 0 else 0.0
        if position.shares == 0:
            position = None

        fill = Fill(
            date=order.trade_date,
            side="SELL",
            code=order.code,
            name=order.name,
            strategy=strategy.name,
            price=round(price, 4),
            raw_open=round(open_price, 4),
            shares=shares,
            gross_amount=round(gross, 2),
            commission=round(commission, 2),
            stamp_tax=round(stamp_tax, 2),
            slippage_cost=round(slippage_cost, 2),
            total_cost=round(total_cost, 2),
            cash_after=round(cash, 2),
            pnl=round(pnl, 2),
            pnl_pct=round(pnl_pct, 2),
            reason=order.reason,
        )
        return cash, position, fill, None

    def _commission(self, amount: float) -> float:
        return max(amount * self.broker.commission_rate, self.broker.min_commission)

    def _slipped_price(self, side: Side, open_price: float) -> tuple[float, float]:
        bp_cost = open_price * self.broker.slippage_bp / 10_000
        per_share = bp_cost + self.broker.slippage_per_share
        if side == "BUY":
            return open_price + per_share, per_share
        return max(0.01, open_price - per_share), per_share


def _prepare_kline(df: pd.DataFrame, end_date: str) -> pd.DataFrame:
    required = {"date", "open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"K 线缺少必要列: {sorted(missing)}")
    data = df.copy()
    data["date"] = pd.to_datetime(data["date"])
    for col in ("open", "high", "low", "close", "volume"):
        data[col] = pd.to_numeric(data[col], errors="coerce")
    data = data.dropna(subset=["date", "open", "high", "low", "close"])
    data = data[data["date"] <= pd.Timestamp(end_date)]
    data = data.sort_values("date").reset_index(drop=True)
    return data


def _position_to_strategy_dict(
    position: Position | None,
    close_price: float,
    date: str,
    all_dates: list[str],
) -> dict[str, Any]:
    if position is None:
        return {}
    first_marker = min((lot.available_from for lot in position.lots), default=date)
    first_trade_date = first_marker[:10]
    buy_index = all_dates.index(first_trade_date) if first_trade_date in all_dates else 0
    current_index = all_dates.index(date) if date in all_dates else buy_index
    return {
        "code": position.code,
        "name": position.name,
        "shares": position.shares,
        "avg_cost": position.avg_cost,
        "cost": position.cost,
        "market_value": position.shares * close_price,
        "available_shares": position.available_shares(date),
        "hold_days": max(0, current_index - buy_index),
    }


def _buy_order_from_signal(code: str, name: str, signal_date: str, trade_date: str, signal: Signal) -> Order:
    return Order(
        side="BUY",
        code=code,
        name=name,
        signal_date=signal_date,
        trade_date=trade_date,
        reason=signal.reason,
        cash_pct=signal.extra.get("cash_pct"),
        position_cap_pct=signal.extra.get("position_cap_pct"),
    )


def _sell_order_from_signal(
    code: str,
    name: str,
    signal_date: str,
    trade_date: str,
    signal: dict[str, Any],
) -> Order:
    return Order(
        side="SELL",
        code=code,
        name=name,
        signal_date=signal_date,
        trade_date=trade_date,
        reason=str(signal.get("reason", "策略卖出")),
        sell_fraction=signal.get("sell_fraction"),
        sell_all=bool(signal.get("sell_all", True)),
    )


def _next_date_marker(trade_date: str) -> str:
    """字符串日期可按字典序比较；买入日之后才可卖。"""
    return f"{trade_date}~"


def _calc_metrics(
    equity_curve: list[dict[str, Any]],
    fills: list[Fill],
    initial_capital: float,
    risk_free_rate: float,
) -> dict[str, float]:
    equities = pd.Series([p["equity"] for p in equity_curve], dtype="float64")
    final = float(equities.iloc[-1])
    total_return = final / initial_capital - 1
    trading_days = max(1, len(equities))
    annual_return = (final / initial_capital) ** (250 / trading_days) - 1 if initial_capital > 0 else 0.0

    peak = equities.cummax()
    drawdown = equities / peak - 1
    max_drawdown = float(drawdown.min()) if len(drawdown) else 0.0

    returns = equities.pct_change().dropna()
    if returns.empty or float(returns.std()) == 0:
        sharpe = 0.0
    else:
        daily_rf = risk_free_rate / 250
        sharpe = float((returns.mean() - daily_rf) / returns.std() * math.sqrt(250))

    sell_fills = [fill for fill in fills if fill.side == "SELL"]
    wins = sum(1 for fill in sell_fills if fill.pnl > 0)
    win_rate = wins / len(sell_fills) if sell_fills else 0.0
    total_cost = sum(fill.total_cost for fill in fills)

    return {
        "total_return_pct": round(total_return * 100, 2),
        "annual_return_pct": round(annual_return * 100, 2),
        "max_drawdown_pct": round(max_drawdown * 100, 2),
        "sharpe": round(sharpe, 3),
        "win_rate_pct": round(win_rate * 100, 2),
        "total_cost": round(total_cost, 2),
    }
