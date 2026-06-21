"""
rQuant.strategies.mean_reversion.rsi_reversion — RSI 均值回归策略。

信号只描述买卖意图；T+1 锁仓、手数、费用和滑点由 backtest.engine 处理。
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ..base import Signal, atr, ma, prev_ma, rsi
from ..registry import register


@register
class RsiMeanReversion:
    """RSI(14) 超卖反弹策略，带 MA200 趋势过滤和 ATR 风险降档。"""

    name = "RsiMeanReversion"
    category = "mean_reversion"
    description = "RSI(14) 超卖/超买 + MA200 趋势过滤 + ATR 仓位控制"

    RSI_N = 14
    RSI_BUY = 30.0
    RSI_SELL = 70.0
    TREND_MA_N = 200
    ATR_N = 14
    MAX_HOLD_DAYS = 20
    STOP_ATR = 2.0
    NORMAL_CASH_PCT = 0.60
    DEFENSIVE_CASH_PCT = 0.30

    def signal_buy(self, code: str, name: str, sector: str, df: pd.DataFrame) -> Signal | None:
        if df is None or len(df) < self.TREND_MA_N + 1:
            return None

        close = float(df["close"].iloc[-1])
        rsi_value = rsi(df, self.RSI_N)
        ma200 = ma(df, self.TREND_MA_N)
        ma200_prev = prev_ma(df, self.TREND_MA_N)
        atr_value = atr(df, self.ATR_N)
        if rsi_value >= self.RSI_BUY:
            return None

        trend_ok = close >= ma200 and ma200 >= ma200_prev
        defensive_ok = ma200 >= ma200_prev and close >= ma200 - 1.5 * atr_value
        if not (trend_ok or defensive_ok):
            return None

        cash_pct = self.NORMAL_CASH_PCT if trend_ok else self.DEFENSIVE_CASH_PCT
        stop_loss = max(0.01, close - self.STOP_ATR * atr_value)
        take_profit = close + 2.5 * atr_value
        suggested = close * 1.003
        confidence = 62.0 + min(20.0, self.RSI_BUY - rsi_value)
        if not trend_ok:
            confidence -= 10.0

        return Signal(
            code=code,
            name=name,
            sector=sector,
            strategy=self.name,
            category=self.category,
            current_price=close,
            suggested_buy=round(suggested, 2),
            stop_loss=round(stop_loss, 2),
            take_profit=round(take_profit, 2),
            reason=(
                f"RSI({self.RSI_N})={rsi_value:.1f}<30 超卖，"
                f"MA200 {'上方' if trend_ok else '附近防守仓'}，ATR={atr_value:.2f}"
            ),
            confidence=round(max(40.0, min(90.0, confidence)), 1),
            extra={
                "rsi": round(rsi_value, 2),
                "ma200": round(ma200, 3),
                "atr": round(atr_value, 3),
                "cash_pct": cash_pct,
                "position_cap_pct": cash_pct,
                "kind": "rsi_mean_reversion",
            },
        )

    def signal_sell(self, position: dict[str, Any], df: pd.DataFrame) -> dict[str, Any] | None:
        if df is None or len(df) < self.RSI_N + 1 or not position:
            return None

        close = float(df["close"].iloc[-1])
        avg_cost = float(position.get("avg_cost") or 0)
        hold_days = int(position.get("hold_days") or 0)
        if avg_cost <= 0:
            return None

        rsi_value = rsi(df, self.RSI_N)
        atr_value = atr(df, self.ATR_N)
        stop_price = avg_cost - self.STOP_ATR * atr_value
        pnl_pct = (close / avg_cost - 1) * 100

        if close <= stop_price:
            return {
                "reason": f"RSI 策略 ATR 止损：收盘 {close:.2f} <= {stop_price:.2f}（当前 {pnl_pct:+.1f}%）",
                "urgency": "urgent",
                "sell_all": True,
            }
        if rsi_value >= self.RSI_SELL:
            return {
                "reason": f"RSI({self.RSI_N})={rsi_value:.1f}>70，超买止盈/退出",
                "urgency": "normal",
                "sell_all": True,
            }
        if hold_days >= self.MAX_HOLD_DAYS:
            return {
                "reason": f"RSI 均值回归持仓满 {hold_days} 日，时间止损退出",
                "urgency": "normal",
                "sell_all": True,
            }
        return None
