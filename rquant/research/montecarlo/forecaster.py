"""
rquant.research.montecarlo.forecaster — 个股蒙特卡洛路径预测器

来源
----
本文件逻辑 1:1 复刻自 ``FactorQ/src/advisor/montecarlo.py``（2026-06-29 同步），
保留所有 [2026-06-25 修复] 注释（停牌日剔除 / σ 退化保护 / TP-SL 自洽校验）。
如需查阅原始决策背景，请参见 FactorQ 仓库的 commit history。

模型
----
基于几何布朗运动（Geometric Brownian Motion, GBM）：

    简化日频模型（dt=1）：
        P_{t+1} = P_t * exp((mu - sigma^2/2) + sigma * Z_t)
        Z_t ~ N(0, 1)
    一般形式（如果未来要做非日频）：
        P_{t+1} = P_t * exp((mu - sigma^2/2) * dt + sigma * sqrt(dt) * Z_t)

当前用 dt=1（一个交易日），mu/sigma 都是日频 — 等价于一般形式 dt=1。

参数估计
--------
mu, sigma 用最近 ``lookback_days`` 个交易日的**有效**日对数收益率
``ln(P_t / P_{t-1})`` 计算。

- **[2026-06-25 修复]** 排除停牌日（close 与前日相同 OR volume=0），避免 0 收益污染 mean/std。
- **[2026-06-25 修复]** σ 退化保护：如果 σ < 1e-4（年化 < 1.6%）→ 用最小 σ 兜底 + warning。
- **[2026-06-25 修复]** silent fallback 警告：实际 log_rets 数量 < 请求 80% 时给 warning。

输出字段
--------
- ``paths.median / p05 / p25 / p75 / p95``：每个未来时点的分位价格
- ``sample_paths``：前 N 条原始路径（前端画淡线展示）
- ``stats``：

  - ``final_price_*``：最终价分位
  - ``expected_return_pct``：中位预期收益
  - ``prob_higher_pct``：上涨概率
  - ``prob_take_profit_pct``：路径中任意一日 close >= TP 的概率
  - ``prob_stop_loss_pct``：路径中任意一日 close <= SL 的概率
  - ``max_drawdown_median_pct``：中位最大回撤
  - ``max_drawdown_worst_5pct_pct``：5 分位最大回撤（≈ 95% 路径不超过这个回撤）
  - ``first_touch_tp_day_median`` / ``first_touch_sl_day_median``：中位首次触 TP/SL 的天数

- ``history_closes`` / ``history_dates``：最近 60 天收盘价（前端画历史→预测衔接）
- ``warnings``：list[str] — 数据质量/边界警告（前端可展示）

时序严谨性
----------
本模块只用历史 K 线估 mu/sigma，**没有任何 look-ahead**。
输出的是"在历史波动率下，未来 N 天的概率路径分布"——不是预言，是 stress test。

已知模型局限（前端固定风险提示里也应说明）
----------------------------------------------
- GBM 假设价格服从对数正态分布、对数收益独立同分布。
- A 股肥尾、政策冲击、跳空等事件可能让实际尾部风险 > 模型预测。
- 路径中只有"日终价"，没有日内 high/low → 命中 TP/SL 概率基于日终价（实际会更早触发）。
"""

from __future__ import annotations

# isort: off
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
# isort: on


# === 经验阈值（2026-06-25 调试中得出，源自 FactorQ）===
MIN_SIGMA_DAILY = 1e-4  # σ < 1e-4 → 年化 < 1.6%，视为"无波动"退化，用兜底值
SIGMA_FLOOR = 0.005  # σ 退化时兜底为 0.5%/日（年化 ~8%，A 股合理下限）
SUSPENDED_VOL_THRESHOLD = 0  # volume <= 此值视为停牌日
MIN_LOG_RETS = 20  # 有效 log return 至少要 20 条，否则拒绝
LOOKBACK_ADEQUACY_RATIO = 0.8  # 实际样本 / 请求 lookback < 0.8 → warning


@dataclass
class MonteCarloConfig:
    """蒙特卡洛模拟参数"""

    forecast_days: int = 20  # 预测多少个交易日
    simulations: int = 1000  # 模拟次数（路径数）
    lookback_days: int = 252  # 用多少天历史算 mu/sigma（约 1 年）
    take_profit: Optional[float] = None  # 止盈价（None = 不算 TP 命中）
    stop_loss: Optional[float] = None  # 止损价（None = 不算 SL 命中）
    seed: Optional[int] = None  # 随机种子（None = 随机）
    sample_paths: int = 5  # 回传前 N 条样本路径给前端画线


class MonteCarloForecaster:
    """蒙特卡洛股价路径预测器"""

    def __init__(self, config: Optional[MonteCarloConfig] = None):
        self.config = config or MonteCarloConfig()

    def _compute_log_returns(
        self,
        df: pd.DataFrame,
        lookback: int,
    ) -> Tuple[np.ndarray, List[str]]:
        """从 df 取最近 lookback 个交易日的**有效**对数收益率序列（排除停牌日 + NaN）。

        [2026-06-25 修复] 排除停牌日，避免 0 收益污染 mean/std：
            停牌判定：close == close.shift(1) 且 volume <= SUSPENDED_VOL_THRESHOLD
            （A 股停牌日 OHLC 全等于前日 close，volume=0）

        Returns:
            (log_rets, warnings)
        """
        warnings: List[str] = []

        # 取最近 lookback+1 行（+1 是为了算 log return 时最后一个 close 有 prev）
        if len(df) < lookback:
            warnings.append(f"实际可用数据 {len(df)} 天 < 请求 lookback {lookback} 天，自动用全部")
            sub = df.tail(len(df)).copy()
            requested = len(df)
        else:
            sub = df.tail(lookback + 1).copy()
            requested = lookback

        # === 关键修复：排除停牌日 + NaN ===
        close = pd.to_numeric(sub["close"], errors="coerce")
        if "volume" in sub.columns:
            vol = pd.to_numeric(sub["volume"], errors="coerce").fillna(0)
        else:
            vol = pd.Series([0.0] * len(sub))

        # 停牌：close == prev_close 且 volume == 0
        is_suspended = (close == close.shift(1)) & (vol <= SUSPENDED_VOL_THRESHOLD)
        # NaN/Inf close
        invalid = close.isna() | np.isinf(close)
        # 第二个及之后的行才有 log return（第一个没有 prev）
        # 但停牌日和 NaN 都应该排除
        # 注意：停牌的第一个值"接班"位置也排除（因为它和 prev 同，log_rets = 0）

        # 计算 log return
        log_close = np.log(close.to_numpy(dtype=float))  # 用 numpy 避免索引问题
        log_rets_raw = np.diff(log_close)  # shape: (len(sub)-1,)

        # 构造 mask（长度 = len(sub) - 1，对齐 log_rets_raw）
        # suspended_mask[i] 对应 sub.iloc[i+1]（因为 log_rets_raw[i] = log_close[i+1] - log_close[i]）
        suspended_mask = is_suspended.iloc[1:].to_numpy(dtype=bool)
        invalid_mask = invalid.iloc[1:].to_numpy(dtype=bool)
        bad_mask = suspended_mask | invalid_mask

        n_total = len(log_rets_raw)
        n_kept = int((~bad_mask).sum())
        if n_kept < n_total:
            n_dropped = n_total - n_kept
            warnings.append(f"排除 {n_dropped}/{n_total} 条停牌日/无效 close 的 log return（保留 {n_kept} 条）")

        if n_kept == 0:
            warnings.append("lookback 期间全部为停牌日/无效数据，无法估 μ/σ")
            return np.array([]), warnings
        log_rets = log_rets_raw[~bad_mask]
        # 再次过滤：去掉 ±inf（极端值保护）
        finite = np.isfinite(log_rets)
        if not finite.all():
            n_inf = int((~finite).sum())
            warnings.append(f"排除 {n_inf} 条 ±inf log return")
            log_rets = log_rets[finite]

        # 看样本是否充足
        if len(log_rets) < MIN_LOG_RETS:
            return log_rets, warnings

        if len(log_rets) < requested * LOOKBACK_ADEQUACY_RATIO:
            warnings.append(
                f"有效样本 {len(log_rets)} < 请求 lookback {requested} × {LOOKBACK_ADEQUACY_RATIO:.0%}，"
                f"统计估计可能不稳定"
            )

        return log_rets, warnings

    def _percentile_band(self, paths: np.ndarray, q: float, axis: int = 0) -> np.ndarray:
        """按 axis 计算分位"""
        return np.percentile(paths, q * 100, axis=axis)

    def _max_drawdown(self, path: np.ndarray) -> float:
        """单条路径的最大回撤（负值）

        MDD = min_t (P_t / max_{s<=t} P_s - 1)，结果 <= 0
        """
        running_max = np.maximum.accumulate(path)
        # 防止 running_max = 0（边界）
        running_max = np.where(running_max == 0, np.nan, running_max)
        drawdown = path / running_max - 1.0
        return float(np.nanmin(drawdown))

    def _first_touch_day(self, path: np.ndarray, target: float, mode: str) -> Optional[int]:
        """首次触目标价的天数（day index，从 0 起；0 = 当前价）

        mode='gte': 任意一日 close >= target
        mode='lte': 任意一日 close <= target
        返回 None 表示未触发。
        """
        if mode == "gte":
            hits = np.where(path >= target)[0]
        else:
            hits = np.where(path <= target)[0]
        return int(hits[0]) if len(hits) > 0 else None

    def _validate_tp_sl(
        self,
        current_price: float,
        tp: Optional[float],
        sl: Optional[float],
    ) -> Tuple[Optional[float], Optional[float], List[str]]:
        """[2026-06-25 修复] 校验 TP/SL 合理性。

        Returns:
            (tp_clean, sl_clean, warnings)
            - 如果 TP < SL：tp_clean = sl_clean = None（不接受这种输入）
            - 警告保留（前端展示用）
        """
        warnings: List[str] = []

        if tp is not None and sl is not None:
            if tp <= sl:
                warnings.append(f"TP ¥{tp:.2f} ≤ SL ¥{sl:.2f} 逻辑不自洽，已忽略 TP/SL（按当前价 ×1.08 / ×0.96 兜底）")
                return None, None, warnings
            if tp == current_price:
                warnings.append("TP 等于当前价，无意义；保留但 TP 命中概率会很高")
            if sl == current_price:
                warnings.append("SL 等于当前价，无意义；保留但 SL 命中概率会很高")

        return tp, sl, warnings

    def forecast(
        self,
        df: pd.DataFrame,
        current_price: float,
        code: str = "",
        name: str = "",
    ) -> Dict:
        """执行蒙特卡洛预测

        Args:
            df: K 线 DataFrame（必须含 'close' 列，按日期升序；最好带 'volume' 用于停牌日判定）
            current_price: 当前价（用于 GBM 起点，**caller 必须传对**——盘中应该是实时价，不是昨收）
            code, name: 透传给前端

        Returns:
            字典：见模块 docstring
        """
        cfg = self.config
        warnings: List[str] = []

        if current_price <= 0:
            return {
                "error": "current_price 必须 > 0",
                "code": code,
                "name": name,
            }
        if df is None or len(df) < 30:
            return {
                "error": f"数据不足（仅 {0 if df is None else len(df)} 天，至少 30 天）",
                "code": code,
                "name": name,
            }

        # 1) 算 log return 的 mu / sigma（[2026-06-25] 排除停牌日 + warning）
        log_rets, ret_warnings = self._compute_log_returns(df, cfg.lookback_days)
        warnings.extend(ret_warnings)

        if len(log_rets) < MIN_LOG_RETS:
            return {
                "error": f"有效样本不足（{len(log_rets)} 条有效 log return，至少 {MIN_LOG_RETS}）"
                + ("；" + "；".join(warnings) if warnings else ""),
                "code": code,
                "name": name,
                "warnings": warnings,
            }

        mu = float(np.mean(log_rets))
        sigma = float(np.std(log_rets, ddof=1))  # 无偏估计

        # [2026-06-25] σ 退化保护
        sigma_floored = False
        if sigma < MIN_SIGMA_DAILY:
            warnings.append(f"σ={sigma:.6f} 极小（年化 < 1.6%），已用兜底 σ={SIGMA_FLOOR}（年化 ~8%）")
            sigma = SIGMA_FLOOR
            sigma_floored = True
        elif sigma > 0.20:
            warnings.append(f"σ={sigma:.4f} 极大（年化 {sigma * math.sqrt(252) * 100:.0f}%），A 股罕见，请确认数据正确")

        # 2) 年化（仅供参考；GBM 本身用日频 mu/sigma）
        mu_annual = mu * 252
        sigma_annual = sigma * math.sqrt(252)

        # 3) 生成随机路径（dt = 1 个交易日，简化的 GBM）
        rng = np.random.default_rng(cfg.seed)
        Z = rng.standard_normal(size=(cfg.simulations, cfg.forecast_days))
        # 增量 = (mu - sigma^2/2) + sigma * Z
        # 完整公式是 (mu - sigma^2/2) * dt + sigma * sqrt(dt) * Z，dt=1 时等价
        increments = (mu - 0.5 * sigma**2) + sigma * Z
        log_paths = np.cumsum(increments, axis=1)
        # 第一列是 0（当前价）
        log_paths = np.hstack([np.zeros((cfg.simulations, 1)), log_paths])
        paths = current_price * np.exp(log_paths)

        # 4) 分位带
        median = self._percentile_band(paths, 0.5)
        p05 = self._percentile_band(paths, 0.05)
        p25 = self._percentile_band(paths, 0.25)
        p75 = self._percentile_band(paths, 0.75)
        p95 = self._percentile_band(paths, 0.95)

        # 5) 统计
        final_prices = paths[:, -1]
        final_median = float(np.median(final_prices))
        final_p05 = float(np.percentile(final_prices, 5))
        final_p95 = float(np.percentile(final_prices, 95))
        expected_return_pct = (final_median / current_price - 1.0) * 100
        prob_higher = float(np.mean(final_prices > current_price)) * 100

        # TP / SL 命中概率（[2026-06-25] 先校验）
        tp_raw = cfg.take_profit
        sl_raw = cfg.stop_loss
        tp, sl, tp_warnings = self._validate_tp_sl(current_price, tp_raw, sl_raw)
        warnings.extend(tp_warnings)

        prob_tp = None
        prob_sl = None
        if tp is not None and tp > 0:
            hits = (paths >= tp).any(axis=1)
            prob_tp = float(np.mean(hits)) * 100
        if sl is not None and sl > 0:
            hits = (paths <= sl).any(axis=1)
            prob_sl = float(np.mean(hits)) * 100

        # 最大回撤分布
        mdds = np.array([self._max_drawdown(paths[i]) for i in range(cfg.simulations)])
        mdd_median = float(np.median(mdds))
        # 95% 路径不超过的回撤 = 5 分位（更负）
        mdd_worst_5pct = float(np.percentile(mdds, 5))

        # 首次触 TP/SL 的中位天数（仅在触发时计入）
        first_tp_days = []
        first_sl_days = []
        if tp is not None and tp > 0:
            for i in range(cfg.simulations):
                d = self._first_touch_day(paths[i], tp, "gte")
                if d is not None:
                    first_tp_days.append(d)
        if sl is not None and sl > 0:
            for i in range(cfg.simulations):
                d = self._first_touch_day(paths[i], sl, "lte")
                if d is not None:
                    first_sl_days.append(d)
        first_tp_median = float(np.median(first_tp_days)) if first_tp_days else None
        first_sl_median = float(np.median(first_sl_days)) if first_sl_days else None

        # 6) 样本路径
        n_samples = min(cfg.sample_paths, cfg.simulations)
        sample_paths = [{"id": int(i + 1), "prices": [round(float(p), 4) for p in paths[i]]} for i in range(n_samples)]

        # 7) 历史段（给前端画历史 60 天 → 当前价的衔接）
        hist_n = min(60, len(df))
        hist_df = df.tail(hist_n)
        history_closes = [round(float(p), 4) for p in hist_df["close"].to_numpy()]
        history_dates = [d.strftime("%m-%d") for d in pd.to_datetime(hist_df["date"])]

        # 8) TP/SL 兜底（前端要展示横线）
        if tp is None or tp <= 0:
            tp = round(current_price * 1.08, 2)
        if sl is None or sl <= 0:
            sl = round(current_price * 0.96, 2)

        return {
            "code": code,
            "name": name,
            "current_price": round(float(current_price), 4),
            "last_date": pd.to_datetime(df["date"].iloc[-1]).strftime("%Y-%m-%d"),
            "lookback_days_used": len(log_rets),
            "forecast_days": cfg.forecast_days,
            "simulations": cfg.simulations,
            "mu_daily": round(mu, 6),
            "sigma_daily": round(sigma, 6),
            "sigma_floored": sigma_floored,  # [2026-06-25] 前端可识别"用了兜底 σ"
            "mu_annualized": round(mu_annual, 4),
            "sigma_annualized": round(sigma_annual, 4),
            "take_profit": round(float(tp), 4),
            "stop_loss": round(float(sl), 4),
            "paths": {
                "median": [round(float(p), 4) for p in median],
                "p05": [round(float(p), 4) for p in p05],
                "p25": [round(float(p), 4) for p in p25],
                "p75": [round(float(p), 4) for p in p75],
                "p95": [round(float(p), 4) for p in p95],
            },
            "sample_paths": sample_paths,
            "history_closes": history_closes,
            "history_dates": history_dates,
            "warnings": warnings,  # [2026-06-25] 数据质量/边界警告
            "stats": {
                "final_price_median": round(final_median, 4),
                "final_price_p05": round(final_p05, 4),
                "final_price_p95": round(final_p95, 4),
                "expected_return_pct": round(expected_return_pct, 2),
                "prob_higher_pct": round(prob_higher, 2),
                "prob_take_profit_pct": round(prob_tp, 2) if prob_tp is not None else None,
                "prob_stop_loss_pct": round(prob_sl, 2) if prob_sl is not None else None,
                "max_drawdown_median_pct": round(mdd_median * 100, 2),
                # [2026-06-25] 更明确命名（之前 max_drawdown_p95_pct 容易误读）
                "max_drawdown_worst_5pct_pct": round(mdd_worst_5pct * 100, 2),
                "first_touch_tp_day_median": (int(first_tp_median) if first_tp_median is not None else None),
                "first_touch_sl_day_median": (int(first_sl_median) if first_sl_median is not None else None),
            },
        }


def run_forecast(
    df: pd.DataFrame,
    current_price: float,
    forecast_days: int = 20,
    simulations: int = 1000,
    lookback_days: int = 252,
    take_profit: Optional[float] = None,
    stop_loss: Optional[float] = None,
    seed: Optional[int] = None,
    code: str = "",
    name: str = "",
) -> Dict:
    """便捷函数：直接跑预测"""
    cfg = MonteCarloConfig(
        forecast_days=forecast_days,
        simulations=simulations,
        lookback_days=lookback_days,
        take_profit=take_profit,
        stop_loss=stop_loss,
        seed=seed,
    )
    return MonteCarloForecaster(cfg).forecast(df, current_price, code=code, name=name)
