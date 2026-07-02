"""
双均线交叉策略 —— MA5 上穿 MA20 金叉买入，MA5 下穿 MA20 死叉卖出。
"""

from vnpy.trader.constant import Direction
from vnpy.trader.object import TradeData, BarData

from .base import BaseStrategy, _ma_from_bars, calc_shares


class MovingAverageCrossStrategy(BaseStrategy):
    name = "ma_cross"
    label = "均线交叉"
    description = "MA5/20 双均线金叉买入、死叉卖出"
    color = "#52c41a"

    fast_n: int = 5
    slow_n: int = 20
    stop_loss: float = -0.08
    take_profit: float = 0.15
    top_k: int = 5
    price_add: float = 0.005

    _param_meta = {
        "fast_n": {"type": "int", "min": 3, "max": 30, "label": "快线周期"},
        "slow_n": {"type": "int", "min": 10, "max": 120, "label": "慢线周期"},
        "stop_loss": {"type": "float", "min": -0.5, "max": -0.01, "step": 0.01, "label": "止损线"},
        "take_profit": {"type": "float", "min": 0.05, "max": 1.0, "step": 0.01, "label": "止盈线"},
        "top_k": {"type": "int", "min": 1, "max": 20, "label": "持仓数量"},
        "price_add": {"type": "float", "min": 0, "max": 0.1, "step": 0.001, "label": "调仓滑点"},
    }

    def on_init(self) -> None:
        self.entry_price: dict[str, float] = {}
        self.max_cache: int = self.slow_n + 2
        self.bar_history: dict[str, list[BarData]] = {}
        self.write_log(f"均线交叉 | MA{self.fast_n}/{self.slow_n}")

    def on_bars(self, bars: dict[str, BarData]) -> None:
        # 维护 bar 缓存
        for sym, bar in bars.items():
            if sym not in self.bar_history:
                self.bar_history[sym] = []
            self.bar_history[sym].append(bar)
            if len(self.bar_history[sym]) > self.max_cache:
                self.bar_history[sym] = self.bar_history[sym][-self.max_cache :]

        # ---- 查找金叉候选 ----
        candidates: list[tuple[str, float]] = []
        for sym in bars:
            hist = self.bar_history.get(sym, [])
            if len(hist) < self.slow_n + 2:
                continue
            if self.pos_data.get(sym, 0) > 0:
                continue

            fast_now = _ma_from_bars(hist, self.fast_n)
            slow_now = _ma_from_bars(hist, self.slow_n)
            fast_prev = _ma_from_bars(hist[:-1], self.fast_n)
            slow_prev = _ma_from_bars(hist[:-1], self.slow_n)

            # 金叉：昨日快线 ≤ 慢线，今日快线 > 慢线
            if fast_prev <= slow_prev and fast_now > slow_now:
                confidence = 75.0
                candidates.append((sym, confidence))

        # ---- 检查持仓退出 ----
        for sym in list(self.pos_data.keys()):
            if self.pos_data[sym] <= 0 or sym not in bars:
                continue
            entry_p = self.entry_price.get(sym)
            hist = self.bar_history.get(sym, [])
            if len(hist) < self.slow_n + 2 or entry_p is None:
                self.target_data[sym] = self.pos_data[sym]
                continue

            close = hist[-1].close_price
            pnl_pct = close / entry_p - 1

            # 止损/止盈
            if pnl_pct <= self.stop_loss or pnl_pct >= self.take_profit:
                self.target_data[sym] = 0.0
                continue

            # 死叉：今日快线 < 慢线（仅在有浮亏时离场）
            fast_now = _ma_from_bars(hist, self.fast_n)
            slow_now = _ma_from_bars(hist, self.slow_n)
            if fast_now < slow_now and pnl_pct < 0:
                self.target_data[sym] = 0.0
                continue

            self.target_data[sym] = self.pos_data[sym]

        self.execute_trading(bars, self.price_add)

        # ---- 新建仓位 ----
        candidates.sort(key=lambda x: x[1], reverse=True)
        selected = candidates[: self.top_k]
        if selected:
            cash = self.get_cash_available()
            per = cash / len(selected)
            for sym, _ in selected:
                if sym not in bars:
                    continue
                price = bars[sym].close_price * (1 + self.price_add)
                shares = calc_shares(per, price)
                if shares > 0:
                    self.buy(sym, price, shares)

    def on_trade(self, trade: TradeData) -> None:
        sym = trade.vt_symbol
        if trade.direction == Direction.LONG:
            new_pos = self.pos_data.get(sym, 0)
            old_pos = new_pos - trade.volume
            old_entry = self.entry_price.get(sym, trade.price)
            self.entry_price[sym] = (
                (old_pos * old_entry + trade.volume * trade.price) / new_pos if new_pos > 0 else trade.price
            )
        else:
            if self.pos_data.get(sym, 0) <= 0:
                self.entry_price.pop(sym, None)
