"""
共享技术指标 —— 所有策略子类可直接引用，避免跨文件重复定义。

提供：
    ma_from_bars(hist, n)  — N 日均价
    calc_rsi(hist, n)      — 简单 RSI（SMA 平滑）
    calc_atr(hist, n)      — Average True Range
"""

from __future__ import annotations


def ma_from_bars(hist: list, n: int) -> float:
    """N 日收盘均价，基于 BarData 列表。

    数据不足 N 根时返回最新收盘价。
    """
    if len(hist) < n:
        return float(hist[-1].close_price)
    return float(sum(b.close_price for b in hist[-n:]) / n)


def calc_rsi(hist: list, n: int = 14) -> float:
    """简单 RSI(N)，基于 SMA 平滑（非 Wilder 指数平滑）。

    数据不足时返回 50.0（中性）。
    """
    if len(hist) < n + 1:
        return 50.0
    closes = [b.close_price for b in hist[-(n + 1) :]]
    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(diff if diff > 0 else 0.0)
        losses.append(-diff if diff < 0 else 0.0)
    avg_gain = sum(gains) / len(gains)
    avg_loss = sum(losses) / len(losses)
    if avg_loss == 0:
        return 100.0
    return float(100 - 100 / (1 + avg_gain / avg_loss))


def calc_atr(hist: list, n: int) -> float:
    """ATR(N) —— Average True Range。

    基于最近 N 根 K 线的 True Range 简单平均。
    数据不足时返回 0.0。
    """
    if len(hist) < n + 1:
        return 0.0
    tr_values: list[float] = []
    recent = hist[-n:]
    prev_close = hist[-(n + 1)].close_price
    for b in recent:
        tr = max(
            b.high_price - b.low_price,
            abs(b.high_price - prev_close),
            abs(b.low_price - prev_close),
        )
        tr_values.append(tr)
        prev_close = b.close_price
    return float(sum(tr_values) / len(tr_values)) if tr_values else 0.0
