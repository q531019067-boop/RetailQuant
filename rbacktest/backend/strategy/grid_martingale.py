"""
网格马丁格尔策略 —— 每日计算滚动网格，低位买入 / 高位止盈或破网止损。
"""

from vnpy.trader.constant import Direction
from vnpy.trader.object import TradeData, BarData

from .base import BaseStrategy, calc_shares


class GridMartingaleStrategy(BaseStrategy):
    name = "grid_martingale"
    label = "网格马丁格尔"
    description = "每日计算网格位置，低位买入 / 高位卖出"
    color = "#1890ff"

    grid_n: int = 10
    top_k: int = 5
    break_stop_pct: float = 0.05
    take_profit_ratio: float = 0.75
    price_add: float = 0.02

    _param_meta = {
        "grid_n": {"type": "int", "min": 5, "max": 60, "label": "网格K线数"},
        "top_k": {"type": "int", "min": 1, "max": 30, "label": "持仓数量"},
        "break_stop_pct": {"type": "float", "min": 0.01, "max": 0.3, "step": 0.01, "label": "破网止损比例"},
        "take_profit_ratio": {"type": "float", "min": 0.5, "max": 0.95, "step": 0.05, "label": "止盈位置比"},
        "price_add": {"type": "float", "min": 0, "max": 0.1, "step": 0.001, "label": "调仓滑点"},
    }

    def on_init(self) -> None:
        self.entry_price: dict[str, float] = {}
        self.bar_cache: dict[str, list[BarData]] = {}
        self.pending_sells: set[str] = set()
        self.write_log(f"网格马丁格尔 | top_k={self.top_k} grid_n={self.grid_n}")

    def on_bars(self, bars: dict[str, BarData]) -> None:
        """每日扫描：在滚动网格低位买入，高位止盈或破网止损卖出。

        网格逻辑：
            - 用最近 grid_n 根 K 线的高/低价作为网格上下界
            - position = (close - grid_low) / (grid_high - grid_low)，范围 0~1
            - position ≤ 0.45 → 低位，买入候选（越接近 0 置信度越高）
            - break_stop_pct → 跌破网格下界一定比例 → 止损
            - take_profit_ratio → 回升到网格上界一定比例 → 止盈
        """
        # 维护 bar 缓存（滑动窗口，只保留 grid_n+1 根）
        for sym, bar in bars.items():
            if sym not in self.bar_cache:
                self.bar_cache[sym] = []
            self.bar_cache[sym].append(bar)
            if len(self.bar_cache[sym]) > self.grid_n + 1:
                self.bar_cache[sym] = self.bar_cache[sym][-(self.grid_n + 1) :]

        # 查找买入候选
        candidates: list[tuple[str, float, float]] = []
        for sym in bars:
            hist = self.bar_cache.get(sym, [])
            if len(hist) < self.grid_n + 1:
                continue
            recent = hist[-(self.grid_n + 1) : -1]
            grid_high = max(b.high_price for b in recent)
            grid_low = min(b.low_price for b in recent)
            close = hist[-1].close_price
            if grid_high <= grid_low:
                continue
            ratio = (close - grid_low) / (grid_high - grid_low)
            if not (0 <= ratio <= 0.45):
                continue
            confidence = max(40.0, 70.0 - ratio * 100.0)
            candidates.append((sym, ratio, confidence))

        # 检查持仓卖出条件
        for sym in [s for s, p in self.pos_data.items() if p > 0]:
            if sym not in bars:
                continue
            hist = self.bar_cache.get(sym, [])
            if len(hist) < self.grid_n + 1:
                continue
            recent = hist[-(self.grid_n + 1) : -1]
            grid_high = max(b.high_price for b in recent)
            grid_low = min(b.low_price for b in recent)
            close = hist[-1].close_price
            if grid_high <= grid_low:
                continue
            ratio = (close - grid_low) / (grid_high - grid_low)
            break_price = grid_low * (1.0 - self.break_stop_pct)

            should_sell = close <= break_price
            if not should_sell:
                entry_p = self.entry_price.get(sym)
                if ratio >= self.take_profit_ratio and entry_p and close > entry_p:
                    should_sell = True

            if should_sell and sym not in self.pending_sells:
                pos = self.pos_data.get(sym, 0)
                if pos > 0:
                    self.pending_sells.add(sym)
                    sell_price = bars[sym].close_price * (1 - self.price_add)
                    self.sell(sym, sell_price, pos)

        # 新建仓位
        candidates.sort(key=lambda x: x[2], reverse=True)
        selected = candidates[: self.top_k]
        if selected:
            cash = self.get_cash_available()
            per = cash / len(selected)
            for sym, _, _ in selected:
                bar = bars.get(sym)
                if bar is None or bar.close_price <= 0:
                    continue
                price = bar.close_price * (1 + self.price_add)
                shares = calc_shares(per, price)
                if shares > 0:
                    self.buy(sym, price, shares)

    def on_trade(self, trade: TradeData) -> None:
        if trade.direction == Direction.LONG:
            cur = self.entry_price.get(trade.vt_symbol)
            pos = self.pos_data.get(trade.vt_symbol, 0)
            if cur is None or pos - trade.volume <= 0:
                self.entry_price[trade.vt_symbol] = trade.price
            else:
                old_size = max(0.0, pos - trade.volume)
                self.entry_price[trade.vt_symbol] = (old_size * cur + trade.volume * trade.price) / pos
        else:
            self.pending_sells.discard(trade.vt_symbol)
            if self.pos_data.get(trade.vt_symbol, 0) <= 0:
                self.entry_price.pop(trade.vt_symbol, None)
