"""
海龟交易策略 —— 唐奇安通道突破。
20 日新高入场，10 日新低离场，2×ATR 移动止损。
"""

from vnpy.trader.constant import Direction
from vnpy.trader.object import TradeData, BarData

from .base import BaseStrategy, _calc_atr, calc_shares


class DonchianTurtleStrategy(BaseStrategy):
    name = "donchian_turtle"
    label = "海龟交易"
    description = "20 日新高入场，10 日新低离场，2×ATR 移动止损"
    color = "#fa8c16"

    entry_n: int = 20
    exit_n: int = 10
    atr_n: int = 20
    take_profit: float = 0.25
    stop_loss: float = -0.08
    top_k: int = 5
    price_add: float = 0.005

    _param_meta = {
        "entry_n": {"type": "int", "min": 5, "max": 60, "label": "入场通道"},
        "exit_n": {"type": "int", "min": 3, "max": 30, "label": "离场通道"},
        "atr_n": {"type": "int", "min": 5, "max": 60, "label": "ATR周期"},
        "take_profit": {"type": "float", "min": 0.05, "max": 1.0, "step": 0.01, "label": "止盈线"},
        "stop_loss": {"type": "float", "min": -0.5, "max": -0.01, "step": 0.01, "label": "止损线"},
        "top_k": {"type": "int", "min": 1, "max": 20, "label": "持仓数量"},
        "price_add": {"type": "float", "min": 0, "max": 0.1, "step": 0.001, "label": "调仓滑点"},
    }

    def on_init(self) -> None:
        self.entry_price: dict[str, float] = {}
        self.max_cache: int = max(self.entry_n, self.atr_n) + 2
        self.bar_history: dict[str, list[BarData]] = {}
        self.write_log(f"海龟交易 | entry={self.entry_n} exit={self.exit_n} atr={self.atr_n}")

    def on_bars(self, bars: dict[str, BarData]) -> None:
        # 维护 bar 缓存
        for sym, bar in bars.items():
            if sym not in self.bar_history:
                self.bar_history[sym] = []
            self.bar_history[sym].append(bar)
            if len(self.bar_history[sym]) > self.max_cache:
                self.bar_history[sym] = self.bar_history[sym][-self.max_cache :]

        # ---- 查找突破候选 ----
        candidates: list[tuple[str, float]] = []
        for sym in bars:
            hist = self.bar_history.get(sym, [])
            if len(hist) < self.entry_n + 1:
                continue
            if self.pos_data.get(sym, 0) > 0:
                continue
            close = hist[-1].close_price
            prev_high = max(b.high_price for b in hist[-(self.entry_n + 1) : -1])
            if close <= prev_high:
                continue
            confidence = 70.0
            candidates.append((sym, confidence))

        # ---- 检查持仓退出 ----
        for sym in list(self.pos_data.keys()):
            if self.pos_data[sym] <= 0 or sym not in bars:
                continue
            entry_p = self.entry_price.get(sym)
            hist = self.bar_history.get(sym, [])
            if len(hist) < self.exit_n + 1 or entry_p is None:
                self.target_data[sym] = self.pos_data[sym]
                continue

            close = hist[-1].close_price
            pnl_pct = close / entry_p - 1

            # 止盈/止损
            if pnl_pct >= self.take_profit or pnl_pct <= self.stop_loss:
                self.target_data[sym] = 0.0
                continue

            # 跌破 exit_n 日低点离场
            prev_low = min(b.low_price for b in hist[-(self.exit_n + 1) : -1])
            if close < prev_low:
                self.target_data[sym] = 0.0
                continue

            # 2×ATR 移动止损
            atr_val = _calc_atr(hist, self.atr_n)
            if entry_p - 2 * atr_val > 0 and close < entry_p - 2 * atr_val:
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
