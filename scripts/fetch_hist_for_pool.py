#!/usr/bin/env python
"""数据准备：读取股票池或代码列表，调用现有 fetch_hist 逻辑拉取并落盘。"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.fetch_hist import fetch_one  # noqa: E402


def _codes_from_args(args: argparse.Namespace) -> list[str]:
    codes = list(args.codes or [])
    if args.pool_file:
        payload = json.loads(Path(args.pool_file).read_text(encoding="utf-8"))
        codes.extend([row["code"] for row in payload.get("stocks", []) if row.get("code")])
    seen: set[str] = set()
    result: list[str] = []
    for code in codes:
        if code not in seen:
            result.append(code)
            seen.add(code)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="按股票池拉取历史日频数据，复用 scripts/fetch_hist.py")
    parser.add_argument("codes", nargs="*", help="股票代码列表，如 sh600519")
    parser.add_argument("--pool-file", default="", help="select_board_pool.py 输出的 JSON")
    parser.add_argument("--from", dest="start", default=None, help="起始日期 YYYY-MM-DD")
    parser.add_argument("--to", dest="end", default=None, help="结束日期 YYYY-MM-DD；可到当天或测试结束日之后")
    parser.add_argument("--limit", type=int, default=0, help="仅拉前 N 只，用于烟测")
    parser.add_argument("--delay", type=float, default=2.0, help="每只之间间隔秒数，避免限流")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    codes = _codes_from_args(args)
    if args.limit > 0:
        codes = codes[: args.limit]
    if not codes:
        raise RuntimeError("没有可拉取的股票代码")

    ok = 0
    for i, code in enumerate(codes, 1):
        print(f"[{i}/{len(codes)}] fetch {code} {args.start or '-inf'} ~ {args.end or '+inf'}")
        rows = fetch_one(code, args.start, args.end)
        if rows > 0:
            ok += 1
        if i < len(codes):
            time.sleep(args.delay)
    print(f"done: success={ok}, total={len(codes)}")


if __name__ == "__main__":
    main()
