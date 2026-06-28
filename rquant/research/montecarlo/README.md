# rquant.research.montecarlo

个股蒙特卡洛路径预测工具库 — 从 FactorQ `src/advisor/montecarlo.py` 复刻而来。

## 状态

- **来源**：1:1 复刻自 [FactorQ](https://github.com/.../FactorQ) `src/advisor/montecarlo.py`（2026-06-29 同步），保留全部核心逻辑与 [2026-06-25] 修复注释。
- **剥离依赖**：原 `__main__` 块依赖 FactorQ 的 `OnDemandAnalyzer`，本包已替换为 `cli.py`，走 `rquant.business.data.fetch_kline`。
- **不触碰**：`rquant/__init__.py` 顶层导出、`web/routes.py`、`templates/`、`static/`、现有 `scripts/`。
- **前端**：暂时不接。如果以后要接，自行在 routes.py 加一个 `/api/montecarlo/<code>` 即可。

## 公开 API

```python
from rquant.research.montecarlo import (
    MonteCarloConfig,
    MonteCarloForecaster,
    run_forecast,
    MIN_LOG_RETS,
    MIN_SIGMA_DAILY,
    SIGMA_FLOOR,
)
```

## 最小用法（库调用）

```python
import pandas as pd
from rquant.business.data import fetch_kline
from rquant.research.montecarlo import run_forecast

df = fetch_kline("sh600000", 400)        # DataFrame: date, open, high, low, close, volume
current_price = float(df["close"].iloc[-1])

out = run_forecast(
    df=df,
    current_price=current_price,
    forecast_days=20,
    simulations=1000,
    lookback_days=252,
    take_profit=round(current_price * 1.08, 2),
    stop_loss=round(current_price * 0.96, 2),
    seed=42,
    code="sh600000",
    name="浦发银行",
)

# out 是 dict，字段见 forecaster.py 模块 docstring
print(out["stats"]["expected_return_pct"], out["stats"]["prob_higher_pct"])
```

## 命令行（独立跑，不依赖 web）

```bash
python -m rquant.research.montecarlo.cli sh600000
python -m rquant.research.montecarlo.cli sh600000 --days 40 --sims 2000 --json
python -m rquant.research.montecarlo.cli sh600000 --tp 13.5 --sl 11.8
python -m rquant.research.montecarlo.cli sh600000 --live-price 12.40  # 盘中实时价
```

## 输出字段（`out`）

| 字段 | 类型 | 说明 |
|------|------|------|
| `code` / `name` | str | 透传 |
| `current_price` | float | GBM 起点（caller 决定） |
| `last_date` | str (YYYY-MM-DD) | K 线末日 |
| `lookback_days_used` | int | 实际用了多少条 log return（剔停牌后） |
| `mu_daily` / `sigma_daily` | float | 日频 μ/σ |
| `mu_annualized` / `sigma_annualized` | float | 年化 μ/σ（仅供参考） |
| `sigma_floored` | bool | 是否用了兜底 σ（数据极静） |
| `take_profit` / `stop_loss` | float | 兜底后的 TP/SL |
| `paths.{median,p05,p25,p75,p95}` | list[float] | 每个时点的分位价格（长度 = forecast_days+1） |
| `sample_paths` | list[{id, prices}] | 前 N 条原始路径（前端画淡线） |
| `history_closes` / `history_dates` | list | 最近 60 天历史收盘价 + 日期（衔接用） |
| `warnings` | list[str] | 数据质量/边界警告 |
| `stats.final_price_*` | float | 最终价分位 |
| `stats.expected_return_pct` | float | 中位预期收益 |
| `stats.prob_higher_pct` | float | 上涨概率 |
| `stats.prob_take_profit_pct` | float \| null | TP 命中概率 |
| `stats.prob_stop_loss_pct` | float \| null | SL 命中概率 |
| `stats.max_drawdown_median_pct` | float | 中位最大回撤 |
| `stats.max_drawdown_worst_5pct_pct` | float | 5 分位最大回撤（≈ 95% 路径不超过） |
| `stats.first_touch_tp_day_median` | int \| null | 中位首次触 TP 的天数 |
| `stats.first_touch_sl_day_median` | int \| null | 中位首次触 SL 的天数 |

错误时 `out["error"]` 是字符串。

## 数据要求

- `df` 是 pandas.DataFrame，列至少 `date, close`（最好带 `volume` 用于停牌日判定），按日期升序。
- 至少 30 天 K 线（库内会校验更严格的 20 条有效 log return）。
- `current_price > 0`，caller 自行保证是"as-of 当前"的真实价。盘中应是实时价，不是昨收。

## 时序严谨性

本库只用历史 K 线估 μ/σ，**没有任何 look-ahead**。
输出是"在历史波动率下，未来 N 天的概率路径分布"——不是预言，是 stress test。

## 已知模型局限

- GBM 假设价格服从对数正态分布、对数收益独立同分布。
- A 股肥尾、政策冲击、跳空等事件可能让实际尾部风险 > 模型预测。
- 路径只有"日终价"，没有日内 high/low → 命中 TP/SL 概率基于日终价（实际会更早触发）。

## 文件结构

```
rquant/research/montecarlo/
├── __init__.py     # 公开 API 导出
├── forecaster.py   # 核心 MonteCarloForecaster / run_forecast
├── cli.py          # 命令行入口（python -m rquant.research.montecarlo.cli）
├── README.md       # 本文件（用户文档 / 快速上手）
└── DESIGN.md       # 设计文档（数学模型 / 决策记录 / 调试指南）
```

## 设计文档

详细的设计 / 数学模型 / 决策记录 / 调试指南见 [`DESIGN.md`](./DESIGN.md)。

主要章节：

1. 一句话定义
2. 复刻来源与差异
3. 数学模型（GBM 推导 + dt 选择）
4. 参数估计（μ/σ + 停牌日剔除 + σ 退化保护）
5. 路径生成算法
6. 统计量计算（分位带 / MDD / TP-SL 命中）
7. 输出字段详解
8. 边界场景处理矩阵
9. 时序严谨性证明
10. 性能与数值注意
11. 已知模型局限
12. 调试与排错
13. 决策记录（13 个关键设计决策）

## 测试

```bash
pytest tests/test_montecarlo.py -v          # 库 smoke test（13 用例）
pytest tests/test_montecarlo_api.py -v      # HTTP API 集成测试（11 用例）
```
