# MonteCarlo 设计文档

> 个股蒙特卡洛路径预测工具库 — 设计 / 实现 / 决策全记录

**模块位置**: `rquant/research/montecarlo/`
**来源**: [FactorQ](https://github.com/.../FactorQ) `src/advisor/montecarlo.py`（2026-06-29 同步）
**复刻策略**: 1:1 保留全部核心算法 + `[2026-06-25]` 修复注释；仅剥除 `OnDemandAnalyzer` 依赖

---

## 目录

1. [一句话定义](#1-一句话定义)
2. [复刻来源与差异](#2-复刻来源与差异)
3. [数学模型](#3-数学模型)
4. [参数估计（μ / σ）](#4-参数估计μ--σ)
5. [路径生成](#5-路径生成)
6. [统计量计算](#6-统计量计算)
7. [输出字段详解](#7-输出字段详解)
8. [边界场景处理矩阵](#8-边界场景处理矩阵)
9. [时序严谨性](#9-时序严谨性)
10. [性能与数值注意](#10-性能与数值注意)
11. [已知模型局限](#11-已知模型局限)
12. [调试与排错](#12-调试与排错)
13. [决策记录](#13-决策记录)

---

## 1. 一句话定义

**给定历史 K 线 + 当前价 + TP/SL，模拟未来 N 天的价格路径分布（GBM + 分位带 + 命中率统计），用于个股 stress test**——不是预言，是"在历史波动率下，未来最可能怎么走 + 最差能差到什么程度"的概率化描述。

---

## 2. 复刻来源与差异

### 2.1 来源

| 项 | FactorQ 原版 | 本库 |
|----|------|------|
| 路径 | `FactorQ/src/advisor/montecarlo.py` | `rquant/research/montecarlo/forecaster.py` |
| 模型 | GBM（日频 dt=1） | 同 |
| 行数 | ~480 | ~340（剥了 __main__ 块） |
| 关键修复 | `[2026-06-25]` 停牌剔除 / σ 退化 / TP-SL 自洽 | 同 |

### 2.2 复刻时做的调整（仅 3 项）

1. **目录重定位**：`src/advisor/` → `rquant/research/montecarlo/`
2. **剥 `__main__` 块**：原版 `__main__` 调 `OnDemandAnalyzer.analyze()` 拿实时行情 + 策略 TP/SL，FactorQ 专属。本库改为 `cli.py`，走 `rquant.business.data.fetch_kline`，TP/SL 让 caller 显式传。
3. **包结构**：原版是单文件，本库拆为 `__init__.py`（导出）+ `forecaster.py`（核心）+ `cli.py`（命令行）+ `README.md`（用户文档）+ `DESIGN.md`（本文）。

### 2.3 没动什么（保证 1:1 复刻）

- 算法步骤（蒙特卡洛流程、σ/μ 估计、分位带、TP/SL 校验、MDD 计算）
- 所有 `[2026-06-25]` 修复注释（停牌日剔除、σ 退化保护、TP/SL 自洽校验）
- 字段名（`sigma_floored`、`max_drawdown_worst_5pct_pct` 等命名都不改）
- 经验阈值常量（`MIN_SIGMA_DAILY=1e-4`、`SIGMA_FLOOR=0.005` 等）

任何差异，**只在调用层**，不影响输出字段语义。

---

## 3. 数学模型

### 3.1 几何布朗运动（GBM）

GBM 是金融业最常用的股价模型假设：

$$
dS_t = \mu S_t \, dt + \sigma S_t \, dW_t
$$

其中：

- $S_t$：第 $t$ 时刻价格
- $\mu$：漂移率（日频 = 年化 / 252）
- $\sigma$：波动率（日频 = 年化 / $\sqrt{252}$）
- $W_t$：标准布朗运动（$dW_t \sim \mathcal{N}(0, dt)$）

精确解（Itô 公式）：

$$
S_{t+dt} = S_t \cdot \exp\left[ \left(\mu - \frac{\sigma^2}{2}\right) dt + \sigma \sqrt{dt} \cdot Z \right], \quad Z \sim \mathcal{N}(0, 1)
$$

### 3.2 本库用的日频简化（dt = 1）

$$
P_{t+1} = P_t \cdot \exp\left( \mu - \frac{\sigma^2}{2} + \sigma \cdot Z_t \right), \quad Z_t \sim \mathcal{N}(0, 1)
$$

其中 $\mu, \sigma$ 都是**日频**参数。

> 一般形式是 $dt$（任意时间步长），dt=1 时跟简化公式完全等价。**目前固定 dt=1**（一个交易日），因为 A 股 T+1，最小有意义的时间步就是"下一个交易日"。如果以后想做分钟级，把 $\mu, \sigma$ 换成"分钟频"参数即可，公式不变。

### 3.3 为什么选 GBM（而不是 jump-diffusion、Heston、SABR 等）

| 模型 | 优点 | 缺点 | 选/不选 |
|------|------|------|--------|
| **GBM** | 解析解已知、参数估计简单、解释直观 | 假设对数收益正态分布、无肥尾 | **选**（教学价值 + 实用底线） |
| Jump-diffusion | 能抓跳空 | 跳幅估计需要事件数据 | 不选（数据成本高） |
| Heston | 随机波动率 | 多 2 个参数，OOS 易过拟合 | 不选（不是这个工具的目标） |
| Historical bootstrap | 无分布假设 | 不能给"未来路径概率分布" | 不选（这是 path simulator，不是 scenario） |

GBM 是**最弱假设 + 最直观**的 baseline。如果用户想"升级"到带跳空的，单独加个 `MonteCarloForecasterV2` 即可，不污染本库语义。

### 3.4 蒙特卡洛 estimator 原理

模拟 $N$ 条独立路径（$N$ = `simulations`），每条路径走 $T$ = `forecast_days` 步。

对每个时点 $t \in \{0, 1, \ldots, T\}$：
- 5 分位 $P_{05}(t) = \mathrm{percentile}_{5\%}\big(\{S^{(i)}_t\}_{i=1}^{N}\big)$
- 25 分位 / 50（中位）/ 75 / 95 类似

**大数定律保证**：当 $N \to \infty$，分位估计收敛到真实分布分位。实务上 $N = 1000$ 已足够（误差 $\sim 1/\sqrt{N} \approx 3\%$），$N = 5000$ 误差 $\sim 1.4\%$，**不需要更高**。

> 注意：分位带宽度受**预测长度** $T$ 影响——预测 60 天的分位带天然比 20 天宽（GBM 的标准差累积放大）。不要拿不同 forecast_days 的结果横向比较带宽。

---

## 4. 参数估计（μ / σ）

### 4.1 公式

取最近 `lookback_days` 个交易日的**有效**对数收益率：

$$
r_t = \ln\left(\frac{P_t}{P_{t-1}}\right)
$$

样本均值 = 漂移率：

$$
\hat{\mu} = \frac{1}{n} \sum_{i=1}^{n} r_i
$$

样本标准差（无偏估计，ddof=1）= 波动率：

$$
\hat{\sigma} = \sqrt{\frac{1}{n-1} \sum_{i=1}^{n} (r_i - \hat{\mu})^2}
$$

年化（仅供参考，**库本身用日频**）：

$$
\hat{\mu}_{\mathrm{annual}} = \hat{\mu} \times 252, \quad \hat{\sigma}_{\mathrm{annual}} = \hat{\sigma} \times \sqrt{252}
$$

> **不年化的原因**：GBM 公式本身要日频参数；如果先年化再除回去，引入浮点误差。如果用户想看年化展示，自己乘。

### 4.2 关键修复：停牌日剔除（[2026-06-25]）

**问题**：A 股停牌日 OHLC 全等于前日 close，volume = 0。如果不剔除，停牌日的 log return = 0，会**降低** $\hat{\mu}$ 并**压缩** $\hat{\sigma}$，让模型"看起来更稳"，但实际上低估了真实波动率。

**判定规则**：

```python
is_suspended = (close == close.shift(1)) & (volume <= 0)
```

**为什么用 close==close.shift(1) 而不是别的**：

| 判定方式 | 误判风险 | 备注 |
|---------|---------|------|
| `volume == 0` | 漏掉"低成交量但有交易"的票 | 不可靠 |
| `close == close.shift(1)` | 大幅低开/高开后又收回 | A 股几乎不会发生 |
| **两者组合**（本库） | 极低 | A 股停牌特征**严格符合** OHLC 全等于前日 + volume=0 |

**剔除流程**（`forecaster.py:_compute_log_returns`）：

1. 取 `lookback + 1` 行（最后一行需要 prev_close）
2. 计算 `log_close = ln(close)`，差分得到 `log_rets_raw`
3. 构造 `bad_mask = suspended_mask | invalid_mask`
4. `log_rets = log_rets_raw[~bad_mask]`
5. 额外剔除 ±inf（极端值保护）
6. 检查样本数（见下）

### 4.3 关键修复：σ 退化保护（[2026-06-25]）

**问题**：某些场景下 σ 极小（如上市初期新股 / 数据源脏），会触发后续 `np.random.normal` 数值问题，导致分位带"几乎是一条直线"——看起来像"模型很有信心"，实际是**伪信号**。

**阈值**：

```python
MIN_SIGMA_DAILY = 1e-4  # σ < 1e-4 → 年化 < 1.6%，视为退化
SIGMA_FLOOR = 0.005     # 兜底为 0.5%/日（年化 ~8%，A 股合理下限）
```

**为什么 1e-4**：A 股真实 σ 大约在 0.015-0.04（日频），1e-4 已经是噪声级。年化 1.6% 比货基还低，**肯定不正常**。

**为什么兜底 0.005**：A 股 ETF 长期年化波动率约 15-25%（日频 0.01-0.016），个股更高。0.005 是个保守下限，避免兜底后路径"剧烈波动"误导用户。

**副作用**：warning 里会说明"已用兜底 σ=0.005"，前端应展示，让用户知道"这不是真实波动"。

### 4.4 样本不足保护

```python
MIN_LOG_RETS = 20                # 有效 log return 至少要 20 条，否则拒绝
LOOKBACK_ADEQUACY_RATIO = 0.8    # 实际样本 / 请求 lookback < 0.8 → warning
```

**为什么 20**：
- $n < 20$：标准差估计不稳定（卡方分布尾部重）
- $n \ge 20$：t 分布接近正态，σ 估计误差 < 15%

**为什么 0.8**：
- 200 天 lookback 只剩 159 条有效（80%）→ 警告但仍算
- < 80% → 警告 + 输出的 `lookback_days_used` 字段诚实反映

### 4.5 当前价的"位置"（重要）

```
log_close = log(close).diff()  →  log_rets[0] = ln(P_1 / P_0)
```

$P_0$ 是最早一天的 close，$P_n$ 是最后一天的 close。`run_forecast(df, current_price=...)` 里传的 `current_price` **不参与** μ/σ 估计——它只是 GBM 路径的**起点**。

> 这意味着用户传"盘中实时价"作为 current_price 时，不会污染历史波动率估计。GBM 起点 = 实时价，μ/σ 仍基于历史日终收盘。

---

## 5. 路径生成

### 5.1 算法步骤

```python
rng = np.random.default_rng(cfg.seed)         # 1. 随机数发生器（可复现）
Z = rng.standard_normal((sims, days))          # 2. 一次性生成所有标准正态
increments = (mu - 0.5 * sigma**2) + sigma * Z # 3. GBM 增量
log_paths = cumsum(increments, axis=1)        # 4. log 价格路径
log_paths = hstack([zeros, log_paths])          # 5. 加 day 0 = 当前价
paths = current_price * exp(log_paths)         # 6. 真实价格路径
```

### 5.2 关键实现细节

- **一次性生成 Z**：`(sims, days)` 矩阵，避免循环里调 RNG（性能 + 一致性）
- **day 0 列 = 0**：让 paths 的形状统一为 `(sims, days+1)`，便于前端的"历史 → 未来"拼接
- **当前价 = paths[*, 0]**：所有路径从同一价起步（GBM 是鞅的修正版本）

### 5.3 数值稳定性

- `increments` 中 `(mu - sigma²/2)` 可能非常小（如 mu=0.0005, sigma=0.02 → -0.0002）——在 float64 下完全没问题
- `cumsum` 在 1000 步以内不会累积到 inf（即使 σ=0.1，1000 步后 log 价格最大约 ±25，对应价格比例 e^25 ≈ 7e10，仍在 float64 范围）
- `exp` 在 log_paths 巨大时（>700）会溢出，但实际不会出现

### 5.4 seed 的语义

- `seed=None` → 每次结果不同（生产模式）
- `seed=42` → 完全可复现（测试 / 调试）

注意 seed 只影响**路径生成**，不影响 μ/σ 估计（μ/σ 由数据决定）。

---

## 6. 统计量计算

### 6.1 分位带（paths）

`np.percentile(paths, q*100, axis=0)` —— 对每个时点 t 取所有 sims 条路径的 q 分位。

```python
median = percentile(paths, 50, axis=0)  # 中位路径
p05    = percentile(paths, 5,  axis=0)  # 5% 分位（最差）
p95    = percentile(paths, 95, axis=0)  # 95% 分位（最好）
```

**单调性**：p05 ≤ p25 ≤ median ≤ p75 ≤ p95（测试里有断言）

### 6.2 最终价分布（stats.final_price_*）

只看路径最后一天 `paths[:, -1]`：

- `final_price_median`：最终价中位
- `final_price_p05`：5 分位（最差 5% 的最终价）
- `final_price_p95`：95 分位（最好 5% 的最终价）

### 6.3 预期收益 & 上涨概率

```python
expected_return_pct = (final_median / current_price - 1) * 100
prob_higher_pct = mean(final_prices > current_price) * 100
```

`expected_return_pct` 基于**中位**而不是均值——GBM 的最终价分布是**对数正态**（右偏），均值 > 中位，用均值会高估预期收益。

### 6.4 TP / SL 命中概率

```python
prob_tp = mean((paths >= tp).any(axis=1)) * 100  # 路径中任意一日 >= TP 的占比
prob_sl = mean((paths <= sl).any(axis=1)) * 100
```

**关键**：是"路径中任意一日"触发，不是"最终价"触发——这反映了"未来 N 天内触顶/触底"的概率，更符合 TP/SL 实际语义。

**已知语义漏洞（保留 FactorQ 原行为）**：
- 当 TP ≤ SL 时，校验拒绝 → tp/sl = None → prob_tp/prob_sl = None
- 但返回的 `take_profit`/`stop_loss` 字段是兜底后的值（`current_price * 1.08 / 0.96`）——这是给前端画横线用
- **结果**：库对自相矛盾的 TP/SL 不重算命中率，前端需注意 `prob_*` 为 None 的情况

### 6.5 最大回撤（MDD）

```python
running_max = np.maximum.accumulate(path)         # 历史最高价
drawdown = path / running_max - 1                # 各时点回撤（负值）
mdd = np.nanmin(drawdown)                        # 最大回撤 = 最深谷底
```

- `max_drawdown_median_pct`：所有路径 MDD 的中位
- `max_drawdown_worst_5pct_pct`：MDD 的 5 分位（**更负**）——意味着 95% 的路径"最差也不会比这个回撤更深"

**为什么用 5 分位而不是 95 分位**：因为 MDD 是负值，5 分位 = "最差的 5% 路径的 MDD 也有多差"，更有 stress test 价值。FactorQ 早期用 `p95_pct` 命名容易误读，2026-06-25 改为 `worst_5pct_pct`。

### 6.6 首次触价天数

```python
first_touch_day = argmax(path >= tp)  # 第一次 >= tp 的 day index
```

- `first_touch_tp_day_median`：所有"触发了 TP"的路径中，首次触发的中位天数
- `first_touch_sl_day_median`：同上，对 SL
- None 表示 0 条路径触发（TP 太离谱 / SL 太离谱）

**注意 day index 从 0 起**：0 = 当前价，1 = 第 1 天收盘。如果 TP = current_price，那 day 0 就触发，`first_touch_tp_day_median = 0`。

---

## 7. 输出字段详解

```python
out = run_forecast(df, current_price=12.34, ...)
# out 是 dict，所有字段：
```

### 7.1 顶层字段

| 字段 | 类型 | 来源 | 说明 |
|------|------|------|------|
| `code` | str | caller | 股票代码，透传 |
| `name` | str | caller | 股票名称，透传 |
| `current_price` | float | caller | GBM 起点（4 位小数） |
| `last_date` | str | `df["date"].iloc[-1]` | K 线末日 YYYY-MM-DD |
| `lookback_days_used` | int | `_compute_log_returns` | 实际有效 log return 条数（剔停牌后） |
| `forecast_days` | int | config | 预测步数 |
| `simulations` | int | config | 路径数 |
| `mu_daily` | float | `mean(log_rets)` | 日频 μ |
| `sigma_daily` | float | `std(log_rets, ddof=1)` | 日频 σ |
| `sigma_floored` | bool | σ < 1e-4 ? | 是否用了兜底 σ |
| `mu_annualized` | float | `mu_daily * 252` | 年化 μ |
| `sigma_annualized` | float | `sigma_daily * sqrt(252)` | 年化 σ |
| `take_profit` | float | 校验后/兜底 | TP 价 |
| `stop_loss` | float | 校验后/兜底 | SL 价 |
| `paths` | dict | 见 7.2 | 分位带 |
| `sample_paths` | list | 前 N 条原始路径 | 画淡线 |
| `history_closes` | list | `df.tail(60).close` | 历史 60 天收盘价 |
| `history_dates` | list | `df.tail(60).date` | 历史 60 天日期（MM-DD） |
| `warnings` | list[str] | 各种校验 | 数据质量警告 |
| `stats` | dict | 见 7.3 | 统计量 |
| `error` | str | 失败时 | 错误信息（成功时不出现） |

### 7.2 paths 子结构

```python
out["paths"] = {
    "median": [...],   # 长度 forecast_days + 1
    "p05":    [...],
    "p25":    [...],
    "p75":    [...],
    "p95":    [...],
}
```

每个 list 索引 i 对应"第 i 个交易日"的**分位价**（i=0 = 当前价）。

### 7.3 stats 子结构

| 字段 | 类型 | 含义 |
|------|------|------|
| `final_price_median` | float | 第 T 天的中位最终价 |
| `final_price_p05` | float | 第 T 天的 5 分位最终价 |
| `final_price_p95` | float | 第 T 天的 95 分位最终价 |
| `expected_return_pct` | float | 中位预期收益率 (%) |
| `prob_higher_pct` | float | 最终价 > 当前价的概率 (%) |
| `prob_take_profit_pct` | float \| None | 路径中任意一日 ≥ TP 的概率 (%) |
| `prob_stop_loss_pct` | float \| None | 路径中任意一日 ≤ SL 的概率 (%) |
| `max_drawdown_median_pct` | float | 路径 MDD 的中位 (%) |
| `max_drawdown_worst_5pct_pct` | float | 路径 MDD 的 5 分位 (%)——95% 路径不超过 |
| `first_touch_tp_day_median` | int \| None | 中位首次触 TP 的天数 |
| `first_touch_sl_day_median` | int \| None | 中位首次触 SL 的天数 |

---

## 8. 边界场景处理矩阵

| 输入 | 现象 | 处理 | 返回 |
|------|------|------|------|
| `df is None` | K 线缺失 | 立即返回 error | `{"error": "数据不足（仅 0 天…）"}` |
| `len(df) < 30` | 数据太少 | 立即返回 error | `{"error": "数据不足（仅 X 天…）"}` |
| `current_price <= 0` | 当前价无效 | 立即返回 error | `{"error": "current_price 必须 > 0"}` |
| 停牌日 ≥ 50% | 大量剔除 | warning + 继续 | `out.warnings` 含 "排除 N 条停牌日…" |
| 全部停牌 | 无有效 log return | 返回 error | `{"error": "有效样本不足（0 条…）"}` |
| 有效样本 < 20 | 不够统计 | 返回 error | `{"error": "有效样本不足（X 条…）"}` |
| 有效样本 < 80% lookback | 数据稀疏 | warning + 继续 | `out.warnings` 含 "统计估计可能不稳定" |
| σ < 1e-4 | 退化 | 兜底 0.005 + warning | `out["sigma_floored"] = True` |
| σ > 0.20 | 极大（年化 > 80%） | warning（不兜底） | `out.warnings` 含 "σ 极大" |
| TP = current_price | 等于起点 | warning | `prob_tp` 接近 100% |
| SL = current_price | 等于起点 | warning | `prob_sl` 接近 100% |
| **TP ≤ SL** | 自相矛盾 | 拒绝 TP/SL + 兜底到 ×1.08/×0.96 + warning | `prob_tp = prob_sl = None` |

**所有 error 路径**：库返回 `{"error": ..., "code": ..., "name": ..., "warnings": [...]}`，HTTP 层映射为 400。

---

## 9. 时序严谨性

### 9.1 证明：本库零 look-ahead

任何预测都满足：

`input(forecast) = K 线(date ≤ D_now) + current_price(at D_now)`

具体地：
- μ/σ 估计只用 `df.tail(lookback_days+1)`——严格在当前日之前
- `current_price` 由 caller 决定，库不"补充"任何当前日之后的数据
- 路径生成是**纯前向模拟**，不基于未来已知信息

### 9.2 为什么这事重要

A 股策略经常掉进"看起来很赚钱"陷阱：

- ❌ 用未来数据算 μ/σ（回填未来信息）→ 数字虚高 50-200%
- ❌ 用当前价参与 μ/σ 估计（重复计算）→ 高估近期波动率
- ❌ 用未来 TP/SL 反推"命中概率"（事后诸葛亮）

本库的做法是：
- ✅ μ/σ 仅来自历史
- ✅ current_price 仅作为 GBM 起点，**不污染**历史统计
- ✅ TP/SL 由 caller 传入，库只算"在该 TP/SL 下的概率"，不做"回填"

**用户责任**：保证 `current_price` 是"as-of 当前"的真实价（盘中应为实时价，不是昨收）。库不查。

### 9.3 给前端的固定风险提示

任何 MC 图表上方应固定展示：

> **模型提示**：本预测基于历史波动率（GBM 模型），未来实际可能因政策、黑天鹅、肥尾事件而严重偏离。仅供参考，不构成投资建议。

---

## 10. 性能与数值注意

### 10.1 性能基准（M2 Mac, Python 3.13, numpy 2.4）

| sims × days | 单次耗时 |
|-------------|---------|
| 1000 × 20 | ~5 ms |
| 1000 × 252 | ~30 ms |
| 5000 × 252 | ~120 ms |

瓶颈在 MDD 计算（Python 循环）。如果 sims > 10000，考虑 numba 加速或向量化 MDD。

### 10.2 内存

- `Z` 矩阵：(sims, days) float64
- 1000 × 252 → ~2 MB
- 10000 × 252 → ~20 MB
- `paths` 同尺寸 → 翻倍
- 总体在 1000 sims 下可忽略

### 10.3 数值边界

- `cumsum` 在 1000 步以内不会溢出（即使 σ=0.1，log 价格最大约 ±25）
- `exp(710)` 是 float64 上界——实际场景不会出现
- 唯一可能出问题的：用户在外部对 paths 做 `np.log` 后再传给库——库本身不假设 paths 是 log 域

---

## 11. 已知模型局限

### 11.1 模型假设的局限

| 假设 | 真实市场 | 影响 |
|------|---------|------|
| 对数收益正态分布 | A 股有明显肥尾（左尾更厚） | 模型低估极端下跌概率 |
| 对数收益独立同分布 | 有波动率聚集、均值回归 | 模型低估短期集群风险 |
| 连续价格 | A 股有涨跌停 ±10%/±20% | 模型可能产生"理论可达"但实际不可达的价格 |
| 无跳空 | A 股有政策跳空、停牌后跳空 | 模型无法预测这些离散事件 |

### 11.2 输出语义边界

- **路径是"日终价"，没有日内 high/low** → 命中 TP/SL 概率基于日终价
  - 实际盘中可能更早触发（TP 拉到日内高点就卖了）
  - 所以 `prob_tp` / `prob_sl` 是**保守下限**，真实"日内触达"概率 ≥ 模型输出
- **历史 60 天是"最近 K 线"**，不是"预测起点前的全部历史"
  - 路径起点 = `current_price`，不一定是末日 close
  - 路径分位带是"从 current_price 出发"的，不是"从末日 close 出发"

### 11.3 不做的事

- ❌ **不做仓位建议**：库只算路径分布 + 命中率，不算 Kelly / 期望效用
- ❌ **不做风险预算**：风险评估是另一层（见 backtest 模块）
- ❌ **不做 portfolio 级**：本库是**单只** MC，多只的协方差矩阵建模另说

---

## 12. 调试与排错

### 12.1 常见 error 排查

| Error 关键词 | 原因 | 修法 |
|--------------|------|------|
| `数据不足（仅 X 天…）` | K 线太少 | 拉更长的 `kline_days` / 检查数据源 |
| `有效样本不足（X 条…）` | 停牌日太多 | 看 warnings 里的"停牌"比例 |
| `current_price 必须 > 0` | caller 传错 | 检查 caller 的取价逻辑 |
| `TP ¥X ≤ SL ¥Y 逻辑不自洽` | TP/SL 输反 | 调换或单独传一个 |
| `σ=X 极小（年化 < 1.6%）` | 数据极静 / 新股 | 看 `sigma_floored=True`，前端应警告 |

### 12.2 Warning 含义速查

| Warning | 含义 | 用户该做什么 |
|---------|------|------------|
| `实际可用数据 N 天 < 请求 lookback N 天` | K 线不够长 | 拉更长的 K 线 |
| `排除 N/M 条停牌日…` | 停牌日被剔除 | 看历史是否频繁停牌（基本面信号） |
| `有效样本 N < 请求 lookback × 80%` | 数据稀疏 | 考虑更长窗口或换标的 |
| `σ=X 极小…已用兜底 σ=0.005` | σ 退化 | 别把这只票当"稳定"标的 |
| `σ=X 极大（年化 Y%）` | 数据异常 | 检查数据源（是否单位错了） |
| `TP ¥X ≤ SL ¥Y 逻辑不自洽` | 用户输入错 | 修 TP/SL |
| `TP 等于当前价` | 没意义 | 改 TP |
| `SL 等于当前价` | 没意义 | 改 SL |

### 12.3 输出 sanity check

跑前先快速验证：

```python
out = run_forecast(df, current_price=..., seed=42)
assert "error" not in out, out["error"]

# 1. 分位单调
import numpy as np
for q_lo, q_hi in [("p05", "p25"), ("p25", "median"), ("median", "p75"), ("p75", "p95")]:
    assert np.all(np.array(out["paths"][q_lo]) <= np.array(out["paths"][q_hi]) + 1e-6)

# 2. 最终价分布 = paths 最后一列
final = np.array(out["paths"]["median"])[-1]
assert abs(final - out["stats"]["final_price_median"]) < 1e-4

# 3. seed 可复现
out2 = run_forecast(df, current_price=..., seed=42)
assert out["paths"]["median"] == out2["paths"]["median"]
```

### 12.4 与 FactorQ 原版的字段对照

| FactorQ | 本库 | 说明 |
|---------|------|------|
| `stats.max_drawdown_p95_pct` | `stats.max_drawdown_worst_5pct_pct` | 2026-06-25 改名为更明确 |
| `take_profit` / `stop_loss` | 同 | 兜底语义一致 |
| `sigma_floored` | 同 | 标志位 |
| `warnings` | 同 | list[str] |
| 其余字段 | 同 | 1:1 对齐 |

---

## 13. 决策记录

### 13.1 为什么是工具库，不是服务

用户原话："以工具库的形式出现，不要干扰别的文件"。

→ 库 API + HTTP 路由 + CLI 三入口，不绑死 web 层 / 数据源。

### 13.2 为什么 dt = 1（不开分钟级 / 小时级）

- A 股 T+1，最小有意义步长是"下个交易日"
- 分钟级需要 tick 数据（数据源没有）
- 分钟级蒙特卡洛计算成本会爆炸（1 天 240 分钟 × 20 天 = 4800 步 × 1000 sims = 4.8M cells）

→ dt=1 是性价比最优解。

### 13.3 为什么用 numpy 而不是 cupy / jax

- numpy 已够快（单次 5ms）
- cupy / jax 引入 GPU 依赖（部署复杂 + 数据传输 overhead）
- 1000 sims × 252 days 量级，CPU 完全 hold 住

→ 拒绝过早优化。

### 13.4 为什么 warnings 是 list[str] 而不是 dataclass

- 前端消费方便（直接 render）
- 加新 warning 不用改 schema
- caller 可以 extend / filter

→ 字符串最务实。

### 13.5 为什么"先校验 TP/SL 再算 prob"而不是"算完再 warn"

- prob_tp 计算依赖 tp 是否为 None
- 校验失败时把 tp 清成 None → prob 自动不计算
- 避免 caller 看到"TP=5%, prob_tp=78%"这种自相矛盾

→ 校验先行。

### 13.6 为什么停牌日剔除用 close==prev_close + volume=0

详见 §4.2。简单说：A 股停牌规则**严格**对应这个特征，误判率极低；其他判定（仅 volume=0 或仅 close 不变）误判率高。

### 13.7 为什么不年化 μ/σ 给库内部用

- GBM 公式用日频
- 年化再除回来引入浮点误差
- 用户展示层想看年化 → 顶层字段暴露 `mu_annualized` / `sigma_annualized`

→ 库用日频，展示用年化。

### 13.8 为什么不存预测结果到磁盘

- 预测是"当前 μ/σ + 当前价"的快照，1 天后 μ/σ 变 → 结果过期
- 缓存成本 > 重算成本（5ms）
- 调用方如果想持久化，自己存（json.dumps 即可）

→ 无状态设计。

---

## 附录 A：术语表

| 术语 | 含义 |
|------|------|
| GBM | Geometric Brownian Motion，几何布朗运动 |
| dt | 时间步长（本库 = 1 个交易日） |
| μ (mu) | 漂移率，日频 = 年化 / 252 |
| σ (sigma) | 波动率，日频 = 年化 / sqrt(252) |
| lookback | 用于估 μ/σ 的历史窗口 |
| forecast_days | 预测未来多少天 |
| simulations | 蒙特卡洛模拟路径数 |
| TP / SL | Take Profit / Stop Loss，止盈 / 止损价 |
| 分位带 | percentile band，如 P5/P50/P95 三条线 |
| MDD | Maximum Drawdown，最大回撤 |
| Look-ahead bias | 用未来数据做预测的偏差（本库零容忍） |
| Stress test | 压力测试，看最差情况下会亏多少 |

## 附录 B：相关文件

- **核心库**: `rquant/research/montecarlo/forecaster.py`
- **命令行**: `rquant/research/montecarlo/cli.py`
- **HTTP 路由**: `rquant/web/routes.py` → `api_montecarlo()`
- **库 smoke test**: `tests/test_montecarlo.py`
- **HTTP 集成测试**: `tests/test_montecarlo_api.py`
- **用户文档**: `rquant/research/montecarlo/README.md`
- **来源**: FactorQ `src/advisor/montecarlo.py`（2026-06-29 同步）
