"""
低吸策略 —— 超跌 + 超卖 + 缩量 + 止跌 四重确认的买入信号。
站上 MA60 或止盈/止损时卖出。
"""

from vnpy.trader.constant import Direction
from vnpy.trader.object import TradeData, BarData

from .base import BaseStrategy, _calc_rsi, _ma_from_bars, calc_shares


class BuyHoldStrategy(BaseStrategy):
    name = "buy_hold"
    label = "低吸策略"
    description = "超跌+超卖+缩量+止跌四重确认，站上MA60离场"
    color = "#13c2c2"

    drop_lookback: int = 20
    drop_threshold: float = -10.0
    ma_n: int = 60
    ma_drop_min: float = -35.0
    ma_drop_max: float = -5.0
    rsi_buy: float = 30.0
    vol_shrink_ratio: float = 0.7
    take_profit: float = 0.20
    stop_loss: float = -0.10
    top_k: int = 5
    price_add: float = 0.005

    _param_meta = {
        "drop_lookback": {"type": "int", "min": 10, "max": 60, "label": "跌幅回顾天数"},
        "drop_threshold": {"type": "float", "min": -50, "max": -3, "step": 1, "label": "跌幅阈值(%)"},
        "ma_n": {"type": "int", "min": 20, "max": 120, "label": "均线周期"},
        "ma_drop_min": {"type": "float", "min": -60, "max": -10, "step": 1, "label": "MA下方最远(%)"},
        "ma_drop_max": {"type": "float", "min": -15, "max": 0, "step": 1, "label": "MA下方最近(%)"},
        "rsi_buy": {"type": "float", "min": 15, "max": 40, "step": 1, "label": "RSI买入阈值"},
        "vol_shrink_ratio": {"type": "float", "min": 0.3, "max": 1.0, "step": 0.05, "label": "缩量比例"},
        "take_profit": {"type": "float", "min": 0.05, "max": 0.5, "step": 0.01, "label": "止盈线"},
        "stop_loss": {"type": "float", "min": -0.3, "max": -0.03, "step": 0.01, "label": "止损线"},
        "top_k": {"type": "int", "min": 1, "max": 20, "label": "持仓数量"},
        "price_add": {"type": "float", "min": 0, "max": 0.1, "step": 0.001, "label": "调仓滑点"},
    }

    def on_init(self) -> None:
        self.entry_price: dict[str, float] = {}
        max_need = max(self.drop_lookback, self.ma_n) + 5
        self.max_cache: int = max_need
        self.bar_history: dict[str, list[BarData]] = {}
        self.write_log(f"低吸策略 | drop>{abs(self.drop_threshold)}% RSI<{self.rsi_buy}")

    def on_bars(self, bars: dict[str, BarData]) -> None:
        # 维护 bar 缓存
        for sym, bar in bars.items():
            if sym not in self.bar_history:
                self.bar_history[sym] = []
            self.bar_history[sym].append(bar)
            if len(self.bar_history[sym]) > self.max_cache:
                self.bar_history[sym] = self.bar_history[sym][-self.max_cache :]

        # ---- 查找低吸候选 ----
        candidates: list[tuple[str, float]] = []
        for sym in bars:
            hist = self.bar_history.get(sym, [])
            if len(hist) < self.ma_n + 5:
                continue
            if self.pos_data.get(sym, 0) > 0:
                continue

            close = hist[-1].close_price
            open_today = hist[-1].open_price
            prev_close = hist[-2].close_price

            # 1. 跌幅过滤
            if len(hist) < self.drop_lookback + 1:
                continue
            chg_20d = (close / hist[-(self.drop_lookback + 1)].close_price - 1) * 100
            if chg_20d > self.drop_threshold:
                continue

            # 2. MA 距离
            ma_val = _ma_from_bars(hist, self.ma_n)
            if ma_val <= 0:
                continue
            drop_to_ma = (close / ma_val - 1) * 100
            if drop_to_ma > self.ma_drop_max or drop_to_ma < self.ma_drop_min:
                continue

            # 3. RSI 超卖
            rsi_val = _calc_rsi(hist, 14)
            if rsi_val >= self.rsi_buy:
                continue

            # 4. 缩量
            vol_3avg = sum(b.volume for b in hist[-3:]) / 3
            vol_20avg = sum(b.volume for b in hist[-20:]) / 20
            if vol_20avg <= 0 or vol_3avg > vol_20avg * self.vol_shrink_ratio:
                continue

            # 5. 当日止跌（反弹）
            if close <= open_today or close <= prev_close:
                continue

            # 6. 最近 3 日至少有 1 根阴线
            recent_3 = hist[-3:]
            has_bear = any(b.close_price < b.open_price for b in recent_3)
            if not has_bear:
                continue

            # 信心度
            drop_score = min(15.0, abs(chg_20d) - abs(self.drop_threshold))
            rsi_score = min(10.0, max(0.0, self.rsi_buy - rsi_val))
            vol_shrink = vol_3avg / vol_20avg if vol_20avg > 0 else 1.0
            shrink_score = min(10.0, max(0.0, (self.vol_shrink_ratio - vol_shrink) * 30))
            confidence = min(85.0, 50.0 + drop_score + rsi_score + shrink_score)
            candidates.append((sym, confidence))

        # ---- 检查持仓退出 ----
        for sym in list(self.pos_data.keys()):
            if self.pos_data[sym] <= 0 or sym not in bars:
                continue
            entry_p = self.entry_price.get(sym)
            hist = self.bar_history.get(sym, [])
            if len(hist) < self.ma_n or entry_p is None:
                self.target_data[sym] = self.pos_data[sym]
                continue

            close = hist[-1].close_price
            pnl_pct = close / entry_p - 1
            ma_val = _ma_from_bars(hist, self.ma_n)

            if pnl_pct >= self.take_profit:
                self.target_data[sym] = 0.0
                continue
            if pnl_pct <= self.stop_loss:
                self.target_data[sym] = 0.0
                continue
            # 站上 MA60 → 低吸目标达成
            if close > ma_val * 1.05:
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
