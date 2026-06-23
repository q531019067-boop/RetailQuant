from __future__ import annotations

import pandas as pd

from rquant.backtest.engine import BacktestEngine, BrokerConfig, Order, Position
from rquant.strategy.base import Signal
from rquant.strategy.factor.generator import FactorConfig, generate_factors


def _df(days: int = 8) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=days, freq="B")
    close = [10 + i * 0.1 for i in range(days)]
    return pd.DataFrame(
        {
            "date": dates,
            "open": close,
            "high": [x + 0.2 for x in close],
            "low": [x - 0.2 for x in close],
            "close": close,
            "volume": [1_000_000 + i * 10_000 for i in range(days)],
            "amount": [0 for _ in range(days)],
        }
    )


class BuyThenSellStrategy:
    name = "BuyThenSell"
    category = "test"
    description = "test strategy"

    def __init__(self) -> None:
        self.buy_count = 0
        self.seen_max_dates: list[pd.Timestamp] = []

    def signal_buy(self, code: str, name: str, sector: str, df: pd.DataFrame) -> Signal | None:
        self.seen_max_dates.append(pd.Timestamp(df["date"].max()))
        if self.buy_count > 0:
            return None
        self.buy_count += 1
        close = float(df["close"].iloc[-1])
        return Signal(
            code=code,
            name=name,
            sector=sector,
            strategy=self.name,
            category=self.category,
            current_price=close,
            suggested_buy=close,
            stop_loss=close * 0.9,
            take_profit=close * 1.1,
            reason="buy once",
            confidence=80,
            extra={"cash_pct": 0.5, "position_cap_pct": 0.5},
        )

    def signal_sell(self, position: dict, df: pd.DataFrame) -> dict | None:
        if position.get("shares", 0) > 0:
            return {"reason": "sell next day", "sell_all": True}
        return None


def test_factor_generator_outputs_expected_columns_and_amount_fallback() -> None:
    factors = generate_factors(
        _df(30),
        FactorConfig(windows=(5, 20), fill_method="zero", winsor_limits=(0.05, 0.95)),
    )

    assert {"ret_5d", "vol_20d_ann", "pv_corr_20d"} <= set(factors.columns)
    assert len(factors) == 30
    assert factors.isna().sum().sum() == 0


def test_backtest_uses_next_open_and_t_plus_one() -> None:
    strategy = BuyThenSellStrategy()
    result = BacktestEngine(initial_capital=100_000).run(
        strategy=strategy,
        code="sh600000",
        name="测试股",
        sector="测试",
        df=_df(5),
        start_date="2026-01-01",
        end_date="2026-01-07",
    )

    assert result.fills[0]["side"] == "BUY"
    assert result.fills[0]["date"] == "2026-01-02"
    assert result.fills[1]["side"] == "SELL"
    assert result.fills[1]["date"] == "2026-01-05"
    assert all(max_date <= pd.Timestamp("2026-01-06") for max_date in strategy.seen_max_dates)


def test_commission_stamp_tax_and_slippage_are_recorded() -> None:
    result = BacktestEngine(
        initial_capital=10_000,
        broker=BrokerConfig(slippage_bp=1.0, stamp_tax_rate=0.0005),
    ).run(
        strategy=BuyThenSellStrategy(),
        code="sh600000",
        name="测试股",
        sector="测试",
        df=_df(5),
        start_date="2026-01-01",
        end_date="2026-01-07",
    )

    buy = result.fills[0]
    sell = result.fills[1]
    assert buy["commission"] == 5.0
    assert sell["commission"] == 5.0
    assert sell["stamp_tax"] > 0
    assert result.total_cost >= buy["commission"] + sell["commission"] + sell["stamp_tax"]


def test_sell_all_allows_odd_lot_exit() -> None:
    engine = BacktestEngine(initial_capital=100_000)
    position = Position(code="sh600000", name="测试股")
    position.add_lot(shares=150, cost=1500, available_from="2026-01-02")
    order = Order(
        side="SELL",
        code="sh600000",
        name="测试股",
        signal_date="2026-01-02",
        trade_date="2026-01-05",
        reason="odd lot exit",
        sell_all=True,
    )

    cash, position, fill, skip = engine._execute_order(
        strategy=BuyThenSellStrategy(),
        order=order,
        cash=0,
        position=position,
        open_price=10,
        close_price=10,
    )

    assert skip is None
    assert fill is not None
    assert fill.shares == 150
    assert position is None
    assert cash > 0
