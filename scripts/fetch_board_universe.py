#!/usr/bin/env python
"""
scripts/fetch_board_universe.py — 拉取 A 股索引与板块/概念目录 → .tab 表

数据源：东方财富 push2 接口（trust_env=False 直连，与 rquant.business.board 一致）

输出（默认 data/boards/）：
  Stocks.tab        — 全 A 股代码、名称、市场分类（用于快速检索/筛选）
  Boards.tab        — 行业/概念/地域板块目录
  StockBoardRel.tab — 个股 ↔ 板块/概念 全量关联（可选；合并后写入 Stocks.tab）

Stocks.tab 合并字段（来自关联表，`|` 分隔多值）：
  sectors, sector_codes, concepts, concept_codes

用法：
  python scripts/fetch_board_universe.py              # 拉股票 + 板块目录
  python scripts/fetch_board_universe.py --stocks-only
  python scripts/fetch_board_universe.py --boards-only --types sector concept
  python scripts/fetch_board_universe.py --relations-only   # 仅重建关联表（约 4-5 分钟）
  python scripts/fetch_board_universe.py --merge-stocks     # 将 StockBoardRel 合并进 Stocks.tab
  python scripts/fetch_board_universe.py --summary
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

_PROJ_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJ_ROOT))

from rquant.business.board import BOARD_TYPES, EAST_MONEY_URL  # noqa: E402

DEFAULT_OUT_DIR = _PROJ_ROOT / "data" / "boards"
PAGE_SIZE = 100
DEFAULT_REL_DELAY = 0.2
LIST_SEP = "|"

STOCKS_HEADER = [
    "code",
    "name",
    "market",
    "market_name",
    "sectors",
    "sector_codes",
    "concepts",
    "concept_codes",
    "updated_at",
]

# 沪A + 深A（含主板/创业板/科创板/北交所）
ALL_A_SHARE_FS = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"

BOARD_TYPE_LABEL = {
    "sector": "行业",
    "concept": "概念",
    "area": "地域",
}

MARKET_LABEL = {
    "sh_main": "上证主板",
    "star": "科创板",
    "sz_main": "深证主板",
    "chinext": "创业板",
    "bj": "北交所",
    "other": "其他",
}

_session = requests.Session()
_session.headers.update(
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://quote.eastmoney.com/",
    }
)
_session.trust_env = False
_retry = Retry(
    total=3,
    backoff_factor=0.5,
    status_forcelist=(500, 502, 503, 504),
    allowed_methods=frozenset(["GET"]),
    raise_on_status=False,
)
_adapter = HTTPAdapter(max_retries=_retry, pool_connections=4, pool_maxsize=8)
_session.mount("https://", _adapter)
_session.mount("http://", _adapter)


def _log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    sys.stderr.write(f"[{ts}] {msg}\n")
    sys.stderr.flush()


def _infer_market(code6: str) -> str:
    if not code6 or len(code6) < 2:
        return "other"
    if code6.startswith("688") or code6.startswith("689"):
        return "star"
    if code6.startswith("92"):
        return "bj"
    if code6.startswith("60") or code6.startswith("90"):
        return "sh_main"
    if code6.startswith("00"):
        return "sz_main"
    if code6.startswith("30"):
        return "chinext"
    if code6.startswith("4") or code6.startswith("8"):
        return "bj"
    return "other"


def _to_stock_code(code6: str) -> str:
    head = code6[0] if code6 else ""
    if head in ("6", "9"):
        return f"sh{code6}"
    return f"sz{code6}"


def _fetch_clist(fs: str, fields: str) -> list[dict]:
    rows: list[dict] = []
    page = 1
    total = None
    while True:
        params = {
            "pn": page,
            "pz": PAGE_SIZE,
            "po": 1,
            "fid": "f12",
            "fs": fs,
            "fields": fields,
        }
        r = _session.get(EAST_MONEY_URL, params=params, timeout=15)
        r.raise_for_status()
        data = r.json().get("data") or {}
        if total is None:
            total = int(data.get("total") or 0)
        diff = data.get("diff") or {}
        if not diff:
            break
        rows.extend(diff.values())
        if len(rows) >= total or len(diff) < PAGE_SIZE:
            break
        page += 1
    return rows


def fetch_all_stocks() -> list[dict]:
    _log("拉取全 A 股列表 ...")
    raw = _fetch_clist(ALL_A_SHARE_FS, "f12,f14")
    stocks: list[dict] = []
    seen: set[str] = set()
    for item in raw:
        code6 = str(item.get("f12") or "").strip()
        name = str(item.get("f14") or "").strip()
        if not code6 or not name:
            continue
        stock_code = _to_stock_code(code6)
        if stock_code in seen:
            continue
        seen.add(stock_code)
        market = _infer_market(code6)
        stocks.append(
            {
                "code": stock_code,
                "name": name,
                "market": market,
                "market_name": MARKET_LABEL.get(market, market),
            }
        )
    stocks.sort(key=lambda x: x["code"])
    _log(f"  股票: {len(stocks)} 只")
    return stocks


def fetch_board_catalog(board_type: str) -> list[dict]:
    fs = BOARD_TYPES.get(board_type)
    if not fs:
        raise ValueError(f"未知板块类型: {board_type}")
    _log(f"拉取 {BOARD_TYPE_LABEL.get(board_type, board_type)} 目录 ...")
    raw = _fetch_clist(fs, "f12,f14,f104")
    boards = []
    for item in raw:
        code = str(item.get("f12") or "").strip()
        name = str(item.get("f14") or "").strip()
        if not code or not name:
            continue
        boards.append(
            {
                "board_code": code,
                "board_name": name,
                "board_type": board_type,
                "stock_count": int(item.get("f104") or 0),
            }
        )
    _log(f"  {BOARD_TYPE_LABEL.get(board_type, board_type)}: {len(boards)} 个")
    return boards


def fetch_board_constituents(board_code: str, delay: float) -> list[dict]:
    fs = f"b:{board_code}+f:!2"
    raw = _fetch_clist(fs, "f12,f14")
    time.sleep(delay)
    stocks = []
    for item in raw:
        code6 = str(item.get("f12") or "").strip()
        name = str(item.get("f14") or "").strip()
        if not code6 or not name:
            continue
        market = _infer_market(code6)
        stocks.append(
            {
                "stock_code": _to_stock_code(code6),
                "stock_name": name,
                "market": market,
                "market_name": MARKET_LABEL.get(market, market),
            }
        )
    return stocks


def fetch_all_relations(boards: list[dict], delay: float) -> list[list]:
    rels: list[list] = []
    for i, board in enumerate(boards, 1):
        code = board["board_code"]
        name = board["board_name"]
        bt = board["board_type"]
        _log(f"  [{i}/{len(boards)}] {bt} {code} {name} ...")
        try:
            stocks = fetch_board_constituents(code, delay)
        except Exception as e:
            _log(f"    [WARN] 成分股拉取失败 {code}: {e}")
            continue
        for s in stocks:
            rels.append(
                [
                    s["stock_code"],
                    s["stock_name"],
                    s["market"],
                    s["market_name"],
                    code,
                    name,
                    bt,
                ]
            )
    _log(f"  关联记录: {len(rels)} 条")
    return rels


def load_boards_from_tab(out_dir: Path) -> list[dict]:
    _, rows = read_tab(out_dir / "Boards.tab")
    boards = []
    for row in rows:
        if len(row) < 3:
            continue
        stock_count = int(row[3]) if len(row) >= 4 and str(row[3]).isdigit() else 0
        boards.append(
            {
                "board_code": row[0],
                "board_name": row[1],
                "board_type": row[2],
                "stock_count": stock_count,
            }
        )
    return boards


def _join_boards(pairs: list[tuple[str, str]]) -> tuple[str, str]:
    if not pairs:
        return "", ""
    codes, names = zip(*pairs)
    return LIST_SEP.join(codes), LIST_SEP.join(names)


def aggregate_relations(rels: list[list]) -> dict[str, dict[str, list[tuple[str, str]]]]:
    grouped: dict[str, dict[str, list[tuple[str, str]]]] = defaultdict(
        lambda: {"sector": [], "concept": [], "area": []}
    )
    seen: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for row in rels:
        if len(row) < 7:
            continue
        stock_code, _, _, _, board_code, board_name, board_type = row[:7]
        if board_code in seen[stock_code][board_type]:
            continue
        seen[stock_code][board_type].add(board_code)
        grouped[stock_code][board_type].append((board_code, board_name))
    return grouped


def merge_stocks_tab(out_dir: Path, updated_at: str | None = None) -> int:
    stocks_path = out_dir / "Stocks.tab"
    rel_path = out_dir / "StockBoardRel.tab"
    if not stocks_path.exists():
        raise FileNotFoundError(f"缺少 {stocks_path}")
    if not rel_path.exists():
        raise FileNotFoundError(f"缺少 {rel_path}")

    _, stock_rows = read_tab(stocks_path)
    _, rel_rows = read_tab(rel_path)
    grouped = aggregate_relations(rel_rows)
    ts = updated_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    merged: list[list] = []
    for row in stock_rows:
        code = row[0]
        name = row[1] if len(row) > 1 else ""
        market = row[2] if len(row) > 2 else ""
        market_name = row[3] if len(row) > 3 else ""
        boards = grouped.get(code, {})
        sector_codes, sectors = _join_boards(boards.get("sector", []))
        concept_codes, concepts = _join_boards(boards.get("concept", []))
        merged.append(
            [
                code,
                name,
                market,
                market_name,
                sectors,
                sector_codes,
                concepts,
                concept_codes,
                ts,
            ]
        )

    write_tab(stocks_path, STOCKS_HEADER, merged)
    with_boards = sum(1 for r in merged if r[4] or r[6])
    _log(f"合并完成: {len(merged)} 只，其中 {with_boards} 只有板块/概念")
    return len(merged)


def write_tab(path: Path, header: list[str], rows: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["\t".join(header)]
    for row in rows:
        lines.append("\t".join(str(v) for v in row))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _log(f"写入 {path} ({len(rows)} 行)")


def read_tab(path: Path) -> tuple[list[str], list[list[str]]]:
    text = path.read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return [], []
    header = lines[0].split("\t")
    rows = [ln.split("\t") for ln in lines[1:]]
    return header, rows


def print_summary(out_dir: Path) -> None:
    stocks_path = out_dir / "Stocks.tab"
    boards_path = out_dir / "Boards.tab"

    if stocks_path.exists():
        _, stock_rows = read_tab(stocks_path)
        market_counter: Counter[str] = Counter()
        for row in stock_rows:
            if len(row) >= 3:
                market_counter[row[2]] += 1
        print("\n========== 股票索引 ==========")
        print(f"  总计: {len(stock_rows)} 只")
        for market in ("sh_main", "star", "sz_main", "chinext", "bj", "other"):
            n = market_counter.get(market, 0)
            if n:
                print(f"  {MARKET_LABEL.get(market, market)} ({market}): {n} 只")
    else:
        print("\n  [缺少 Stocks.tab]")

    if boards_path.exists():
        _, board_rows = read_tab(boards_path)
        by_type: Counter[str] = Counter()
        for row in board_rows:
            if len(row) >= 3:
                by_type[row[2]] += 1
        print("\n========== 板块/概念目录 ==========")
        for bt in ("sector", "concept", "area"):
            n = by_type.get(bt, 0)
            if n:
                print(f"  {BOARD_TYPE_LABEL.get(bt, bt)} ({bt}): {n} 个")
    else:
        print("\n  [缺少 Boards.tab]")

    rel_path = out_dir / "StockBoardRel.tab"
    if rel_path.exists():
        _, rel_rows = read_tab(rel_path)
        rel_by_type: Counter[str] = Counter()
        stock_codes: set[str] = set()
        for row in rel_rows:
            if len(row) < 7:
                continue
            stock_codes.add(row[0])
            rel_by_type[row[6]] += 1
        print("\n========== 个股-板块关联 ==========")
        print(f"  关联记录: {len(rel_rows)} 条")
        print(f"  去重股票: {len(stock_codes)} 只")
        for bt in ("sector", "concept", "area"):
            n = rel_by_type.get(bt, 0)
            if n:
                print(f"  {BOARD_TYPE_LABEL.get(bt, bt)}: {n} 条")


def run_fetch(
    out_dir: Path,
    fetch_stocks: bool,
    fetch_boards: bool,
    fetch_relations: bool,
    board_types: list[str],
    rel_delay: float,
) -> None:
    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if fetch_stocks:
        stocks = fetch_all_stocks()
        write_tab(
            out_dir / "Stocks.tab",
            ["code", "name", "market", "market_name", "updated_at"],
            [[s["code"], s["name"], s["market"], s["market_name"], updated_at] for s in stocks],
        )
        if (out_dir / "StockBoardRel.tab").exists():
            merge_stocks_tab(out_dir, updated_at)

    all_boards: list[dict] = []
    if fetch_boards:
        for bt in board_types:
            all_boards.extend(fetch_board_catalog(bt))
        write_tab(
            out_dir / "Boards.tab",
            ["board_code", "board_name", "board_type", "stock_count", "updated_at"],
            [[b["board_code"], b["board_name"], b["board_type"], b["stock_count"], updated_at] for b in all_boards],
        )
    elif fetch_relations and (out_dir / "Boards.tab").exists():
        all_boards = load_boards_from_tab(out_dir)
        _log(f"从 Boards.tab 读取 {len(all_boards)} 个板块")

    if fetch_relations:
        if not all_boards:
            for bt in board_types:
                all_boards.extend(fetch_board_catalog(bt))
        _log(f"拉取成分股关联（{len(all_boards)} 个板块，间隔 {rel_delay}s）...")
        rels = fetch_all_relations(all_boards, rel_delay)
        write_tab(
            out_dir / "StockBoardRel.tab",
            [
                "stock_code",
                "stock_name",
                "market",
                "market_name",
                "board_code",
                "board_name",
                "board_type",
            ],
            rels,
        )
        merge_stocks_tab(out_dir, updated_at)

    print_summary(out_dir)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="拉取 A 股索引与板块/概念目录 → .tab",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), help="输出目录")
    parser.add_argument(
        "--types",
        nargs="+",
        choices=list(BOARD_TYPES.keys()),
        default=["sector", "concept"],
        help="板块目录类型（默认 sector concept）",
    )
    parser.add_argument("--stocks-only", action="store_true", help="仅拉股票索引")
    parser.add_argument("--boards-only", action="store_true", help="仅拉板块目录")
    parser.add_argument(
        "--relations-only",
        action="store_true",
        help="仅重建 StockBoardRel.tab（优先读已有 Boards.tab）",
    )
    parser.add_argument(
        "--with-relations",
        action="store_true",
        help="同时拉取个股-板块全量关联（耗时长）",
    )
    parser.add_argument(
        "--rel-delay",
        type=float,
        default=DEFAULT_REL_DELAY,
        help=f"拉成分股时请求间隔秒数（默认 {DEFAULT_REL_DELAY}）",
    )
    parser.add_argument(
        "--merge-stocks",
        action="store_true",
        help="将 StockBoardRel.tab 的板块/概念字段合并进 Stocks.tab",
    )
    parser.add_argument("--summary", action="store_true", help="仅统计已有 tab")
    args = parser.parse_args()
    out_dir = Path(args.out_dir)

    if args.summary:
        print_summary(out_dir)
        return

    if args.merge_stocks:
        _log(f"合并目录: {out_dir}")
        merge_stocks_tab(out_dir)
        print_summary(out_dir)
        return

    exclusive = sum([args.stocks_only, args.boards_only, args.relations_only])
    if exclusive > 1:
        parser.error("--stocks-only / --boards-only / --relations-only 不能同时使用")

    if args.relations_only:
        fetch_stocks = fetch_boards = False
        fetch_relations = True
    else:
        fetch_stocks = not args.boards_only
        fetch_boards = not args.stocks_only
        fetch_relations = args.with_relations

    _log(f"输出目录: {out_dir}")
    t0 = time.time()
    run_fetch(out_dir, fetch_stocks, fetch_boards, fetch_relations, args.types, args.rel_delay)
    _log(f"完成，耗时 {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
