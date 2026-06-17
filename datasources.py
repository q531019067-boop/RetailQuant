"""
rQuant.datasources — 数据源池
- 抽象层：KlineSource / QuoteSource Protocol
- 实现：SinaKlineSource / SinaQuoteSource（默认）
- 池：DataSourcePool — 优先级路由、健康度跟踪、自动 failover
- 旧业务代码（data.py / board.py）通过 `pool` 单例访问，签名不变
"""

from __future__ import annotations
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Protocol

import pandas as pd
import requests

CACHE_DIR = Path(__file__).parent / "data"
CACHE_DIR.mkdir(exist_ok=True)

SINA_KLINE_URL = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
SINA_QUOTE_URL = "https://hq.sinajs.cn/list="
SINA_HEADERS = {"Referer": "https://finance.sina.com.cn/"}

STALE_DAYS = 5
PRICE_COLS = ("open", "high", "low", "close", "volume")
DEFAULT_TIMEOUT = 8

# 单源失败后冷却时间（秒）—— 避免短时间内反复打
UNHEALTHY_COOLDOWN = 60


# ============== 数据源协议 ==============


class KlineSource(Protocol):
    name: str

    def fetch(self, code: str, days: int) -> list[dict]: ...
    def healthy(self) -> bool: ...


class QuoteSource(Protocol):
    name: str

    def fetch(self, code: str) -> dict | None: ...
    def fetch_batch(self, codes: list[str]) -> dict[str, dict]: ...
    def healthy(self) -> bool: ...


# ============== Sina K 线源 ==============


class SinaKlineSource:
    """Sina K 线源 + 本地 JSON 缓存"""

    name = "sina_kline"

    def __init__(self, cache_dir: Path = CACHE_DIR, timeout: int = DEFAULT_TIMEOUT):
        self.cache_dir = cache_dir
        self.timeout = timeout
        self._unhealthy_until = 0.0

    def _cache_path(self, code: str) -> Path:
        return self.cache_dir / f"{code}.json"

    def _read_cache(self, code: str) -> list[dict]:
        p = self._cache_path(code)
        if not p.exists():
            return []
        try:
            return json.loads(p.read_text())
        except Exception:
            return []

    def _write_cache(self, code: str, rows: list[dict]) -> None:
        self._cache_path(code).write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")

    def _need_refresh(self, cached: list[dict]) -> bool:
        if not cached:
            return True
        try:
            last_dt = datetime.strptime(cached[-1].get("day", ""), "%Y-%m-%d")
            return (datetime.now() - last_dt).days >= STALE_DAYS
        except ValueError:
            return True

    def fetch(self, code: str, days: int = 250) -> list[dict]:
        """拉 K 线 + JSON 缓存。返回原始行（{day, open, high, low, close, volume}）。"""
        cached = self._read_cache(code)
        if not self._need_refresh(cached):
            return cached[-days:]

        try:
            url = f"{SINA_KLINE_URL}?symbol={code}&scale=240&ma=no&datalen={days}"
            r = requests.get(url, timeout=self.timeout)
            if r.status_code == 200 and r.text.strip():
                fresh = r.json()
                if isinstance(fresh, list) and fresh:
                    existing_dates = {x.get("day") for x in cached}
                    merged = list(cached)
                    for row in fresh:
                        if row.get("day") not in existing_dates:
                            merged.append(row)
                    merged.sort(key=lambda x: x.get("day", ""))
                    merged = merged[-days:]
                    self._write_cache(code, merged)
                    self._unhealthy_until = 0.0
                    return merged
        except Exception:
            self._unhealthy_until = time.time() + UNHEALTHY_COOLDOWN
        return cached[-days:] if cached else []

    def healthy(self) -> bool:
        return time.time() > self._unhealthy_until


# ============== Sina 行情源 ==============


class SinaQuoteSource:
    """Sina 实时行情源 + 短窗口批量缓存（防限流）"""

    name = "sina_quote"
    BATCH_TTL = 30.0  # 同 code 复用窗口（秒）

    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        self.timeout = timeout
        self._unhealthy_until = 0.0
        self._batch_cache: dict[str, tuple[dict, float]] = {}  # code -> (data, ts)

    def fetch_batch(self, codes: list[str]) -> dict[str, dict]:
        """批量拉行情，返回 {code: {...}}。已拉过且未过期的 code 复用。"""
        if not codes:
            return {}
        now = time.time()
        result: dict[str, dict] = {}
        to_fetch: list[str] = []
        for c in codes:
            cached = self._batch_cache.get(c)
            if cached and now - cached[1] < self.BATCH_TTL:
                result[c] = cached[0]
            else:
                to_fetch.append(c)

        if to_fetch:
            try:
                url = SINA_QUOTE_URL + ",".join(to_fetch)
                r = requests.get(url, headers=SINA_HEADERS, timeout=self.timeout)
                if r.status_code == 200:
                    for c in to_fetch:
                        item = self._parse_line(c, r.text)
                        if item is not None:
                            self._batch_cache[c] = (item, now)
                            result[c] = item
                    self._unhealthy_until = 0.0
            except Exception:
                self._unhealthy_until = time.time() + UNHEALTHY_COOLDOWN
        return result

    def fetch(self, code: str) -> dict | None:
        return self.fetch_batch([code]).get(code)

    def _parse_line(self, code: str, text: str) -> dict | None:
        m = re.search(rf'var hq_str_{code}="([^"]*)"', text)
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
            "name": fields[0],
            "price": round(current, 3),
            "change_pct": round((current - prev_close) / prev_close * 100, 2),
            "change_amt": round(current - prev_close, 3),
        }

    def healthy(self) -> bool:
        return time.time() > self._unhealthy_until


# ============== 数据源池 ==============


class DataSourcePool:
    """管理多个 K 线 / 行情源，按优先级和健康度路由，自动 failover"""

    def __init__(self):
        self._kline: list[KlineSource] = [SinaKlineSource()]
        self._quote: list[QuoteSource] = [SinaQuoteSource()]

    # ----- 注册源 -----

    def add_kline(self, source: KlineSource, priority: int = 0) -> None:
        """priority 越小越优先"""
        self._kline.insert(min(priority, len(self._kline)), source)

    def add_quote(self, source: QuoteSource, priority: int = 0) -> None:
        self._quote.insert(min(priority, len(self._quote)), source)

    # ----- K 线 -----

    def fetch_kline(self, code: str, days: int = 250) -> list[dict]:
        last_err: Exception | None = None
        for src in self._kline:
            if not src.healthy():
                continue
            try:
                rows = src.fetch(code, days)
                if rows:
                    return rows
            except Exception as e:
                last_err = e
        if last_err:
            raise last_err
        return []

    def to_dataframe(self, code: str, days: int = 250) -> pd.DataFrame:
        """便捷：fetch_kline + 转 DataFrame（列：date, open, high, low, close, volume）"""
        rows = self.fetch_kline(code, days)
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows).rename(columns={"day": "date"})
        df[list(PRICE_COLS)] = df[list(PRICE_COLS)].apply(pd.to_numeric, errors="coerce")
        return df[["date", *PRICE_COLS]]

    # ----- 行情 -----

    def fetch_quote(self, code: str) -> dict | None:
        for src in self._quote:
            if not src.healthy():
                continue
            try:
                item = src.fetch(code)
                if item is not None:
                    return item
            except Exception:
                continue
        return None

    def fetch_quotes(self, codes: list[str]) -> dict[str, dict]:
        """批量拉行情：走优先级最高的健康源"""
        for src in self._quote:
            if not src.healthy():
                continue
            try:
                result = src.fetch_batch(codes)
                if result:
                    return result
            except Exception:
                continue
        return {}

    # ----- 健康度面板 -----

    def status(self) -> dict:
        return {
            "kline": [{"name": s.name, "healthy": s.healthy()} for s in self._kline],
            "quote": [{"name": s.name, "healthy": s.healthy()} for s in self._quote],
        }


# 全局单例
pool = DataSourcePool()
