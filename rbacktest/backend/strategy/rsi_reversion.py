"""
RSI 均值回归策略 —— RSI(14) 超卖反弹，MA200 趋势过滤，ATR 风险控制。
"""

from vnpy.trader.constant import Direction
from vnpy.trader.object import TradeData, BarData

from .base import BaseStrategy, _calc_atr, _calc_rsi, _ma_from_bars, calc_shares


class RsiMeanReversionStrategy(BaseStrategy):
    name = "rsi_reversion"
    label = "RSI回归"
    description = "RSI(14)超卖反弹 + MA200趋势过滤 + ATR仓位控制"
    color = "#eb2f96"

    rsi_n: int = 14
    rsi_buy: float = 30.0
    rsi_sell: float = 70.0
    trend_ma_n: int = 200
    atr_n: int = 14
    stop_atr: float = 2.0
    max_hold_days: int = 20
    cash_pct: float = 0.60
    top_k: int = 5
    price_add: float = 0.005

    _param_meta = {
        "rsi_n": {"type": "int", "min": 5, "max": 30, "label": "RSI周期"},
        "rsi_buy": {"type": "float", "min": 15, "max": 40, "step": 1, "label": "RSI买入阈值"},
        "rsi_sell": {"type": "float", "min": 60, "max": 85, "step": 1, "label": "RSI卖出阈值"},
        "trend_ma_n": {"type": "int", "min": 50, "max": 300, "label": "趋势MA周期"},
        "atr_n": {"type": "int", "min": 5, "max": 30, "label": "ATR周期"},
        "stop_atr": {"type": "float", "min": 1.0, "max": 4.0, "step": 0.5, "label": "ATR止损倍数"},
        "max_hold_days": {"type": "int", "min": 5, "max": 60, "label": "最长持仓天数"},
        "cash_pct": {"type": "float", "min": 0.1, "max": 1.0, "step": 0.05, "label": "仓位比例"},
        "top_k": {"type": "int", "min": 1, "max": 20, "label": "持仓数量"},
        "price_add": {"type": "float", "min": 0, "max": 0.1, "step": 0.001, "label": "调仓滑点"},
    }

    def on_init(self) -> None:
        self.entry_price: dict[str, float] = {}
        self.hold_since: dict[str, int] = {}  # symbol → 持仓起始 bar index
        self.bar_count: int = 0
        self.max_cache: int = max(self.trend_ma_n, self.rsi_n, self.atr_n) + 2
        self.write_log(f"RSI回归 | RSI{self.rsi_n}<{self.rsi_buy} 趋势MA{self.trend_ma_n}")

    def on_bars(self, bars: dict[str, BarData]) -> None:
        self.bar_count += 1

        self._maintain_bars(bars)

        # ---- 查找 RSI 超卖候选 ----
        candidates: list[tuple[str, float]] = []
        for sym in bars:
            hist = self.bar_history.get(sym, [])
            if len(hist) < self.trend_ma_n + 1:
                continue
            if self.pos_data.get(sym, 0) > 0:
                continue

            rsi_val = _calc_rsi(hist, self.rsi_n)
            if rsi_val >= self.rsi_buy:
                continue

            close = hist[-1].close_price
            ma_trend = _ma_from_bars(hist, self.trend_ma_n)
            atr_val = _calc_atr(hist, self.atr_n)

            # 趋势过滤：价格在 MA 上方或附近（不超过 1.5×ATR 下方）
            if close < ma_trend - 1.5 * atr_val:
                continue

            confidence = min(90.0, 62.0 + (self.rsi_buy - rsi_val))
            candidates.append((sym, confidence))

        # ---- 检查持仓退出 ----
        for sym in list(self.pos_data.keys()):
            if self.pos_data[sym] <= 0 or sym not in bars:
                continue
            entry_p = self.entry_price.get(sym)
            hist = self.bar_history.get(sym, [])
            if len(hist) < self.rsi_n + 1 or entry_p is None:
                self.target_data[sym] = self.pos_data[sym]
                continue

            close = hist[-1].close_price
            pnl_pct = close / entry_p - 1
            rsi_val = _calc_rsi(hist, self.rsi_n)
            atr_val = _calc_atr(hist, self.atr_n)

            # ATR 止损
            stop_price = entry_p - self.stop_atr * atr_val
            if close <= stop_price:
                self.target_data[sym] = 0.0
                continue

            # RSI 超买退出
            if rsi_val >= self.rsi_sell and pnl_pct > 0:
                self.target_data[sym] = 0.0
                continue

            # 时间止损
            hold_start = self.hold_since.get(sym, self.bar_count)
            if self.bar_count - hold_start >= self.max_hold_days:
                self.target_data[sym] = 0.0
                continue

            self.target_data[sym] = self.pos_data[sym]

        self.execute_trading(bars, self.price_add)

        # ---- 新建仓位 ----
        candidates.sort(key=lambda x: x[1], reverse=True)
        selected = candidates[: self.top_k]
        if selected:
            cash = self.get_cash_available() * self.cash_pct
            per = cash / len(selected)
            for sym, _ in selected:
                if sym not in bars:
                    continue
                price = bars[sym].close_price * (1 + self.price_add)
                shares = calc_shares(per, price)
                if shares > 0:
                    self.buy(sym, price, shares)
                    self.hold_since[sym] = self.bar_count

    def on_trade(self, trade: TradeData) -> None:
        self._update_entry_price(trade)
        if trade.direction == Direction.SHORT and self.pos_data.get(trade.vt_symbol, 0) <= 0:
            self.hold_since.pop(trade.vt_symbol, None)
