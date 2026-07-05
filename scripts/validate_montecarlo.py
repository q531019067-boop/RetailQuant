#!/usr/bin/env python
"""滚动验证 rquant.research.montecarlo 的概率校准质量。"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from statistics import NormalDist

import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from rquant.business.data import fetch_kline  # noqa: E402
from rquant.research.montecarlo import DEFAULT_SIMULATIONS, run_forecast  # noqa: E402


def _pit(current: float, future: float, drift: float, sigma: float, days: int) -> float | None:
    if current <= 0 or future <= 0 or sigma <= 0 or days <= 0:
        return None
    z = (math.log(future / current) - drift * days) / (sigma * math.sqrt(days))
    return NormalDist().cdf(z)


def _brier(rows: list[dict], prob_key: str, actual_key: str) -> float | None:
    vals = []
    for row in rows:
        prob = row.get(prob_key)
        actual = row.get(actual_key)
        if prob is None or actual is None:
            continue
        vals.append((prob / 100 - actual) ** 2)
    return round(sum(vals) / len(vals), 6) if vals else None


def validate_code(args: argparse.Namespace, code: str) -> list[dict]:
    df = fetch_kline(code, args.days)
    if df is None or df.empty:
        return []
    df = df.sort_values("date").reset_index(drop=True)
    rows: list[dict] = []
    last_start = len(df) - args.forecast_days
    for idx in range(args.min_history, last_start, args.step):
        hist = df.iloc[: idx + 1].copy()
        future = df.iloc[idx + 1 : idx + 1 + args.forecast_days].copy()
        current = float(hist["close"].iloc[-1])
        tp = round(current * args.tp_mult, 4)
        sl = round(current * args.sl_mult, 4)
        out = run_forecast(
            hist,
            current_price=current,
            forecast_days=args.forecast_days,
            simulations=args.simulations,
            lookback_days=args.lookback,
            take_profit=tp,
            stop_loss=sl,
            seed=args.seed,
            code=code,
        )
        if "error" in out:
            rows.append({"code": code, "date": str(hist["date"].iloc[-1]), "error": out["error"]})
            continue
        stats = out["stats"]
        future_close = float(future["close"].iloc[-1])
        future_closes = future["close"].astype(float)
        actual_tp = int((future_closes >= tp).any())
        actual_sl = int((future_closes <= sl).any())
        p05 = stats["final_price_p05"]
        p50 = stats["final_price_median"]
        p95 = stats["final_price_p95"]
        rows.append(
            {
                "code": code,
                "date": str(pd.to_datetime(hist["date"].iloc[-1]).date()),
                "future_date": str(pd.to_datetime(future["date"].iloc[-1]).date()),
                "current": round(current, 4),
                "future_close": round(future_close, 4),
                "p05": p05,
                "p50": p50,
                "p95": p95,
                "covered_p05_p95": int(p05 <= future_close <= p95),
                "median_bias_pct": round((future_close / p50 - 1) * 100, 4) if p50 > 0 else None,
                "pit": _pit(current, future_close, out["mu_daily"], out["sigma_daily"], args.forecast_days),
                "prob_tp": stats.get("prob_take_profit_pct"),
                "prob_sl": stats.get("prob_stop_loss_pct"),
                "actual_tp": actual_tp,
                "actual_sl": actual_sl,
                "warnings": "；".join(out.get("warnings", [])),
            }
        )
    return rows


def summarize(rows: list[dict], args: argparse.Namespace) -> dict:
    ok_rows = [row for row in rows if "error" not in row]
    coverage = sum(row["covered_p05_p95"] for row in ok_rows) / len(ok_rows) if ok_rows else 0.0
    biases = [row["median_bias_pct"] for row in ok_rows if row.get("median_bias_pct") is not None]
    pits = [row["pit"] for row in ok_rows if row.get("pit") is not None]
    return {
        "generated_at": datetime.now().isoformat(),
        "codes": args.codes,
        "config": vars(args),
        "sample_count": len(ok_rows),
        "error_count": len(rows) - len(ok_rows),
        "coverage_p05_p95": round(coverage, 6),
        "median_bias_pct": round(float(pd.Series(biases).median()), 6) if biases else None,
        "pit_mean": round(sum(pits) / len(pits), 6) if pits else None,
        "brier_tp": _brier(ok_rows, "prob_tp", "actual_tp"),
        "brier_sl": _brier(ok_rows, "prob_sl", "actual_sl"),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="验证 MonteCarlo 预测分布校准度")
    parser.add_argument("codes", nargs="+", help="股票代码列表，如 sh600000 sz000001")
    parser.add_argument("--days", type=int, default=900, help="拉取 K 线天数")
    parser.add_argument("--lookback", type=int, default=252, help="估参窗口")
    parser.add_argument("--forecast-days", type=int, default=20, help="预测窗口")
    parser.add_argument("--simulations", type=int, default=DEFAULT_SIMULATIONS, help="模拟次数")
    parser.add_argument("--min-history", type=int, default=252, help="最小历史长度")
    parser.add_argument("--step", type=int, default=5, help="滚动步长")
    parser.add_argument("--tp-mult", type=float, default=1.08, help="TP = current * tp_mult")
    parser.add_argument("--sl-mult", type=float, default=0.96, help="SL = current * sl_mult")
    parser.add_argument("--seed", type=int, default=None, help="随机种子；默认 None")
    parser.add_argument("--out", default="results/montecarlo_validation", help="输出目录")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    rows: list[dict] = []
    for code in args.codes:
        rows.extend(validate_code(args, code.strip().lower()))

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    detail_path = out_dir / f"{stamp}_coverage.csv"
    summary_path = out_dir / f"{stamp}_summary.json"
    pd.DataFrame(rows).to_csv(detail_path, index=False)
    summary_path.write_text(json.dumps(summarize(rows, args), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"明细: {detail_path}")
    print(f"汇总: {summary_path}")


if __name__ == "__main__":
    main()
