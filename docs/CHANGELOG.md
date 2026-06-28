# Changelog

> RetailQuant 项目变更日志
> 格式参考 [Keep a Changelog](https://keepachangelog.com/)

---

## [Unreleased] - 2026-06-22

### Fixed（修复）

#### 🔴 P0-1：首页 N+1 K 线查询（性能）

- **文件**：`rquant/web/routes.py`
- **问题**：`index()` 路由里持仓 / 卖出信号 / 买入信号三处循环各自调用 `data.fetch_kline(code, 70)`，N 只股票会拉 3N 次 K 线。
- **修复**：在视图入口一次性预加载（持仓 + 标的池 → 去重 → `code → DataFrame` 字典），三处循环复用同一份 DataFrame。
- **影响**：首页首屏 K 线拉取从 3N 降到 1 次；池子 ≥ 20 只时有感。

#### 🔴 P0-2：路由器全局缓存污染回测（正确性）

- **文件**：
  - `rquant/strategy/router/market_regime.py`
  - `rquant/strategy/router/scenario_router.py`
- **问题**：`get_market_regime()` 按"今天日期"缓存 MarketState。**回测时**整次回测都用"今天的 regime"，过去每个月的 BULL / BEAR / SIDEWAYS 被错误替换。
- **修复**：
  - `get_market_regime(index_df=None, use_cache=True)` 增加 `use_cache` 参数。
  - 缓存 key 改为"传入 index_df 的最后日期"而非"今天"，避免污染。
  - 新增 `ScenarioRouter.signal_buy_at(regime_state)` 回测入口，调用方传入已算好的 regime，回测场景必须配合 `use_cache=False`。
- **影响**：回测 OOS 验证可信赖；路由器接入精细版回测引擎时不需要再改 router 本身。

#### 🔴 P0-3：月频回测 look-ahead bias（正确性）

- **文件**：`rquant/strategy/factor/factor_calc.py`
- **问题**：`run_pipeline` 拉 K 线时用全量（默认 250 天 / datalen=5000），不按 `rebalance_date` 切片。调仓日 2025-06-01 算 20 日动量时，可能用到 2025-06-02 之后的收盘价。
- **修复**：`run_pipeline` 第 2 步拉完 K 线后立即按 `rebalance_date` 切片：

  ```python
  df = df[df["date"] <= rebalance_date].reset_index(drop=True)
  ```

- **影响**：月频回测数字会**下降**（之前偏乐观），修后才是真可实盘的数字。

### Verified

- ✅ 5 个相关模块静态 import 正常
- ✅ `get_market_regime(use_cache=False)` 不污染全局缓存
- ✅ 不同日期的 regime 互不串扰（cache 按数据日期 key）
- ✅ `ScenarioRouter.signal_buy_at` 返回 Signal 正常
- ✅ `run_pipeline` 端到端：200 行 K 线（故意含未来数据）→ 切片剩 92 行
- ✅ `ruff check` 无 warning

### Documentation

- 新增 `docs/code-walkthrough-2026-06-22.md`（全量代码导读）
- 新增 `docs/opt-2026-06-22.md`（优化建议 + patch）
- 新增 `docs/CHANGELOG.md`（本文件）
- 同步 `docs/STRATEGIES.md`、`docs/多因子选股回测系统.md`、`docs/大纲.md`、`docs/代码索引.md`

---

## [Unreleased] - 2026-06-29

### Added（新增）

#### 蒙特卡洛路径预测工具库（个股 stress test）

- **来源**：从 `FactorQ/src/advisor/montecarlo.py` 1:1 复刻而来（保留全部核心算法与 `[2026-06-25]` 修复注释），位置 `rquant/research/montecarlo/`。
- **新增包**：
  - `rquant/research/montecarlo/__init__.py` — 公开 API 导出（`MonteCarloConfig` / `MonteCarloForecaster` / `run_forecast` + 5 个经验阈值常量）
  - `rquant/research/montecarlo/forecaster.py` — 核心 GBM + 停牌日剔除 + σ 退化保护 + TP/SL 自洽校验
  - `rquant/research/montecarlo/cli.py` — 命令行入口（`python -m rquant.research.montecarlo.cli`）
  - `rquant/research/montecarlo/README.md` — 用户文档（quick reference）
  - `rquant/research/montecarlo/DESIGN.md` — 设计文档（13 章 + 2 附录，654 行）
- **新增 HTTP 路由**：`rquant/web/routes.py` → `GET /api/montecarlo/<code>`（自选股 / 持仓行均可触发）
  - Query params：`days` / `sims` / `lookback` / `kline_days` / `seed` / `tp` / `sl` / `live_price`
  - 响应：与 `run_forecast()` 同 schema，`{ok: true, ...out_dict}` 或 4xx/5xx
- **新增前端 UI**：
  - `templates/index.html` — 新增 `#mc-modal` + 自选股 / 持仓行 `[📊 预测]` 按钮 + 5 个 JS 函数（`showMonteCarlo` / `runMonteCarlo` / `closeMonteCarlo` / `_mcRenderSummary` / `_mcRenderChart`）
  - `static/style.css` — 新增 11 个 `.mc-*` 类
  - Chart.js 4.4.1（已有 CDN 依赖）画分位带渐变（`fill: { target: datasetIndex }`）
- **新增测试**：
  - `tests/test_montecarlo.py` — 库 smoke test（13 用例：import / 字段 / 复现 / 单调 / TP-SL 自洽 / 停牌日 / σ 退化 / error 分支）
  - `tests/test_montecarlo_api.py` — Flask test_client 集成测试（11 用例：路由 / 成功 / seed 复现 / live_price / TP-SL 透传 / 兜底 / 空 K 线 / fetch 异常 / 库 error / 大小写 / lookback 钳位）

### Verified

- ✅ `pytest tests/test_montecarlo.py tests/test_montecarlo_api.py` → 24/24 passed
- ✅ `ruff check` + `ruff format` 全部通过
- ✅ 完整链路 smoke：`curl /api/montecarlo/sh600000?days=20&sims=200&seed=42&tp=13.5&sl=11.8` → 200 + 字段齐全
- ✅ 服务 `python3 app.py` 端口 8080 启动正常

### Documentation

- 新增 `rquant/research/montecarlo/DESIGN.md`（设计 / 数学 / 决策记录）
- 更新 `docs/ui.md`：§8 持仓行 / §11 自选股行 加 `[📊 预测]` 按钮；新增 §13 蒙特卡洛弹窗章节；§14-§16 重编号；JS 函数速查表 +5 行；CSS 类速查表 +11 行
- 同步本 CHANGELOG

### Non-breaking（无破坏）

- `rquant/__init__.py` 顶层导出、`web/routes.py` 仅 +1 import + 1 新路由，**不影响**现有页面 / API
- 没动 `templates/error.html`、`static/style.css` 现有样式（仅 append）
- 没改 `requirements.txt` / `pyproject.toml` / 任何 `scripts/`

---

## 历史变更

变更日志自 2026-06-22 起维护。之前的版本演变请查阅 git log。
