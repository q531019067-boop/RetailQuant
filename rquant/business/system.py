"""
rquant.business.system — 系统层信息
- 市场状态（基于当前时间的简单判断）
- 策略状态（mock：4 个内置策略 + 模拟运行/停止 + 信号数）
- 系统日志（内存 ring buffer + logging 装饰器）

注：strategy_status 当前是 mock（基于策略注册表 + 内存 dict），
   真实持久化运行时状态见 TODOLIST.md
"""

from __future__ import annotations
import logging
import threading
import time
from collections import deque
from datetime import datetime, time as dtime

from config import config

# ============== 市场状态 ==============

# A 股交易时段（含集合竞价）
TRADING_SESSIONS = [
    ("集合竞价", dtime(9, 15), dtime(9, 25)),
    ("早盘", dtime(9, 30), dtime(11, 30)),
    ("午休", dtime(11, 30), dtime(13, 0)),
    ("午盘", dtime(13, 0), dtime(15, 0)),
]


def _session_for(now: dtime) -> str:
    for name, start, end in TRADING_SESSIONS:
        if start <= now < end:
            return name
    # 9:25-9:30 中间空隙
    if dtime(9, 25) <= now < dtime(9, 30):
        return "集合竞价结束"
    return "休市"


def get_market_status() -> dict:
    """返回当前市场状态（基于 A 股交易时段判断）"""
    now = datetime.now()
    weekday = now.weekday()  # 0=Mon, 6=Sun
    time_str = now.strftime("%H:%M:%S")
    date_str = now.strftime("%Y-%m-%d")

    if weekday >= 5:
        return {
            "date": date_str,
            "time": time_str,
            "state": "休市",
            "label": "周末",
            "is_open": False,
            "next_open": "下周一 09:30",
        }

    session = _session_for(now.time())
    is_open = session in ("集合竞价", "早盘", "午盘")

    return {
        "date": date_str,
        "time": time_str,
        "state": session,
        "label": "开盘中" if is_open else "休市",
        "is_open": is_open,
        "next_open": None,
    }


# ============== 策略状态 ==============

# 内存中的运行时状态（key=strategy_name, value=signal_count/last_run/status）
_strategy_state: dict[str, dict] = {}
_strategy_lock = threading.Lock()


def _known_strategies() -> list[str]:
    """动态从 rquant.strategy.registry 拉所有已注册策略名（按 category/name 排序保证稳定）"""
    try:
        from rquant.strategy import all_strategies  # 延迟 import 避免循环

        return sorted((s.name for s in all_strategies()), key=lambda n: n)
    except Exception:
        return []


def get_strategy_status() -> list[dict]:
    """返回每个策略的运行时状态

    真实实现：策略名从 rquant.strategy.registry 动态拉（新增策略 0 配置接入）；
              信号数 + 最后运行时间由 routes.py / scan_stock 完成后调 report_strategy_run 上报。
    """
    out = []
    now = time.time()
    with _strategy_lock:
        for name in _known_strategies():
            s = _strategy_state.get(name)
            if s is None:
                # 首次出现：默认状态 running + 30 分钟内的随机 last_run（仅当 registry 没上报过）
                s = {
                    "status": "running",
                    "signals_today": 0,
                    "last_run": now - 60 * (hash(name) % 30 + 1),
                }
                _strategy_state[name] = s
            signals = s.get("signals_today", 0)
            status = s.get("status", "stopped")
            last_run = s.get("last_run")
            last_run_str = datetime.fromtimestamp(float(last_run)).strftime("%H:%M:%S") if last_run else "--:--:--"
            out.append(
                {
                    "name": name,
                    "status": status,
                    "signals_today": signals,
                    "last_run": last_run_str,
                }
            )
    return out


def report_strategy_run(name: str, signal_count: int = 0) -> None:
    """策略跑完一次时调用（更新信号数 + 最后运行时间）

    调用方（routes.py / scan_stock 等）每跑完一个策略的 signal_buy 就上报一次。
    """
    with _strategy_lock:
        prev = _strategy_state.get(name, {})
        _strategy_state[name] = {
            "status": "running",
            "signals_today": prev.get("signals_today", 0) + signal_count,
            "last_run": time.time(),
        }


# ============== 系统日志 ==============

_MAX_LOG_ENTRIES = config.business.max_log_entries
_log_buffer: deque[dict] = deque(maxlen=_MAX_LOG_ENTRIES)
_log_lock = threading.Lock()
_initialized = False


class _RingBufferHandler(logging.Handler):
    """logging.Handler 装饰器：把日志同时写进内存 ring buffer"""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            entry = {
                "ts": datetime.fromtimestamp(record.created).strftime("%H:%M:%S"),
                "level": record.levelname,
                "logger": record.name,
                "module": record.name,  # 兼容设计图的"模块"字段
                "message": self.format(record),
            }
            with _log_lock:
                _log_buffer.append(entry)
        except Exception:
            pass  # 日志系统不能因为自身 bug 挂掉


def _ensure_log_capture() -> None:
    """装一个全局 handler 到 root logger（只装一次）"""
    global _initialized
    if _initialized:
        return
    handler = _RingBufferHandler()
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    # 避免重复添加
    if not any(isinstance(h, _RingBufferHandler) for h in root.handlers):
        root.addHandler(handler)
    _initialized = True


def get_system_log(limit: int = 50) -> list[dict]:
    """返回最近 limit 条日志（最新在前）"""
    _ensure_log_capture()
    with _log_lock:
        items = list(_log_buffer)
    items.reverse()
    return items[:limit]


def log_info(module: str, message: str) -> None:
    """业务代码统一入口（替代直接 print / stderr）"""
    _ensure_log_capture()
    logging.getLogger(module).info(message)


def log_warn(module: str, message: str) -> None:
    _ensure_log_capture()
    logging.getLogger(module).warning(message)


def log_error(module: str, message: str) -> None:
    _ensure_log_capture()
    logging.getLogger(module).error(message)
