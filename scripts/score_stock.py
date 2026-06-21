#!/usr/bin/env python
"""步骤 2（多策略评分）：针对单只股票和指定日期，按 lookback 历史计算多策略得分与买卖信号。"""

from __future__ import annotations

import argparse
import sys
from dataclasses import asdict
from pathlib import Path
import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.fetch_hist import fetch_one  # noqa: E402
from rquant.research.workflow import DEFAULT_STRATEGIES, score_stock_strategies, write_json  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="多策略评分：严格按 as-of 日期切片，防未来函数")
    parser.add_argument("--code", required=True, help="股票代码，如 sh600519")
    parser.add_argument("--as-of", required=True, help="决策日期 YYYY-MM-DD")
    parser.add_argument("--lookback-days", type=int, default=365, help="向前取多少自然日历史")
    parser.add_argument("--name", default="", help="股票名称")
    parser.add_argument("--sector", default="", help="所属板块")
    parser.add_argument("--strategies", nargs="+", default=list(DEFAULT_STRATEGIES), help="策略名称列表")
    parser.add_argument("--position-avg-cost", type=float, default=0.0, help="可选：持仓均价，用于计算卖出信号")
    parser.add_argument("--position-shares", type=int, default=0, help="可选：持仓股数，用于计算卖出信号")
    parser.add_argument("--fetch-missing", action="store_true", help="评分前先调用 scripts/fetch_hist.py 拉取并落盘")
    parser.add_argument("--fetch-to", default="", help="拉数截止日；默认等于 --as-of，可传到测试结束日或当天")
    parser.add_argument("--out", default="", help="输出 JSON 路径")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    position = None
    if args.position_avg_cost > 0 and args.position_shares > 0:
        position = {
            "avg_cost": args.position_avg_cost,
            "shares": args.position_shares,
            "cost": args.position_avg_cost * args.position_shares,
        }
    if args.fetch_missing:
        fetch_start = (pd.Timestamp(args.as_of) - pd.Timedelta(days=args.lookback_days)).strftime("%Y-%m-%d")
        fetch_one(args.code, fetch_start, args.fetch_to or args.as_of)
    scores = score_stock_strategies(
        code=args.code,
        as_of=args.as_of,
        lookback_days=args.lookback_days,
        strategies=args.strategies,
        name=args.name or args.code,
        sector=args.sector,
        position=position,
        allow_fetch=args.fetch_missing,
    )
    payload = {
        "code": args.code,
        "name": args.name or args.code,
        "as_of": args.as_of,
        "lookback_days": args.lookback_days,
        "scores": [asdict(x) for x in scores],
    }
    out = Path(args.out or f"results/research/score_{args.code}_{args.as_of}.json")
    write_json(out, payload)
    print(f"score_count={len(scores)} json={out}")
    for score in scores:
        print(
            f"{score.strategy:20s} action={score.action:8s} score={score.score:+.4f} confidence={score.confidence:.1f}"
        )


if __name__ == "__main__":
    main()
