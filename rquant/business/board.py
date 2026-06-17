"""
rQuant.board — 板块行情业务层
- 维护板块名 → ETF 代码的映射（SECTOR_ETFS）
- 行情数据走 DataSourcePool（rquant.data_source）
- 业务层缓存 2 分钟
- 对外 API：fetch_sector_boards / fetch_concept_boards / fetch_board_stocks
"""

from __future__ import annotations
import sys
import time
from datetime import datetime

from rquant.data_source import pool

# ============== 板块 ETF 池 ==============
# Sina 不暴露真实"行业板块"或"概念板块"成分股接口；
# 用 ETF 行情做板块代理，同一份池子被行业 / 概念两个 tab 共用。

SECTOR_ETFS: list[dict[str, str]] = [
    {"code": "sh512480", "name": "半导体"},
    {"code": "sh512800", "name": "银行"},
    {"code": "sh512880", "name": "证券"},
    {"code": "sh512690", "name": "白酒"},
    {"code": "sz159928", "name": "消费"},
    {"code": "sh512010", "name": "医药"},
    {"code": "sh516160", "name": "新能源"},
    {"code": "sh515790", "name": "光伏"},
    {"code": "sh512660", "name": "军工"},
    {"code": "sh512200", "name": "房地产"},
    {"code": "sz159611", "name": "电力"},
    {"code": "sh515210", "name": "钢铁"},
    {"code": "sh512400", "name": "有色金属"},
    {"code": "sz159865", "name": "养殖"},
    {"code": "sh561230", "name": "化工"},
    {"code": "sh510050", "name": "上证50"},
    {"code": "sh510300", "name": "沪深300"},
    {"code": "sh510500", "name": "中证500"},
    {"code": "sh588000", "name": "科创50"},
    {"code": "sz159949", "name": "创业板50"},
    {"code": "sh515030", "name": "新能车"},
    {"code": "sh512170", "name": "医疗"},
    {"code": "sh561160", "name": "锂电池"},
    {"code": "sh515050", "name": "5G通信"},
    {"code": "sh516510", "name": "云计算"},
    {"code": "sh512100", "name": "中证1000"},
    {"code": "sz159766", "name": "旅游"},
    {"code": "sh516970", "name": "基建"},
    {"code": "sh516090", "name": "新材料"},
    {"code": "sh515880", "name": "通信"},
]

# ============== 业务层缓存 ==============

CACHE_TTL = 120  # 秒（盘中快速刷新）

_cache: dict[str, tuple] = {}  # key → (data, timestamp)


def _log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    sys.stderr.write(f"[{ts}] [board] {msg}\n")
    sys.stderr.flush()


def _cached(key: str):
    if key in _cache:
        data, ts = _cache[key]
        if time.time() - ts < CACHE_TTL:
            return data
    return None


def _set_cache(key: str, data):
    _cache[key] = (data, time.time())


# ============== 公开接口 ==============


def _build_boards_response(board_type: str, top_n: int) -> list[dict]:
    """从数据池拉所有 SECTOR_ETFS 行情，按涨幅降序返回。"""
    cache_key = f"boards_{board_type}"
    cached = _cached(cache_key)
    if cached is not None:
        _log(f"{board_type} 板块: 命中缓存, {len(cached)} 条")
        return cached[:top_n]

    codes = [e["code"] for e in SECTOR_ETFS]
    name_map = {e["code"]: e["name"] for e in SECTOR_ETFS}

    quotes = pool.fetch_quotes(codes)
    if not quotes:
        _log(f"{board_type} 板块: 数据源返回空")
        return []

    rows: list[dict] = []
    for code in codes:
        item = quotes.get(code)
        if not item:
            continue
        # 用业务映射的板块名覆盖 Sina 返回的 ETF 自身名
        rows.append({**item, "name": name_map.get(code, item["name"])})

    rows.sort(key=lambda x: x["change_pct"], reverse=True)
    _log(f"{board_type} 板块: 刷新完成, {len(rows)} 只 ETF")
    _set_cache(cache_key, rows)
    return rows[:top_n]


def fetch_sector_boards(top_n: int = 30) -> list[dict]:
    """获取行业板块排行（按涨幅降序）"""
    return _build_boards_response("sector", top_n)


def fetch_concept_boards(top_n: int = 30) -> list[dict]:
    """获取概念板块排行（按涨幅降序）"""
    return _build_boards_response("concept", top_n)


def fetch_board_stocks(board_code: str, top_n: int = 20) -> list[dict]:
    """获取板块「成分股」——Sina 方案下只能返回该 ETF 自身详情"""
    cache_key = f"stocks_{board_code}"
    cached = _cached(cache_key)
    if cached is not None:
        return cached[:top_n]

    item = pool.fetch_quote(board_code)
    if item is None:
        _log(f"成分股 {board_code}: 数据源返回空")
        return []

    result = [
        {
            **item,
            "turnover": 0,
            "pe": 0,
        }
    ]
    _set_cache(cache_key, result)
    return result[:top_n]
