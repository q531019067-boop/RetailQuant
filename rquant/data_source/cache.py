"""
rquant.data_source.cache — 数据源缓存目录 + 通用常量
- 业务数据（portfolio.json / trades.json / watchlist.json）→ data/
- K 线 / 行情缓存 → cache/
"""

from __future__ import annotations

from config import config

# K 线 / 行情 JSON 缓存目录
CACHE_DIR = config.project_root / config.paths.cache_dir
CACHE_DIR.mkdir(exist_ok=True)

# Sina 接口常量
SINA_KLINE_URL = config.data_source.sina.kline_url
SINA_QUOTE_URL = config.data_source.sina.quote_url
SINA_HEADERS = {"Referer": config.data_source.sina.referer}

# 通用常量
STALE_DAYS = config.cache.stale_days
PRICE_COLS = ("open", "high", "low", "close", "volume")
DEFAULT_TIMEOUT = config.data_source.sina.timeout
UNHEALTHY_COOLDOWN = config.data_source.sina.unhealthy_cooldown
