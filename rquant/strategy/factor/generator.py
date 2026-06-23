"""
rquant.strategy.factor.generator — 因子生成与特征工程接口。

输入标准 OHLCV/Amount DataFrame，输出与原始索引对齐的因子矩阵。
第一版聚焦可解释、可回测的基础量价因子。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal

import pandas as pd

FillMethod = Literal["none", "ffill", "bfill", "zero", "median"]


@dataclass(frozen=True)
class FactorConfig:
    """因子生成参数。"""

    windows: tuple[int, ...] = (5, 20, 60)
    min_periods: int | None = None
    annualization: int = 250
    fill_method: FillMethod = "ffill"
    winsor_limits: tuple[float, float] | None = (0.01, 0.99)
    dropna: bool = False


def generate_factors(
    df: pd.DataFrame,
    config: FactorConfig | None = None,
    windows: Iterable[int] | None = None,
    fill_method: FillMethod | None = None,
    winsor_limits: tuple[float, float] | None | object = ...,
    dropna: bool | None = None,
) -> pd.DataFrame:
    """生成基础动量、波动率与量价相关因子。

    参数既支持传入 `FactorConfig`，也支持直接覆盖常用字段，便于脚本调用。
    """
    cfg = config or FactorConfig()
    if windows is not None:
        cfg = FactorConfig(
            windows=tuple(windows),
            min_periods=cfg.min_periods,
            annualization=cfg.annualization,
            fill_method=cfg.fill_method,
            winsor_limits=cfg.winsor_limits,
            dropna=cfg.dropna,
        )
    if fill_method is not None:
        cfg = FactorConfig(
            windows=cfg.windows,
            min_periods=cfg.min_periods,
            annualization=cfg.annualization,
            fill_method=fill_method,
            winsor_limits=cfg.winsor_limits,
            dropna=cfg.dropna,
        )
    if winsor_limits is not ...:
        cfg = FactorConfig(
            windows=cfg.windows,
            min_periods=cfg.min_periods,
            annualization=cfg.annualization,
            fill_method=cfg.fill_method,
            winsor_limits=winsor_limits,  # type: ignore[arg-type]
            dropna=cfg.dropna,
        )
    if dropna is not None:
        cfg = FactorConfig(
            windows=cfg.windows,
            min_periods=cfg.min_periods,
            annualization=cfg.annualization,
            fill_method=cfg.fill_method,
            winsor_limits=cfg.winsor_limits,
            dropna=dropna,
        )

    data = _prepare_ohlcva(df)
    result = pd.DataFrame(index=data.index)
    close = data["close"]
    amount = data["amount"]
    returns = close.pct_change()
    amount_change = amount.pct_change()

    for n in cfg.windows:
        min_periods = cfg.min_periods or n
        result[f"ret_{n}d"] = close / close.shift(n) - 1
        result[f"vol_{n}d_ann"] = returns.rolling(n, min_periods=min_periods).std() * (cfg.annualization**0.5)
        result[f"pv_corr_{n}d"] = returns.rolling(n, min_periods=min_periods).corr(amount_change)

    result = _winsorize(result, cfg.winsor_limits)
    result = _fill_missing(result, cfg.fill_method)
    if cfg.dropna:
        result = result.dropna()
    return result


def momentum_factor(df: pd.DataFrame, n: int = 20) -> pd.Series:
    data = _prepare_ohlcva(df)
    return data["close"] / data["close"].shift(n) - 1


def annualized_volatility_factor(df: pd.DataFrame, n: int = 20, annualization: int = 250) -> pd.Series:
    data = _prepare_ohlcva(df)
    return data["close"].pct_change().rolling(n, min_periods=n).std() * (annualization**0.5)


def price_volume_corr_factor(df: pd.DataFrame, n: int = 20) -> pd.Series:
    data = _prepare_ohlcva(df)
    returns = data["close"].pct_change()
    amount_change = data["amount"].pct_change()
    return returns.rolling(n, min_periods=n).corr(amount_change)


def _prepare_ohlcva(df: pd.DataFrame) -> pd.DataFrame:
    required = {"open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"行情数据缺少必要列: {sorted(missing)}")

    data = df.copy()
    for col in ("open", "high", "low", "close", "volume"):
        data[col] = pd.to_numeric(data[col], errors="coerce")
    if "amount" not in data.columns:
        data["amount"] = data["close"] * data["volume"]
    else:
        data["amount"] = pd.to_numeric(data["amount"], errors="coerce")
        fallback = data["close"] * data["volume"]
        data["amount"] = data["amount"].where(data["amount"] > 0, fallback)
    return data


def _winsorize(df: pd.DataFrame, limits: tuple[float, float] | None) -> pd.DataFrame:
    if limits is None:
        return df
    lo, hi = limits
    if not 0 <= lo <= hi <= 1:
        raise ValueError("winsor_limits 必须满足 0 <= low <= high <= 1")
    result = df.copy()
    for col in result.columns:
        lower = result[col].quantile(lo)
        upper = result[col].quantile(hi)
        result[col] = result[col].clip(lower=lower, upper=upper)
    return result


def _fill_missing(df: pd.DataFrame, method: FillMethod) -> pd.DataFrame:
    if method == "none":
        return df
    if method == "ffill":
        return df.ffill()
    if method == "bfill":
        return df.bfill()
    if method == "zero":
        return df.fillna(0.0)
    if method == "median":
        return df.fillna(df.median(numeric_only=True))
    raise ValueError(f"未知缺失值处理方式: {method}")
