"""
rquant.review — 每日复盘模块

组件：
- analyzer: 复盘数据分析（策略扫描 + 准确性评估）
- chart:    股价折线图生成（Top-5 近 90 交易日走势）
- converter: 格式转换（JSON → Typst / HTML）
- sender:   邮件发送（SMTP）

调度：每日在 config.review.review_time 触发的定时任务线程。
"""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Any

from config import config
from rquant.log import error, info, warning

_scheduler_thread: threading.Thread | None = None
_stop_event = threading.Event()


def run_full_review(force: bool = False) -> dict[str, Any] | None:
    """执行完整复盘流程：分析 → 格式转换 → 邮件发送"""
    if not force and not config.review.enabled:
        return None

    from .analyzer import run_review
    from .converter import convert_all
    from .sender import send_report

    report = run_review()
    if report is None:
        return None
    convert_all(report["date"])
    send_report(report["date"])
    return report


def _parse_review_time() -> tuple[int, int]:
    try:
        h, m = config.review.review_time.strip().split(":")
        return int(h), int(m)
    except (ValueError, IndexError):
        warning("review", f"复盘时间格式无效: {config.review.review_time}，使用默认 15:30")
        return 15, 30


def _in_window(now: datetime, hour: int, minute: int) -> bool:
    """当前时间是否在复盘窗口内（复盘时间 ±2h）"""
    target = hour * 60 + minute
    now_m = now.hour * 60 + now.minute
    return target <= now_m <= target + 120


def _scheduler_loop() -> None:
    if not config.review.enabled:
        return

    rh, rm = _parse_review_time()
    info("review", f"复盘调度已就绪，每日 {rh:02d}:{rm:02d} 触发")
    last_triggered: datetime | None = None

    while not _stop_event.is_set():
        now = datetime.now()
        if (last_triggered is None or last_triggered.date() != now.date()) and _in_window(now, rh, rm):
            last_triggered = now
            try:
                run_full_review()
            except Exception as e:
                error("review", f"复盘执行异常: {e}")

        # 每 10 分钟检查一次
        if _stop_event.wait(timeout=600):
            break


def start_review_scheduler() -> None:
    """启动复盘调度后台线程（幂等）"""
    global _scheduler_thread
    if not config.review.enabled:
        return
    if _scheduler_thread and _scheduler_thread.is_alive():
        return
    _stop_event.clear()
    _scheduler_thread = threading.Thread(
        target=_scheduler_loop,
        daemon=True,
        name="review-scheduler",
    )
    _scheduler_thread.start()
    info("review", "复盘调度线程已启动")


def stop_review_scheduler() -> None:
    """停止复盘调度线程"""
    _stop_event.set()
    if _scheduler_thread and _scheduler_thread.is_alive():
        _scheduler_thread.join(timeout=5)
        info("review", "复盘调度线程已停止")


__all__ = [
    "run_full_review",
    "start_review_scheduler",
    "stop_review_scheduler",
]
