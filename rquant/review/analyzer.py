"""
rquant.review.analyzer — 复盘数据分析

复盘流程：
1. 从标的池获取所有股票，拉取 K 线
2. 使用所有已注册策略扫描买入信号
3. 按置信度排序取 Top-5
4. 加载历史复盘报告，对比评估准确性
5. 产出 JSON 格式报告文件（reports/{YYYY-MM-DD}.json）
"""

from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from config import config
from rquant.business import data as biz_data
from rquant.business.pool_store import get_pool
from rquant.log import debug, info, warning
from rquant.strategy import scan_stock

REPORT_DIR = config.project_root / config.review.report_dir
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def _today() -> str:
    return date.today().isoformat()


def _report_path(report_date: str) -> Path:
    return REPORT_DIR / f"{report_date}.json"


def _load_report(report_date: str) -> dict | None:
    path = _report_path(report_date)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _load_previous_reports(days_back: int = 5) -> dict[str, dict]:
    """加载最近 N 个交易日的复盘报告（key: 日期字符串）"""
    reports: dict[str, dict] = {}
    for d in range(1, days_back + 1):
        report_date = (date.today() - timedelta(days=d)).isoformat()
        r = _load_report(report_date)
        if r:
            reports[report_date] = r
    return reports


def _compare_accuracy(today_signals: list[dict], prev_reports: dict[str, dict]) -> list[dict]:
    """对比历史报告推荐标的与当前数据的准确性"""
    accuracy: list[dict] = []
    for report_date, report in sorted(prev_reports.items(), reverse=True):
        prev_picks: list[dict] = report.get("top_stocks", [])
        if not prev_picks:
            continue
        today_code_signals: dict[str, list[dict]] = {}
        for sig in today_signals:
            today_code_signals.setdefault(sig["code"], []).append(sig)

        detail: list[dict] = []
        hit_count = 0
        for pick in prev_picks:
            code = pick["code"]
            today_sigs = today_code_signals.get(code, [])
            n = len(today_sigs)
            if n > 0:
                hit_count += 1
            detail.append(
                {
                    "code": code,
                    "name": pick.get("name", ""),
                    "prev_confidence": pick.get("confidence", 0),
                    "prev_strategy": pick.get("strategy", ""),
                    "today_signal_count": n,
                    "today_max_confidence": max((s["confidence"] for s in today_sigs), default=0),
                }
            )
        total = len(prev_picks)
        accuracy.append(
            {
                "date": report_date,
                "total": total,
                "hit": hit_count,
                "hit_rate": round(hit_count / total * 100, 1) if total > 0 else 0,
                "detail": detail,
            }
        )
    return accuracy


def run_review() -> dict | None:
    """执行一次复盘分析，返回报告 dict；失败返回 None"""
    info("review", "开始复盘分析…")
    start_time = time.time()

    pool = get_pool(kind="stock", enabled_only=True)
    if not pool:
        warning("review", "标的池为空，跳过复盘")
        return None

    debug("review", f"标的池共 {len(pool)} 只股票")

    all_signals: list[dict] = []
    fetch_errors: list[str] = []
    kline_cache: dict[str, Any] = {}  # 缓存 K 线供后续图表使用

    for item in pool:
        code = item["code"]
        name = item.get("name", code)
        sector = item.get("sector", "")
        try:
            df = biz_data.fetch_kline(code, days=250)
        except Exception as e:
            fetch_errors.append(f"{code} K线拉取失败: {e}")
            warning("review", f"{code} K线拉取失败: {e}")
            continue

        if df is None or df.empty:
            continue

        kline_cache[code] = df

        signals = scan_stock(code, name, sector, df)
        for sig in signals:
            all_signals.append(
                {
                    "code": sig.code,
                    "name": sig.name,
                    "sector": sig.sector,
                    "strategy": sig.strategy,
                    "category": sig.category,
                    "current_price": sig.current_price,
                    "suggested_buy": sig.suggested_buy,
                    "stop_loss": sig.stop_loss,
                    "take_profit": sig.take_profit,
                    "reason": sig.reason,
                    "confidence": sig.confidence,
                }
            )

    all_signals.sort(key=lambda s: s["confidence"], reverse=True)

    top5_dict: dict[str, dict] = {}
    for sig in all_signals:
        code = sig["code"]
        if code not in top5_dict and len(top5_dict) < 5:
            top5_dict[code] = sig

    top5 = sorted(top5_dict.values(), key=lambda s: s["confidence"], reverse=True)

    prev_reports = _load_previous_reports(days_back=5)
    accuracy_report = _compare_accuracy(all_signals, prev_reports)

    report_date = _today()
    elapsed = round(time.time() - start_time, 1)
    report: dict[str, Any] = {
        "date": report_date,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_seconds": elapsed,
        "pool_size": len(pool),
        "total_signals": len(all_signals),
        "fetch_errors": fetch_errors,
        "top_stocks": top5,
        "accuracy": accuracy_report,
    }

    path = _report_path(report_date)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    info("review", f"复盘完成（{elapsed}s），共 {len(all_signals)} 个信号，Top-{len(top5)} 已写入 {path}")

    # 生成 Top-5 股价折线图
    from rquant.review.chart import plot_top_stocks_charts

    plot_top_stocks_charts(top5, kline_cache)

    return report
