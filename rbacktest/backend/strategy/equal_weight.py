"""
动量轮动策略 —— 每月初按过去 lookback 日收益率排序，等权持有前 top_k 只。
"""

from vnpy.trader.object import TradeData, BarData

from .base import BaseStrategy, calc_shares


class EqualWeightStrategy(BaseStrategy):
    name = "equal_weight"
    label = "动量轮动"
    description = "每月初按过去 lookback 日收益率排序，等权持有前 top_k 只"
    color = "#cf1322"

    top_k: int = 3
    lookback: int = 20
    price_add: float = 0.01

    _param_meta = {
        "top_k": {"type": "int", "min": 1, "max": 20, "label": "持仓数量"},
        "lookback": {"type": "int", "min": 5, "max": 120, "label": "回顾天数"},
        "price_add": {"type": "float", "min": 0, "max": 0.1, "step": 0.001, "label": "调仓滑点"},
    }

    def on_init(self) -> None:
        self.bar_history: dict[str, list[BarData]] = {}
        self.write_log(f"动量轮动 | top_k={self.top_k} lookback={self.lookback}")

    def on_bars(self, bars: dict[str, BarData]) -> None:
        """月度调仓：每月前 5 个交易日内，按 lookback 收益率排序，等权持有 top_k。

        卖出：将所有持仓 target 设为 0，引擎自动清仓。
        买入：对每个入选标的，分配 total_value / len(selected) 资金。
        """
        # 累积 bar 历史（滑动窗口，只保留 lookback+2 根 K 线）
        for sym, bar in bars.items():
            if sym not in self.bar_history:
                self.bar_history[sym] = []
            self.bar_history[sym].append(bar)
            if len(self.bar_history[sym]) > self.lookback + 2:
                self.bar_history[sym] = self.bar_history[sym][-(self.lookback + 2) :]

        dt = next(iter(bars.values())).datetime if bars else None
        if dt is None or dt.day > 5:
            return

        # 按 lookback 收益率打分
        scored: list[tuple[str, float]] = []
        for sym in self.vt_symbols:
            hist = self.bar_history.get(sym, [])
            if len(hist) < self.lookback + 1:
                continue
            past_close = hist[-(self.lookback + 1)].close_price
            if past_close <= 0:
                continue
            ret = hist[-1].close_price / past_close - 1
            scored.append((sym, ret))

        scored.sort(key=lambda x: x[1], reverse=True)
        selected = scored[: self.top_k]

        for s in self.vt_symbols:
            self.target_data[s] = 0.0

        if not selected:
            return

        total_value: float = self.get_cash_available()
        for bar in bars.values():
            pos = self.pos_data.get(bar.vt_symbol, 0)
            if pos > 0:
                total_value += pos * bar.close_price

        per_stock = total_value / len(selected)

        for sym, _ in selected:
            bar = bars.get(sym)
            if bar is None or bar.close_price <= 0:
                continue
            self.target_data[sym] = calc_shares(per_stock, bar.close_price)

        self.execute_trading(bars, self.price_add)

    def on_trade(self, trade: TradeData) -> None:
        pass
