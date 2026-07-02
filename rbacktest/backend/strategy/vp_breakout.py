"""
量价突破策略 —— 突破前N日高点 + 量能放大 + 强势收盘时买入；止盈/止损/破均线卖出。
"""

import numpy as np
from vnpy.trader.object import TradeData, BarData

from .base import BaseStrategy, calc_shares


class VpBreakoutStrategy(BaseStrategy):
    name = "vp_breakout"
    label = "量价突破"
    description = "突破前N日高点 + 量能放大 + 强势收盘时买入；止盈/止损/破均线卖出"
    color = "#722ed1"

    high_n: int = 11
    vol_ratio_min: float = 1.5
    close_to_high: float = 0.97
    ma_exit: int = 10
    take_profit: float = 0.30
    stop_loss: float = -0.10
    top_k: int = 5
    cash_ratio: float = 0.95
    price_add: float = 0.005

    _param_meta = {
        "high_n": {"type": "int", "min": 5, "max": 60, "label": "突破窗口"},
        "vol_ratio_min": {"type": "float", "min": 1.0, "max": 5.0, "step": 0.1, "label": "量比最低阈值"},
        "close_to_high": {"type": "float", "min": 0.9, "max": 1.0, "step": 0.01, "label": "强势收盘比"},
        "ma_exit": {"type": "int", "min": 5, "max": 60, "label": "离场均线"},
        "take_profit": {"type": "float", "min": 0.05, "max": 1.0, "step": 0.01, "label": "止盈线"},
        "stop_loss": {"type": "float", "min": -0.5, "max": -0.01, "step": 0.01, "label": "止损线"},
        "top_k": {"type": "int", "min": 1, "max": 20, "label": "持仓数量"},
        "cash_ratio": {"type": "float", "min": 0.5, "max": 1.0, "step": 0.05, "label": "现金使用率"},
        "price_add": {"type": "float", "min": 0, "max": 0.1, "step": 0.001, "label": "调仓滑点"},
    }

    def on_init(self) -> None:
        self.entry_price: dict[str, float] = {}
        self.max_cache: int = max(self.high_n, self.ma_exit) + 2
        self.write_log(f"量价突破 | pool={len(self.vt_symbols)} top_k={self.top_k}")

    def on_bars(self, bars: dict[str, BarData]) -> None:
        """每日扫描：价格突破前 high_n 日高点 + 量能放大 + 强势收盘时买入。

        买入条件（三个同时满足）：
            1. 收盘价 > 前 high_n 日最高价（突破）
            2. 当日成交量 ≥ vol_ratio_min × 近 5 日均量（放量确认）
            3. 收盘价 / 当日最高价 ≥ close_to_high（强势，非冲高回落）

        卖出条件（满足任一）：
            - 浮盈 ≥ take_profit（止盈）
            - 浮亏 ≤ stop_loss（止损）
            - 收盘价 < MA(ma_exit) × 0.97（破均线）
        """
        self._maintain_bars(bars)

        # 查找突破候选
        candidates: list[tuple[str, float]] = []
        for sym in bars:
            hist = self.bar_history.get(sym, [])
            if len(hist) < self.high_n + 1:
                continue
            window = hist[-(self.high_n + 1) :]
            close = window[-1].close_price
            high_today = window[-1].high_price
            vol_today = window[-1].volume
            if self.pos_data.get(sym, 0) > 0:
                continue
            prev_high = max(b.high_price for b in window[:-1])
            if close <= prev_high:
                continue
            avg_vol = np.mean([b.volume for b in hist[-6:-1]])
            if avg_vol <= 0 or vol_today < self.vol_ratio_min * avg_vol:
                continue
            if high_today <= 0 or (close / high_today) < self.close_to_high:
                continue
            vol_ratio = vol_today / avg_vol
            confidence = max(60.0, min(90.0, 60.0 + (vol_ratio - self.vol_ratio_min) * 15.0))
            candidates.append((sym, confidence))

        # 检查持仓退出条件
        for sym in list(self.pos_data.keys()):
            if self.pos_data[sym] <= 0 or sym not in bars:
                continue
            entry_p = self.entry_price.get(sym)
            hist = self.bar_history.get(sym, [])
            if len(hist) < self.ma_exit + 1 or entry_p is None:
                self.target_data[sym] = self.pos_data[sym]
                continue
            close = hist[-1].close_price
            pnl_pct = close / entry_p - 1
            if pnl_pct >= self.take_profit or pnl_pct <= self.stop_loss:
                self.target_data[sym] = 0.0
                continue
            ma_val = np.mean([b.close_price for b in hist[-self.ma_exit :]])
            if close < ma_val * 0.97:
                self.target_data[sym] = 0.0
                continue
            self.target_data[sym] = self.pos_data[sym]

        self.execute_trading(bars, self.price_add)

        # 新建仓位
        candidates.sort(key=lambda x: x[1], reverse=True)
        selected = candidates[: self.top_k]
        if selected:
            cash = self.get_cash_available() * self.cash_ratio
            per = cash / len(selected)
            for sym, _ in selected:
                if sym not in bars:
                    continue
                price = bars[sym].close_price * (1 + self.price_add)
                volume = calc_shares(per, price)
                if volume >= 100:
                    self.buy(sym, price, volume)

    def on_trade(self, trade: TradeData) -> None:
        self._update_entry_price(trade)
