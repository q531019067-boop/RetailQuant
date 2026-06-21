#!/usr/bin/env python
"""步骤 3：在时间范围内对候选池反复评分并模拟炒股，比较策略表现。"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from rquant.backtest import BrokerConfig  # noqa: E402
from scripts.fetch_hist import fetch_one  # noqa: E402
from rquant.research.workflow import (  # noqa: E402
    DEFAULT_STRATEGIES,
    select_liquid_board_pool,
    simulate_strategy_pool,
    write_json,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="组合模拟：候选池 -> 多策略评分 -> 模拟成交与收益对比")
    parser.add_argument("--start", required=True, help="回测开始日期 YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="回测结束日期 YYYY-MM-DD")
    parser.add_argument("--capital", type=float, default=100_000.0, help="本金")
    parser.add_argument("--pool-file", default="", help="第一步输出的股票池 JSON；不传则按 start 自动选池")
    parser.add_argument("--board-limit", type=int, default=20, help="自动选池时的板块数量")
    parser.add_argument("--stocks-per-board", type=int, default=6, help="自动选池时每板块股票数量")
    parser.add_argument(
        "--board-type", default="sector", choices=["sector", "concept", "area"], help="自动选池板块类型"
    )
    parser.add_argument("--board-keywords", nargs="*", default=[], help="板块名称关键词范围")
    parser.add_argument("--board-codes", nargs="*", default=[], help="板块代码范围")
    parser.add_argument("--strategies", nargs="+", default=list(DEFAULT_STRATEGIES), help="策略名称列表")
    parser.add_argument("--lookback-days", type=int, default=365, help="每个决策日向前取多少自然日历史")
    parser.add_argument("--max-positions", type=int, default=5, help="组合最大持仓数")
    parser.add_argument("--out-dir", default="results/research/simulation", help="输出目录")
    parser.add_argument("--commission-rate", type=float, default=0.00025)
    parser.add_argument("--stamp-tax-rate", type=float, default=0.0005)
    parser.add_argument("--slippage-bp", type=float, default=1.0)
    parser.add_argument(
        "--fetch-missing", action="store_true", help="模拟前先调用 scripts/fetch_hist.py 为股票池拉数并落盘"
    )
    parser.add_argument("--fetch-to", default="", help="拉数截止日；默认等于 --end，可传到当天")
    parser.add_argument("--fetch-delay", type=float, default=2.0, help="拉数间隔秒数")
    parser.add_argument("--fetch-limit", type=int, default=0, help="仅拉前 N 只，用于烟测")
    return parser


def _load_pool(args: argparse.Namespace) -> list[dict]:
    if args.pool_file:
        payload = json.loads(Path(args.pool_file).read_text(encoding="utf-8"))
        return payload.get("stocks", [])
    selection = select_liquid_board_pool(
        as_of=args.start,
        board_limit=args.board_limit,
        stocks_per_board=args.stocks_per_board,
        board_type=args.board_type,
        board_keywords=args.board_keywords,
        board_codes=args.board_codes,
    )
    return selection.stocks


def main() -> None:
    args = build_parser().parse_args()
    pool = _load_pool(args)
    if not pool:
        raise RuntimeError("股票池为空，无法模拟")

    if args.fetch_missing:
        fetch_start = (pd.Timestamp(args.start) - pd.Timedelta(days=args.lookback_days)).strftime("%Y-%m-%d")
        fetch_pool = pool[: args.fetch_limit] if args.fetch_limit > 0 else pool
        for i, row in enumerate(fetch_pool, 1):
            code = row["code"]
            print(f"[fetch {i}/{len(fetch_pool)}] {code} {fetch_start} ~ {args.fetch_to or args.end}")
            fetch_one(code, fetch_start, args.fetch_to or args.end)
            if i < len(fetch_pool):
                time.sleep(args.fetch_delay)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    broker = BrokerConfig(
        commission_rate=args.commission_rate,
        stamp_tax_rate=args.stamp_tax_rate,
        slippage_bp=args.slippage_bp,
    )

    summaries: list[dict] = []
    for strategy_name in args.strategies:
        result = simulate_strategy_pool(
            pool=pool,
            start=args.start,
            end=args.end,
            strategy_name=strategy_name,
            capital=args.capital,
            lookback_days=args.lookback_days,
            max_positions=args.max_positions,
            broker=broker,
        )
        summary = {k: v for k, v in result.items() if k not in {"trades", "equity_curve", "skipped"}}
        summaries.append(summary)
        prefix = out_dir / strategy_name
        pd.DataFrame(result["trades"]).to_csv(f"{prefix}_trades.csv", index=False)
        pd.DataFrame(result["equity_curve"]).to_csv(f"{prefix}_equity.csv", index=False)
        write_json(Path(f"{prefix}_summary.json"), summary)

    matrix = pd.DataFrame(summaries).sort_values(["annual_return_pct", "max_drawdown_pct"], ascending=[False, False])
    matrix_path = out_dir / "strategy_matrix.csv"
    matrix.to_csv(matrix_path, index=False)
    write_json(out_dir / "pool_used.json", {"stocks": pool})
    print(matrix.to_string(index=False))
    print(f"out_dir={out_dir}")
    print(f"matrix={matrix_path}")


if __name__ == "__main__":
    main()
