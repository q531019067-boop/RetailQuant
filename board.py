"""
rQuant.board — 板块行情数据层
- 通过 Sina 行情 API 获取行业 ETF 实时数据
- 行业 / 概念 复用同一份 ETF 池（底层数据源相同，差异化交给前端标签）
- 2 分钟内存缓存（盘中快速刷新）
"""

from __future__ import annotations
import re
import sys
import time
from datetime import datetime

import requests

SINA_QUOTE_API = "https://hq.sinajs.cn/list="
SINA_HEADERS = {"Referer": "https://finance.sina.com.cn/"}

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

# ============== 缓存 ==============

_cache: dict[str, tuple] = {}  # key → (data, timestamp)
CACHE_TTL = 120  # 秒


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


# ============== Sina 行情解析 ==============


def _parse_sina_quote_line(code: str, text: str, fallback_name: str) -> dict | None:
    """从 Sina 批量返回的文本中解析单只 ETF 行情"""
    pattern = rf'var hq_str_{code}="([^"]*)"'
    m = re.search(pattern, text)
    if not m:
        return None
    fields = m.group(1).split(",")
    if len(fields) < 4:
        return None
    try:
        prev_close = float(fields[2])
        current = float(fields[3])
    except (ValueError, IndexError):
        return None
    if prev_close <= 0:
        return None
    return {
        "code": code,
        "name": fallback_name or fields[0],
        "price": round(current, 3),
        "change_pct": round((current - prev_close) / prev_close * 100, 2),
        "change_amt": round(current - prev_close, 3),
    }


def _fetch_etf_quotes(etf_list: list[dict[str, str]]) -> list[dict]:
    """批量拉取 ETF 实时行情（Sina API）"""
    if not etf_list:
        return []
    codes = [e["code"] for e in etf_list]
    url = SINA_QUOTE_API + ",".join(codes)
    try:
        r = requests.get(url, headers=SINA_HEADERS, timeout=8)
        if r.status_code != 200:
            _log(f"Sina ETF 行情请求失败: HTTP {r.status_code}")
            return []
    except Exception as e:
        _log(f"Sina ETF 行情异常: {e}")
        return []

    results = []
    for etf in etf_list:
        item = _parse_sina_quote_line(etf["code"], r.text, etf["name"])
        if item is not None:
            results.append(item)
        else:
            _log(f"Sina ETF 未找到: {etf['code']}")
    return results


# ============== 公开接口 ==============


def fetch_boards(board_type: str = "sector", top_n: int = 30) -> list[dict]:
    """获取板块排行（按涨幅降序）

    board_type 暂作 cache key 区分，行业/概念底层用同一份 ETF 池。
    """
    cache_key = f"boards_{board_type}"
    cached = _cached(cache_key)
    if cached is not None:
        _log(f"{board_type} 板块: 命中缓存, {len(cached)} 条")
        return cached[:top_n]

    data = _fetch_etf_quotes(SECTOR_ETFS)
    data.sort(key=lambda x: x["change_pct"], reverse=True)
    if not data:
        _log(f"{board_type} 板块: 返回空数据")
    else:
        _log(f"{board_type} 板块: 刷新完成, {len(data)} 只 ETF")
    _set_cache(cache_key, data)
    return data[:top_n]


# 向后兼容的薄包装（历史 API 名字保留）
def fetch_sector_boards(top_n: int = 30) -> list[dict]:
    return fetch_boards("sector", top_n)


def fetch_concept_boards(top_n: int = 30) -> list[dict]:
    return fetch_boards("concept", top_n)


def fetch_board_stocks(board_code: str, top_n: int = 20) -> list[dict]:
    """获取板块「成分股」——Sina 方案下只能返回该 ETF 自身"""
    cache_key = f"stocks_{board_code}"
    cached = _cached(cache_key)
    if cached is not None:
        return cached[:top_n]

    try:
        r = requests.get(SINA_QUOTE_API + board_code, headers=SINA_HEADERS, timeout=8)
        if r.status_code != 200:
            _log(f"成分股 {board_code}: HTTP {r.status_code}")
            return []

        pattern = rf'var hq_str_{board_code}="([^"]*)"'
        m = re.search(pattern, r.text)
        if not m:
            return []

        fields = m.group(1).split(",")
        if len(fields) < 4:
            return []

        name = fields[0]
        prev_close = float(fields[2])
        current = float(fields[3])
        result = [
            {
                "code": board_code,
                "name": name,
                "price": round(current, 3),
                "change_pct": round((current - prev_close) / prev_close * 100, 2),
                "change_amt": round(current - prev_close, 3),
                "turnover": 0,
                "pe": 0,
            }
        ]
        _set_cache(cache_key, result)
        return result[:top_n]
    except Exception as e:
        _log(f"成分股 {board_code}: 异常 {e}")
    return []
