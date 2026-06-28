"""rquant.research.montecarlo — 个股蒙特卡洛路径预测工具库。

来源说明
--------
本包是从 ``FactorQ/src/advisor/montecarlo.py`` 复刻而来（2026-06-29）。
复刻时保留了原实现的全部核心逻辑（GBM 模型、停牌日剔除、σ 退化保护、
TP/SL 自洽校验、MDD 统计、warnings 上报），仅做了以下调整：

1. **路径变更**：从 ``src/advisor/montecarlo.py`` → ``rquant/research/montecarlo/``
2. **依赖剥除**：移除原 ``__main__`` 块中对 FactorQ ``OnDemandAnalyzer`` 的依赖，
   改写为 ``cli.py``，使用 RetailQuant 自身的 ``rquant.business.data.fetch_kline``。
3. **作为工具库**：

   - 不注册任何路由、不写前端；
   - 不动 ``rquant/__init__.py`` 顶层导出（避免影响现有 import）；
   - 不动 ``web/routes.py`` / ``templates`` / ``static``；
   - 任何上层（CLI、Flask route、Jupyter、单元测试）都可以
     ``from rquant.research.montecarlo import run_forecast`` 直接调用。

接口
----
::

    from rquant.research.montecarlo import run_forecast, MonteCarloConfig, MonteCarloForecaster

    out = run_forecast(
        df=kline_df,                # 必须含 date, close, volume 列（按日期升序）
        current_price=12.34,        # 当前价（盘中应传实时价，不是昨收）
        forecast_days=20,           # 预测多少个交易日
        simulations=1000,           # 模拟路径数
        lookback_days=252,          # 用多少天历史估 μ/σ
        take_profit=13.32,          # 止盈价（可选）
        stop_loss=11.85,            # 止损价（可选）
        seed=42,                    # 随机种子（可选）
        code="sh600000",
        name="浦发银行",
    )

数据要求
--------
- ``df`` 是 pandas.DataFrame，列至少包含 ``date`` / ``close`` / ``volume``，按日期升序。
- ``current_price > 0``，且 caller 自行保证是"as-of 当前"的真实价（盘中应为实时价）。
- 至少 30 天 K 线（库内会校验更严格的 20 条有效 log return）。

时序严谨性
----------
本库只用历史 K 线估 μ/σ，**没有任何 look-ahead**。
输出是"在历史波动率下，未来 N 天的概率路径分布"——不是预言，是 stress test。

已知模型局限
------------
- GBM 假设价格服从对数正态分布、对数收益独立同分布。
- A 股肥尾、政策冲击、跳空等事件可能让实际尾部风险 > 模型预测。
- 路径只有"日终价"，没有日内 high/low → 命中 TP/SL 概率基于日终价（实际会更早触发）。

详细字段说明见 ``forecaster.py`` 模块 docstring。
"""

from .forecaster import (
    LOOKBACK_ADEQUACY_RATIO,
    MIN_LOG_RETS,
    MIN_SIGMA_DAILY,
    SIGMA_FLOOR,
    SUSPENDED_VOL_THRESHOLD,
    MonteCarloConfig,
    MonteCarloForecaster,
    run_forecast,
)

__all__ = [
    "LOOKBACK_ADEQUACY_RATIO",
    "MIN_LOG_RETS",
    "MIN_SIGMA_DAILY",
    "SIGMA_FLOOR",
    "SUSPENDED_VOL_THRESHOLD",
    "MonteCarloConfig",
    "MonteCarloForecaster",
    "run_forecast",
]
