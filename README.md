# RetailQuant

A 股个人量化看板（单实例、本地优先、零外部账号）—— Flask + 缠论近似 + 板块 Treemap + 自选股。

- ✅ 缠论近似（MA5 > MA20 + 站上 MA5 → 买入信号）
- ✅ Buy & Hold 近似（现价 < MA60 × 0.95 → 低吸信号）
- ✅ 止损 / 止盈信号（-7% / +15% / 跌破 MA60）
- ✅ Flask + 看板（持仓、信号、资金曲线）
- ✅ 加仓 / 减仓 / 删除交易
- ✅ 板块 Treemap（行业 / 概念 Tab）
- ✅ 自选股（持久化 + 弹窗切换 + 实时行情）

---

## 启动

```bash
cd /Users/ggg1235/Downloads/rQuant
pip install -r requirements.txt
python3 app.py
# 浏览器访问 http://localhost:8080
```

自定义端口：

```bash
RQUANT_PORT=5060 python3 app.py
```

> 没有 waitress 时自动 fallback 到 Flask dev server（`app.run(debug=True)`）。

---

## 修改记录

### 2026-06-17 · 代码优化（净减 91 行，0 业务逻辑变更）

针对最近一次提交（`cdac79e 新增板块 Treemap 行情、自选股功能、看板优化`）和全项目做的代码优化与冗余清理。

#### Bug 修复

| # | 位置 | 问题 | 修复 |
|---|---|---|---|
| 1 | `requirements.txt` | 缺 `squarify`，`app.py` import 会 `ModuleNotFoundError` | 加 `squarify>=0.4` |
| 2 | `strategy.py:44` | `ma60 = _calc_ma(df, 60)` 计算后从未使用 | 删除 |
| 3 | `app.py:9, 31`, `board.py:11`, `strategy.py:9` | 未使用的 import | 删除 |
| 4 | `app.py` 默认端口 `5060` 与 README `8080` 不一致（已统一为 `8080`，可通过 `RQUANT_PORT` 覆盖） | 合并到 README |

#### 去重

| # | 位置 | 问题 | 修复 |
|---|---|---|---|
| 5 | `board.py:20-84` | `INDUSTRY_ETFS` 和 `CONCEPT_ETFS` **30/30 完全相同**（仅顺序略不同） | 合并为单一 `SECTOR_ETFS`，行业/概念共用池子 |
| 6 | `board.py:170-203` | `fetch_sector_boards` / `fetch_concept_boards` 镜像函数 | 统一为 `fetch_boards(type, top_n)`，原 API 名保留为薄包装 |
| 7 | `app.py:107-117, 299-319` | watchlist 渲染逻辑复制 2 份 | 抽 `_build_watchlist_view()` |
| 8 | `app.py:150-154` | `add_position` 用 `for ... break` 找 name | `_pool_name_map()` 字典查找 |
| 9 | `portfolio.py:22-32` | `_load_json` / `_save_json` 与 `data.py` 完全重复 | 直接 `from data import _load_json, _save_json` |

#### 死代码清理

| # | 位置 | 内容 | 处理 |
|---|---|---|---|
| 10 | `templates/index.html:376-462` | 86 行 JS `squarify()` 实现 + 注释——后端 Python squarify 早就算了坐标，注释也明确说"前端不再需要此函数" | 整段删除 |
| 11 | `app.py:31`, `board.py:91-95` | `def _log(): import sys` 在函数内重复 import | 移除 |

#### 重构

| # | 位置 | 改动 |
|---|---|---|
| 12 | `data.py:78-83` | 5 列 for 循环 → `df[cols].apply(pd.to_numeric, errors="coerce")` 一次性向量化 |
| 13 | `data.py:90-94` | `upsert_stock` 用 `setdefault(...).update(kwargs)` 替代 4 行 if/None |
| 14 | `strategy.py:91-99` | `scan_stock` 用 tuple + for 替代两个 if 块 |
| 15 | `app.py:14-17` | `int(os.environ.get("RQUANT_PORT", "5060"))` 提取为 `DEFAULT_PORT` 常量（module-level） |

#### 风格统一

- 全部 `List` / `Dict` / `Optional[X]` → `list` / `dict` / `X | None`（`__future__ annotations` 下兼容 3.9+）
- `ruff check` **0 错误**，`ruff format` 已应用
- 删除 `_test_*.py` 中的 E401/E402（多 import 同一行 / import 顺序）

#### 回归证据

```
ruff check   → All checks passed!
ruff format  → 7 files already formatted
端点回归      → 8/8 通过（11 路由全注册）
策略单元测试  → chanlun2b / buyhold / sell_signal 全 OK
Sina 行情    → sector 30 只 + concept 30 只，Treemap 坐标计算成功
```

#### 故意未动

- 业务逻辑：缠论 2B / BuyHold 阈值、止损 -7% / 止盈 +15% / MA60 跌破——实战参数原样
- 路由 / API 形态：11 路由路径、方法、返回 JSON 结构 100% 保持
- `fetch_sector_boards` / `fetch_concept_boards` 名字：留薄包装，不破坏其他模块 import
- 缓存 TTL、CACHE_DIR 路径、JSON 文件结构：全保持

---

## 文件

```
rQuant/
├── app.py              # Flask 主程序（11 路由）
├── board.py            # 板块行情（Sina 拉数 + 2 分钟缓存 + Treemap 坐标）
├── data.py             # Sina K 线 + JSON 缓存 + 自选股 + 标的池
├── strategy.py         # 缠论近似 + BuyHold + 卖出信号
├── portfolio.py        # 持仓管理（JSON 存储）
├── requirements.txt    # flask / waitress / pandas / requests / squarify
├── _test_api.py        # 备选数据源探针（nufm.dfcfw.com，未启用）
├── _test_sina.py       # 板块接口冒烟测试
├── templates/
│   ├── index.html      # 看板（持仓 + 信号 + Treemap + 自选股）
│   └── error.html
├── static/
│   └── style.css
└── data/               # K 线 JSON 缓存（自动生成）+ watchlist / portfolio / trades
```

## 注意

- 第一次访问会触发 Sina 拉数，沙箱环境可能慢
- 数据每 5 天自动刷新（应付周末/节假日）
- 持仓在 `data/portfolio.json`，删除 = 清空
- 自选股在 `data/watchlist.json`，手动编辑也生效
- `_test_*.py` 是开发期探针脚本，发布时可忽略
