# rbacktest

基于 VNPY Alpha 引擎的量化回测系统，前端 React + 后端 Flask，支持多策略对比、基准叠加、扩展指标和交易明细。

## 架构

```
rbacktest/
├── backend/
│   ├── __init__.py
│   ├── app.py                 Flask API 入口（端口检测 + 数据校验）
│   ├── backtest_engine.py     回测引擎（指标计算、交易提取、基准加载）
│   ├── strategy/              策略包（自动注册 + 参数 schema 生成）
│   │   ├── base.py             BaseStrategy 基类（_maintain_bars 共用工具）
│   │   ├── registry.py         注册中心（__init_subclass__ 自动发现）
│   │   ├── equal_weight.py     动量轮动
│   │   ├── grid_martingale.py  网格马丁格尔
│   │   ├── vp_breakout.py      量价突破
│   │   ├── donchian_turtle.py  海龟交易
│   │   ├── ma_cross.py         均线交叉
│   │   ├── rsi_reversion.py    RSI 均值回归
│   │   └── buy_hold.py         低吸策略
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx             回测结果展示（对比表+图表+交易明细+基准）
│   │   ├── api.js              API 调用层
│   │   ├── components/
│   │   │   ├── ParamPanel.jsx  参数面板（搜索/快速选择/策略编辑）
│   │   │   └── Icons.jsx
│   │   ├── App.css
│   │   ├── index.css
│   │   └── main.jsx
│   ├── package.json
│   ├── vite.config.js
│   └── index.html
├── tools/
│   ├── convert_data.py         Qlib → VNPY AlphaLab 数据转换
│   └── fetch_stock_names.py    从 akshare 下载股票名称缓存
├── tests/
│   ├── conftest.py
│   ├── test_api.py             (10 tests)
│   ├── test_engine.py          (10 tests)
│   ├── test_registry.py        注册 + 工具函数 (19 tests)
│   ├── test_momentum_rotation.py
│   ├── test_grid_martingale.py
│   └── test_vp_breakout.py
├── data/
│   ├── daily/                  *.parquet（VNPY AlphaLab 格式）
│   └── contract.json
├── stock_names.json            股票代码→名称映射（静态元数据，已提交）
├── start.sh
├── DATA_CONVERSION.md
└── README.md
```

## 内置策略

| 策略 | 名称 | 逻辑 |
|------|------|------|
| `equal_weight` | 动量轮动 | 每月初按过去 N 日收益率排序，等权持有前 top_k 只 |
| `grid_martingale` | 网格马丁格尔 | 每日计算滚动网格，低位买入/高位止盈或破网止损 |
| `vp_breakout` | 量价突破 | 突破前N日高点 + 量能放大 + 强势收盘时买入 |
| `donchian_turtle` | 海龟交易 | 20 日新高入场，10 日新低离场，2×ATR 移动止损 |
| `ma_cross` | 均线交叉 | MA5/20 双均线金叉买入，死叉卖出 |
| `rsi_reversion` | RSI 回归 | RSI(14) 超卖反弹 + MA200 趋势过滤 + ATR 仓位控制 |
| `buy_hold` | 低吸策略 | 超跌(20日>10%)+超卖(RSI<30)+缩量+止跌 四重确认 |

前端可同时勾选多个策略，结果以对比表格和叠加折线图展示。策略通过 `BaseStrategy` 基类自动注册，新增策略只需新建文件 + 一行 import。

## 策略开发

```python
# backend/strategy/my_strategy.py
from .base import BaseStrategy

class MyStrategy(BaseStrategy):
    name = "my_strategy"
    label = "我的策略"
    description = "策略说明"
    color = "#eb2f96"

    top_k: int = 5
    _param_meta = {
        "top_k": {"type": "int", "min": 1, "max": 20, "label": "持仓数量"},
    }

    def on_init(self): ...
    def on_bars(self, bars): ...
    def on_trade(self, trade): ...
```

然后在 `backend/strategy/__init__.py` 加一行 `from . import my_strategy`，策略即自动注册，前端参数面板和 API 都会自动包含。

## 数据准备

参见 [`DATA_CONVERSION.md`](DATA_CONVERSION.md) 获取完整流程（下载 Qlib 数据 → 转换为 VNPY AlphaLab 格式）。

### 股票名称

运行一次即可缓存：

```bash
uv run python rbacktest/tools/fetch_stock_names.py
```

生成 `rbacktest/stock_names.json`（已提交到仓库，clone 即可用）。定期 `--force` 刷新以获取新上市/改名。

Parquet 文件需包含列：`datetime`, `vt_symbol`, `open`, `high`, `low`, `close`, `volume`, `turnover`。

## 安装与运行

### 后端

```bash
cd rbacktest/backend
uv venv
uv pip install -r requirements.txt
uv pip install vnpy --index-url https://pypi.tuna.tsinghua.edu.cn/simple
.venv/bin/python app.py
```

端口默认 `15000`，可通过 `RBACKTEST_PORT` 环境变量覆盖。启动时会检测端口占用并告警退出。

### 前端

```bash
cd rbacktest/frontend
npm install
npm run dev
```

前端运行在 `http://localhost:5173`，通过 Vite proxy 转发 `/api` 请求到后端。

### 一键启动

```bash
chmod +x start.sh
./start.sh
```

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/stocks` | 获取可用股票列表 |
| GET | `/api/stock-names` | 代码→名称映射（支持 `?codes=` 筛选） |
| GET | `/api/strategies` | 策略元数据（含 color / param schema） |
| GET | `/api/benchmark` | 基准日线净值（默认沪深300，支持 `?code=` 切换） |
| POST | `/api/optimize` | 参数网格搜索，返回所有组合的指标矩阵 |
| POST | `/api/backtest` | 运行回测，返回统计+逐日+交易明细 |
| POST | `/api/export` | 导出回测结果为 CSV 下载 |

POST `/api/backtest` 返回新增字段：

```
results[策略名].statistics  → sortino_ratio, calmar_ratio, win_rate, profit_factor,
                               avg_win, avg_loss, max_consecutive_wins/losses
results[策略名].trades      → [{date, symbol, side, price, shares, entry_price, pnl, pnl_pct}]
```

## 已知限制

### 复权与分红

当前数据为 Qlib 提供的**前复权归一化**价格（首日=1.0），`factor`（复权因子）和 `adjclose`（后复权价）在数据转换阶段被丢弃。

**影响**：

- 现金分红不会记入账户现金，策略总收益系统性低估约 **2~3%/年**（A 股平均股息率）
- 送转股不会自动调整持仓数量
- 仓位计算使用归一化数值而非真实价格

**为什么不修复**：

1. 这是国内回测引擎（VNPY、Qlib、聚宽、米筐）的行业默认做法 — 前复权熨平价格曲线，分红缺口由数据源承担
2. 系统定位是**技术面策略对比引擎**，所有策略在同一数据上跑，缺少的分红大家都没算，相对排名不变
3. 实现完整的分红事件模拟（价格跳空 + 现金入账 + 红利税）约需 3~5 天开发，涉及引入分红数据库和引擎层事件处理

**如果要修复**，路径大致为：引入 akshare 分红表 → 在回测引擎中插入"除权事件"回调 → 调整 BarData 价格 + 增加账户现金余额。届时需同步修改 `convert_data.py` 保留 `factor` 列，以及 `backtest_engine.py` 支持除权日事件注入。

## 测试

```bash
cd rbacktest
backend/.venv/bin/python -m pytest tests/ -v   # 63 tests
```

## Lint & Format

```bash
uv run ruff check rbacktest/        # Python
uv run ruff format rbacktest/       # Python
cd rbacktest/frontend && npx prettier --check src/  # JS/CSS
```

## 技术栈

- 后端：Python 3.11+, Flask, VNPY Alpha, Polars, NumPy
- 前端：React 18, Vite, Recharts
- 测试：pytest（63 tests）
- 包管理：uv (Python), npm (Node)
- Lint：ruff (Python), prettier (JS/CSS)
