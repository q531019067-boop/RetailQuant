"""rQuant.strategies.trend.ma_cross — MA5/20 双均线策略。"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ..base import Signal, ma, prev_ma
from ..registry import register


@register
class MovingAverageCross:
    """MA5 上穿 MA20 买入，MA5 下穿 MA20 或硬止损卖出。"""

    name = "MovingAverageCross"
    category = "trend"
    description = "MA5/20 双均线金叉死叉策略"

    FAST_N = 5
    SLOW_N = 20
    STOP_LOSS = -0.08
    TAKE_PROFIT = 0.15
    CASH_PCT = 0.95

    def signal_buy(self, code: str, name: str, sector: str, df: pd.DataFrame) -> Signal | None:
        if df is None or len(df) < self.SLOW_N + 1:
            return None

        fast = ma(df, self.FAST_N)
        slow = ma(df, self.SLOW_N)
        fast_prev = prev_ma(df, self.FAST_N)
        slow_prev = prev_ma(df, self.SLOW_N)
        if not (fast_prev <= slow_prev and fast > slow):
            return None

        close = float(df["close"].iloc[-1])
        suggested = close * 1.003
        return Signal(
            code=code,
            name=name,
            sector=sector,
            strategy=self.name,
            category=self.category,
            current_price=close,
            suggested_buy=round(suggested, 2),
            stop_loss=round(suggested * (1 + self.STOP_LOSS), 2),
            take_profit=round(suggested * (1 + self.TAKE_PROFIT), 2),
            reason=f"MA{self.FAST_N} 上穿 MA{self.SLOW_N}：{fast:.2f}>{slow:.2f}",
            confidence=75.0,
            extra={
                "ma_fast": round(fast, 3),
                "ma_slow": round(slow, 3),
                "cash_pct": self.CASH_PCT,
                "position_cap_pct": self.CASH_PCT,
                "kind": "ma_cross",
            },
        )

    def signal_sell(self, position: dict[str, Any], df: pd.DataFrame) -> dict[str, Any] | None:
        if df is None or len(df) < self.SLOW_N + 1 or not position:
            return None

        close = float(df["close"].iloc[-1])
        avg_cost = float(position.get("avg_cost") or 0)
        if avg_cost <= 0:
            return None

        pnl_pct = close / avg_cost - 1
        fast = ma(df, self.FAST_N)
        slow = ma(df, self.SLOW_N)
        fast_prev = prev_ma(df, self.FAST_N)
        slow_prev = prev_ma(df, self.SLOW_N)

        if pnl_pct <= self.STOP_LOSS:
            return {
                "reason": f"MA 双均线硬止损：{pnl_pct * 100:+.1f}% <= {self.STOP_LOSS * 100:.0f}%",
                "urgency": "urgent",
                "sell_all": True,
            }
        if pnl_pct >= self.TAKE_PROFIT:
            return {
                "reason": f"MA 双均线止盈：{pnl_pct * 100:+.1f}% >= {self.TAKE_PROFIT * 100:.0f}%",
                "urgency": "normal",
                "sell_all": True,
            }
        if fast_prev >= slow_prev and fast < slow:
            return {
                "reason": f"MA{self.FAST_N} 下穿 MA{self.SLOW_N}：{fast:.2f}<{slow:.2f}",
                "urgency": "normal",
                "sell_all": True,
            }
        return None
