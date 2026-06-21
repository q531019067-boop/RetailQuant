#!/usr/bin/env python
"""半导体/算力 10 股 × STRATEGIES.md 10 策略批量单股回测与报告生成。"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from rquant.backtest import BacktestEngine, BrokerConfig  # noqa: E402
from rquant.research.workflow import load_kline  # noqa: E402
from rquant.strategy import get  # noqa: E402

DEFAULT_OUT_DIR = "results/semiconductor_compute_10x10_2025-06-18_2026-06-18"
DEFAULT_REPORT = "docs/semiconductor_compute_10x10_report.md"

DOCUMENTED_STRATEGIES = (
    "VpBreakout",
    "DonchianTurtle",
    "CrossBorderDca",
    "DividendLowvolRotation",
    "MultiFactor",
    "GridMartingale",
    "DragonTigerPattern",
    "ChanLun2B",
    "BuyHold",
    "ScenarioRouter",
)

STOCK_UNIVERSE: tuple[tuple[str, str, str], ...] = (
    ("sh600460", "士兰微", "半导体"),
    ("sz002371", "北方华创", "半导体"),
    ("sh603501", "韦尔股份", "半导体"),
    ("sh603986", "兆易创新", "半导体"),
    ("sz002049", "紫光国微", "半导体"),
    ("sz000977", "浪潮信息", "算力"),
    ("sh603019", "中科曙光", "算力"),
    ("sh601138", "工业富联", "算力"),
    ("sz000938", "紫光股份", "算力"),
    ("sz000034", "神州数码", "算力"),
)


@dataclass(frozen=True)
class RunConfig:
    start: str
    end: str
    capital: float
    out_dir: Path
    report_path: Path
    strategies: tuple[str, ...]
    position_pct: float = 0.95
    commission_rate: float = 0.00025
    min_commission: float = 5.0
    stamp_tax_rate: float = 0.0005
    slippage_bp: float = 1.0
    slippage_per_share: float = 0.0
    risk_free_rate: float = 0.02


def build_broker(cfg: RunConfig) -> BrokerConfig:
    return BrokerConfig(
        commission_rate=cfg.commission_rate,
        min_commission=cfg.min_commission,
        stamp_tax_rate=cfg.stamp_tax_rate,
        slippage_bp=cfg.slippage_bp,
        slippage_per_share=cfg.slippage_per_share,
        default_position_pct=cfg.position_pct,
        risk_free_rate=cfg.risk_free_rate,
    )


def run_single_backtest(
    *,
    cfg: RunConfig,
    broker: BrokerConfig,
    code: str,
    name: str,
    sector: str,
    df: pd.DataFrame,
    strategy_name: str,
) -> dict:
    strategy = get(strategy_name)
    if strategy is None:
        raise RuntimeError(f"策略未注册: {strategy_name}")

    engine = BacktestEngine(initial_capital=cfg.capital, broker=broker)
    result = engine.run(
        strategy=strategy,
        code=code,
        name=name,
        sector=sector,
        df=df,
        start_date=cfg.start,
        end_date=cfg.end,
    )

    prefix = cfg.out_dir / f"{code}_{strategy_name}"
    pd.DataFrame(result.fills).to_csv(f"{prefix}_trades.csv", index=False)
    pd.DataFrame(result.equity_curve).to_csv(f"{prefix}_equity.csv", index=False)
    summary = result.summary()
    Path(f"{prefix}_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return summary


def run_batch(cfg: RunConfig) -> pd.DataFrame:
    cfg.out_dir.mkdir(parents=True, exist_ok=True)
    broker = build_broker(cfg)
    rows: list[dict] = []
    total = len(STOCK_UNIVERSE) * len(cfg.strategies)
    done = 0

    for code, name, sector in STOCK_UNIVERSE:
        df = load_kline(code, allow_fetch=False)
        if df is None or df.empty:
            raise RuntimeError(f"无法读取 {code} 的 K 线数据")

        stock_rows: list[dict] = []
        for strategy_name in cfg.strategies:
            done += 1
            print(f"[{done}/{total}] {code} × {strategy_name} ...")
            summary = run_single_backtest(
                cfg=cfg,
                broker=broker,
                code=code,
                name=name,
                sector=sector,
                df=df,
                strategy_name=strategy_name,
            )
            rows.append(summary)
            stock_rows.append(summary)

        stock_matrix = pd.DataFrame(stock_rows)
        stock_matrix.to_csv(cfg.out_dir / f"{code}_strategy_compare.csv", index=False)

    matrix = pd.DataFrame(rows)
    matrix.to_csv(cfg.out_dir / "full_matrix.csv", index=False)
    return matrix


def aggregate(matrix: pd.DataFrame, cfg: RunConfig) -> dict:
    matrix = matrix.copy()
    matrix["profit"] = matrix["final_equity"] - matrix["initial_capital"]

    by_strategy = (
        matrix.groupby("strategy", as_index=False)
        .agg(
            runs=("strategy", "count"),
            avg_final_equity=("final_equity", "mean"),
            avg_profit=("profit", "mean"),
            avg_return_pct=("total_return_pct", "mean"),
            avg_annual_return_pct=("annual_return_pct", "mean"),
            avg_max_drawdown_pct=("max_drawdown_pct", "mean"),
            avg_sharpe=("sharpe", "mean"),
            avg_win_rate_pct=("win_rate_pct", "mean"),
            total_trades=("trade_count", "sum"),
        )
        .sort_values(["avg_return_pct", "avg_sharpe"], ascending=False)
    )
    by_strategy.to_csv(cfg.out_dir / "strategy_ranking.csv", index=False)

    best_rows = []
    for code, name in matrix[["code", "name"]].drop_duplicates().itertuples(index=False):
        sub = matrix[(matrix["code"] == code)].sort_values("total_return_pct", ascending=False).iloc[0]
        best_rows.append(
            {
                "code": code,
                "name": name,
                "best_strategy": sub["strategy"],
                "best_return_pct": sub["total_return_pct"],
                "best_final_equity": sub["final_equity"],
                "best_profit": sub["profit"],
            }
        )
    by_stock = pd.DataFrame(best_rows).sort_values("best_return_pct", ascending=False)
    by_stock.to_csv(cfg.out_dir / "stock_best_strategy.csv", index=False)

    best_single = matrix.sort_values(["total_return_pct", "sharpe"], ascending=False).iloc[0]
    best_strategy_row = by_strategy.iloc[0]

    return {
        "matrix": matrix,
        "by_strategy": by_strategy,
        "by_stock": by_stock,
        "best_single": best_single,
        "best_strategy_row": best_strategy_row,
    }


def _fmt_money(value: float) -> str:
    return f"{value:,.2f}"


def _fmt_pct(value: float) -> str:
    return f"{value:.2f}%"


def write_report(agg: dict, cfg: RunConfig) -> None:
    matrix: pd.DataFrame = agg["matrix"]
    by_strategy: pd.DataFrame = agg["by_strategy"]
    by_stock: pd.DataFrame = agg["by_stock"]
    best_single = agg["best_single"]
    best_strategy_row = agg["best_strategy_row"]

    top10_runs = matrix.sort_values(["total_return_pct", "sharpe"], ascending=False).head(10)
    strategy_table_lines = []
    for _, row in by_strategy.iterrows():
        strategy_table_lines.append(
            f"| {row['strategy']} | {_fmt_money(row['avg_final_equity'])} | "
            f"{_fmt_money(row['avg_profit'])} | {_fmt_pct(row['avg_return_pct'])} | "
            f"{_fmt_pct(row['avg_annual_return_pct'])} | {_fmt_pct(row['avg_max_drawdown_pct'])} | "
            f"{row['avg_sharpe']:.2f} | {int(row['total_trades'])} |"
        )

    run_table_lines = []
    for _, row in top10_runs.iterrows():
        run_table_lines.append(
            f"| {row['code']} | {row['name']} | {row['strategy']} | "
            f"{_fmt_money(row['final_equity'])} | {_fmt_money(row['profit'])} | "
            f"{_fmt_pct(row['total_return_pct'])} | {_fmt_pct(row['max_drawdown_pct'])} | "
            f"{row['sharpe']:.2f} | {int(row['trade_count'])} |"
        )

    stock_table_lines = []
    for _, row in by_stock.iterrows():
        stock_table_lines.append(
            f"| {row['code']} | {row['name']} | {row['best_strategy']} | "
            f"{_fmt_money(row['best_final_equity'])} | {_fmt_money(row['best_profit'])} | "
            f"{_fmt_pct(row['best_return_pct'])} |"
        )

    content = f"""# 半导体/算力 10×10 策略模拟报告

> 生成时间：2026-06-20  
> 测试窗口：{cfg.start} ~ {cfg.end}  
> 初始资金：{_fmt_money(cfg.capital)} 元 / 每次仅 1 只股票 + 1 个策略  
> 结果目录：`{cfg.out_dir.as_posix()}`

---

## 一、测试口径

| 项目 | 设定 |
|------|------|
| 股票池 | 半导体 5 只 + 算力 5 只，共 10 只 |
| 策略池 | STRATEGIES.md 文档口径 10 个策略 |
| 回测模式 | 单股单策略隔离回测，互不共享资金 |
| 撮合规则 | T+1、100 股整数手买入、卖出可零股清仓 |
| 费用 | 佣金万 2.5（最低 5 元）、卖出印花税 0.05%、滑点 1bp |
| 总运行数 | {len(STOCK_UNIVERSE)} × {len(cfg.strategies)} = {len(STOCK_UNIVERSE) * len(cfg.strategies)} |

### 股票池

| 代码 | 名称 | 板块 |
|------|------|------|
"""
    for code, name, sector in STOCK_UNIVERSE:
        content += f"| `{code}` | {name} | {sector} |\n"

    content += """
### 策略池

"""
    for strategy_name in cfg.strategies:
        content += f"- `{strategy_name}`\n"

    content += f"""
---

## 二、核心结论

### 最强策略设计（按 10 股平均收益）

- **策略名称**：`{best_strategy_row["strategy"]}`
- **10 股平均最终权益**：{_fmt_money(best_strategy_row["avg_final_equity"])} 元
- **10 股平均盈利**：{_fmt_money(best_strategy_row["avg_profit"])} 元
- **10 股平均收益率**：{_fmt_pct(best_strategy_row["avg_return_pct"])}
- **10 股平均年化收益**：{_fmt_pct(best_strategy_row["avg_annual_return_pct"])}
- **10 股平均最大回撤**：{_fmt_pct(best_strategy_row["avg_max_drawdown_pct"])}
- **10 股平均 Sharpe**：{best_strategy_row["avg_sharpe"]:.2f}

### 最佳单次组合（100 次中的冠军）

- **组合**：`{best_single["code"]}` {best_single["name"]} × `{best_single["strategy"]}`
- **最终权益**：{_fmt_money(best_single["final_equity"])} 元
- **盈利金额**：{_fmt_money(best_single["profit"])} 元
- **总收益率**：{_fmt_pct(best_single["total_return_pct"])}
- **年化收益率**：{_fmt_pct(best_single["annual_return_pct"])}
- **最大回撤**：{_fmt_pct(best_single["max_drawdown_pct"])}
- **Sharpe**：{best_single["sharpe"]:.2f}
- **交易次数**：{int(best_single["trade_count"])}

> 说明：若你每次只选 1 只股票 + 1 个策略投入 10 万，本报告中的“最佳单次组合”代表 100 次实验里的最高收益样本；  
> “最强策略设计”代表在 10 只股票上平均表现最好的策略类型。

---

## 三、策略平均表现排名

| 策略 | 平均最终权益 | 平均盈利 | 平均收益率 | 平均年化 | 平均最大回撤 | 平均 Sharpe | 总交易次数 |
|------|-------------|---------|-----------|---------|-------------|------------|-----------|
"""
    content += "\n".join(strategy_table_lines)
    content += """

---

## 四、Top 10 单次回测结果

| 代码 | 名称 | 策略 | 最终权益 | 盈利 | 收益率 | 最大回撤 | Sharpe | 交易次数 |
|------|------|------|---------|------|--------|---------|--------|---------|
"""
    content += "\n".join(run_table_lines)
    content += """

---

## 五、各股票最佳策略

| 代码 | 名称 | 最佳策略 | 最终权益 | 盈利 | 收益率 |
|------|------|---------|---------|------|--------|
"""
    content += "\n".join(stock_table_lines)
    content += f"""

---

## 六、产物索引

| 文件 | 说明 |
|------|------|
| `{cfg.out_dir.as_posix()}/full_matrix.csv` | 100 次回测汇总矩阵 |
| `{cfg.out_dir.as_posix()}/strategy_ranking.csv` | 按策略聚合排名 |
| `{cfg.out_dir.as_posix()}/stock_best_strategy.csv` | 每只股票的最佳策略 |
| `{cfg.out_dir.as_posix()}/{{code}}_{{strategy}}_summary.json` | 单次回测摘要 |
| `{cfg.out_dir.as_posix()}/{{code}}_{{strategy}}_trades.csv` | 单次成交明细 |
| `{cfg.out_dir.as_posix()}/{{code}}_{{strategy}}_equity.csv` | 单次权益曲线 |

---

## 七、风险与解读

1. **单股隔离**：每次回测仅持有一只股票，未做组合分散；与实际多标的轮动不同。
2. **MultiFactor 语义**：此处为单股 `signal_buy` 模式，与组合 TopN 多因子回测不同。
3. **ETF 策略迁移**：`CrossBorderDca`、`DividendLowvolRotation` 原设计偏 ETF，直接用于个股仅供参考。
4. **ScenarioRouter**：依赖市场状态路由，单股表现可能受子策略切换影响。
5. **样本窗口**：仅覆盖 {cfg.start} ~ {cfg.end} 约 1 年，结论不代表长期稳定超额。

---

## 八、最终回答

**在当前策略设计下，10 股平均表现最强的是 `{best_strategy_row["strategy"]}`，10 万本金平均可赚到 {_fmt_money(best_strategy_row["avg_profit"])} 元（平均收益率 {_fmt_pct(best_strategy_row["avg_return_pct"])}）。**

若只挑 100 次实验中的最优单次组合，则是 **`{best_single["code"]}` {best_single["name"]} × `{best_single["strategy"]}`**，最终权益 **{_fmt_money(best_single["final_equity"])} 元**，盈利 **{_fmt_money(best_single["profit"])} 元**（收益率 **{_fmt_pct(best_single["total_return_pct"])}**）。
"""

    cfg.report_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.report_path.write_text(content, encoding="utf-8")
    print(f"\n报告已写入: {cfg.report_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="半导体/算力 10×10 单股单策略批量回测")
    parser.add_argument("--start", default="2025-06-18", help="交易窗口起始日")
    parser.add_argument("--end", default="2026-06-18", help="交易窗口结束日")
    parser.add_argument("--capital", type=float, default=100_000.0, help="初始资金")
    parser.add_argument("--out", default=DEFAULT_OUT_DIR, help="输出目录")
    parser.add_argument("--report", default=DEFAULT_REPORT, help="Markdown 报告路径")
    parser.add_argument(
        "--strategies",
        nargs="+",
        default=list(DOCUMENTED_STRATEGIES),
        help="策略 name 列表",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    cfg = RunConfig(
        start=args.start,
        end=args.end,
        capital=args.capital,
        out_dir=Path(args.out),
        report_path=Path(args.report),
        strategies=tuple(args.strategies),
    )

    print(f"开始 10×10 回测: {len(STOCK_UNIVERSE)} 股 × {len(cfg.strategies)} 策略")
    matrix = run_batch(cfg)
    agg = aggregate(matrix, cfg)
    write_report(agg, cfg)

    best = agg["best_strategy_row"]
    best_single = agg["best_single"]
    print("\n=== 完成 ===")
    print(f"最强策略(平均): {best['strategy']} | 平均盈利 {_fmt_money(best['avg_profit'])}")
    print(f"最佳单次: {best_single['code']} × {best_single['strategy']} | 盈利 {_fmt_money(best_single['profit'])}")


if __name__ == "__main__":
    main()
