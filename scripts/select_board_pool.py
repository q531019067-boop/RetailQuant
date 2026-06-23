#!/usr/bin/env python
"""步骤 1：按 as-of 日期选择高流动性、高话题度、高波动板块股票池。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from rquant.research.workflow import select_liquid_board_pool, write_json  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="板块选池：优先资金高流通性、热门、波动较大的板块")
    parser.add_argument("--as-of", required=True, help="选池日期 YYYY-MM-DD，只使用该日及以前 K 线")
    parser.add_argument("--board-limit", type=int, default=20, help="入选板块数量")
    parser.add_argument("--stocks-per-board", type=int, default=6, help="每个板块最多选几只股票")
    parser.add_argument("--board-type", default="sector", choices=["sector", "concept", "area"], help="板块类型")
    parser.add_argument("--board-keywords", nargs="*", default=[], help="板块名称关键词过滤，可多个")
    parser.add_argument("--board-codes", nargs="*", default=[], help="板块代码过滤，可多个")
    parser.add_argument("--out", default="", help="输出 JSON 路径")
    parser.add_argument("--csv", default="", help="可选：输出股票池 CSV 路径")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    selection = select_liquid_board_pool(
        as_of=args.as_of,
        board_limit=args.board_limit,
        stocks_per_board=args.stocks_per_board,
        board_type=args.board_type,
        board_keywords=args.board_keywords,
        board_codes=args.board_codes,
    )
    out = Path(args.out or f"results/research/board_pool_{args.as_of}.json")
    write_json(out, selection.__dict__)
    if args.csv:
        Path(args.csv).parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(selection.stocks).to_csv(args.csv, index=False)

    print(f"as_of={selection.as_of}")
    print(
        f"selected_boards={len(selection.boards)} selected_stocks={len(selection.stocks)} skipped={len(selection.skipped)}"
    )
    print(f"json={out}")
    if args.csv:
        print(f"csv={args.csv}")


if __name__ == "__main__":
    main()
