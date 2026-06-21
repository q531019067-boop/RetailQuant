#!/usr/bin/env python
"""对同一标的运行 MA、RSI、网格三策略对比回测。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from rquant.backtest import BacktestEngine, BrokerConfig  # noqa: E402
from rquant.business import data as business_data  # noqa: E402
from rquant.data_source import parquet_store  # noqa: E402
from rquant.strategy import get  # noqa: E402

DEFAULT_STRATEGIES = ("MovingAverageCross", "RsiMeanReversion", "GridMartingale")


def load_kline(code: str, days: int) -> pd.DataFrame:
    """优先读取 Parquet 长历史；缺失时降级到现有业务 K 线接口。"""
    df = parquet_store.read(code)
    if df is not None and not df.empty:
        return df
    return business_data.fetch_kline(code, days)


def run_compare(args: argparse.Namespace) -> pd.DataFrame:
    df = load_kline(args.code, args.days)
    if df is None or df.empty:
        raise RuntimeError(f"无法读取 {args.code} 的 K 线数据")

    broker = BrokerConfig(
        commission_rate=args.commission_rate,
        min_commission=args.min_commission,
        stamp_tax_rate=args.stamp_tax_rate,
        slippage_bp=args.slippage_bp,
        slippage_per_share=args.slippage_per_share,
        default_position_pct=args.position_pct,
        risk_free_rate=args.risk_free_rate,
    )

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    for strategy_name in args.strategies:
        strategy = get(strategy_name)
        if strategy is None:
            raise RuntimeError(f"策略未注册: {strategy_name}")

        engine = BacktestEngine(initial_capital=args.capital, broker=broker)
        result = engine.run(
            strategy=strategy,
            code=args.code,
            name=args.name or args.code,
            sector=args.sector,
            df=df,
            start_date=args.start,
            end_date=args.end,
        )

        prefix = out_dir / f"{args.code}_{strategy_name}"
        pd.DataFrame(result.fills).to_csv(f"{prefix}_trades.csv", index=False)
        pd.DataFrame(result.equity_curve).to_csv(f"{prefix}_equity.csv", index=False)
        Path(f"{prefix}_summary.json").write_text(
            json.dumps(result.summary(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        rows.append(result.summary())

    matrix = pd.DataFrame(rows)
    matrix_path = out_dir / f"{args.code}_strategy_compare.csv"
    matrix.to_csv(matrix_path, index=False)
    print(matrix.to_string(index=False))
    print(f"\n输出目录: {out_dir}")
    print(f"对比矩阵: {matrix_path}")
    return matrix


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MA / RSI / Grid 多策略对比回测")
    parser.add_argument("--code", required=True, help="股票代码，如 sh600519")
    parser.add_argument("--name", default="", help="股票名称，默认使用 code")
    parser.add_argument("--sector", default="", help="所属板块")
    parser.add_argument("--start", required=True, help="交易窗口起始日 YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="交易窗口结束日 YYYY-MM-DD")
    parser.add_argument("--capital", type=float, default=100_000.0, help="初始资金")
    parser.add_argument("--days", type=int, default=320, help="业务 K 线降级读取天数")
    parser.add_argument("--strategies", nargs="+", default=list(DEFAULT_STRATEGIES), help="策略 name 列表")
    parser.add_argument("--out", default="results/strategy_compare", help="输出目录")
    parser.add_argument("--position-pct", type=float, default=0.95, help="默认单策略最大仓位比例")
    parser.add_argument("--commission-rate", type=float, default=0.00025, help="佣金率，默认万 2.5")
    parser.add_argument("--min-commission", type=float, default=5.0, help="最低佣金")
    parser.add_argument("--stamp-tax-rate", type=float, default=0.0005, help="卖出印花税率，默认 0.05%")
    parser.add_argument("--slippage-bp", type=float, default=1.0, help="滑点 bp")
    parser.add_argument("--slippage-per-share", type=float, default=0.0, help="固定滑点，元/股")
    parser.add_argument("--risk-free-rate", type=float, default=0.02, help="年化无风险利率")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    run_compare(args)


if __name__ == "__main__":
    main()
