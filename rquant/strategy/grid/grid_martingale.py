"""
rQuant.strategies.grid.grid_martingale — 风控网格交易策略。

保留历史类名 `GridMartingale` 以兼容注册名，但实现不再做无限马丁。
核心风控：单票仓位上限、单格资金上限、破网止损。
"""

from __future__ import annotations
from typing import Any

import pandas as pd

from ..base import Signal
from ..registry import register


@register
class GridMartingale:
    """适合震荡市的日线网格策略，禁止无限补仓。"""

    name = "GridMartingale"
    category = "grid"
    description = "日线风控网格：等距网格 + 仓位上限 + 破网止损"

    GRID_N = 20
    GRID_LEVELS = 6
    BASE_MODE = "ma"  # "ma" 或 "initial"，当前信号层用 rolling MA
    POSITION_CAP_PCT = 0.50
    PER_GRID_CASH_PCT = 0.10
    BREAK_STOP_PCT = 0.05
    TAKE_PROFIT_GRID_RATIO = 0.75

    def signal_buy(self, code: str, name: str, sector: str, df: pd.DataFrame) -> Signal | None:
        """价格跌入下方网格时，生成单格买入信号。"""
        if df is None or len(df) < self.GRID_N + 1:
            return None

        close = float(df["close"].iloc[-1])
        grid = self._grid(df)
        if grid is None:
            return None
        low, high, grid_size, ratio = grid

        # 只在下半区分批接，越靠近下沿置信度越高；破网交给卖出风控，不继续补仓。
        if ratio < 0 or ratio > 0.45:
            return None

        confidence = max(40.0, 70.0 - ratio * 100)
        suggested = round(close * 1.002, 2)
        return Signal(
            code=code,
            name=name,
            sector=sector,
            strategy=self.name,
            category=self.category,
            current_price=close,
            suggested_buy=suggested,
            stop_loss=round(low * (1 - self.BREAK_STOP_PCT), 2),
            take_profit=round(low + (self.TAKE_PROFIT_GRID_RATIO * (high - low)), 2),
            reason=(
                f"网格买入：现价 ¥{close:.3f} 位于 {self.GRID_N} 日区间 "
                f"¥{low:.3f}-¥{high:.3f} 的 {ratio * 100:.0f}% 位置"
            ),
            confidence=round(confidence, 1),
            extra={
                "grid_high": high,
                "grid_low": low,
                "grid_size": grid_size,
                "position_ratio": round(ratio, 3),
                "cash_pct": self.PER_GRID_CASH_PCT,
                "position_cap_pct": self.POSITION_CAP_PCT,
                "kind": "grid_buy",
            },
        )

    def signal_sell(self, position: dict[str, Any], df: pd.DataFrame) -> dict[str, Any] | None:
        """上沿分批止盈；跌破网格下沿一定比例后清仓退出。"""
        if df is None or df.empty or len(df) < self.GRID_N + 1:
            return None
        close = float(df["close"].iloc[-1])
        avg_cost = position.get("avg_cost", 0)
        shares = position.get("shares", 0)
        if avg_cost <= 0 or shares <= 0:
            return None

        grid = self._grid(df)
        if grid is None:
            return None
        low, high, _, ratio = grid
        pnl_pct = (close / avg_cost - 1) * 100
        break_price = low * (1 - self.BREAK_STOP_PCT)

        if close <= break_price:
            return {
                "reason": f"网格破网止损：收盘 {close:.2f} <= {break_price:.2f}，清仓跳出",
                "urgency": "urgent",
                "sell_all": True,
            }

        if ratio >= self.TAKE_PROFIT_GRID_RATIO and pnl_pct > 0:
            return {
                "reason": f"网格上沿止盈：现价位于区间 {ratio * 100:.0f}% 位置，浮盈 {pnl_pct:+.1f}%",
                "urgency": "normal",
                "sell_fraction": 0.5,
                "sell_all": False,
            }
        return None

    def _grid(self, df: pd.DataFrame) -> tuple[float, float, float, float] | None:
        """用前 N 日高低点定网格，避免当前 K 线扩大网格后再触发信号。"""
        high = float(df["high"].iloc[-(self.GRID_N + 1) : -1].max())
        low = float(df["low"].iloc[-(self.GRID_N + 1) : -1].min())
        close = float(df["close"].iloc[-1])
        if high <= low:
            return None
        grid_size = (high - low) / self.GRID_LEVELS
        position_ratio = (close - low) / (high - low)
        return low, high, grid_size, position_ratio
