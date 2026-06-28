"""
rquant.research.montecarlo.cli — 命令行入口（standalone）

与 FactorQ 原版 __main__ 的差异
--------------------------------
- 原版 ``__main__`` 依赖 FactorQ 的 ``OnDemandAnalyzer``（含实时行情 + 策略 TP/SL）。
- 本 CLI 不依赖 ``OnDemandAnalyzer``，只通过 RetailQuant 业务层::

      from rquant.business.data import fetch_kline, get_stock

  - ``fetch_kline(code, days)`` 走 DataSourcePool 拉 K 线（缓存优先）。
  - ``get_stock(code)`` 从已查看过的内存字典读 name。
  - 当前价取 K 线最后一行 close（如需盘中实时价，caller 自行覆盖）。
  - TP/SL 必须显式传（没有现成策略信号时，按 ±4%/±8% 兜底）。

用法
----
::

    python -m rquant.research.montecarlo.cli sh600000
    python -m rquant.research.montecarlo.cli sh600000 --days 40 --sims 2000
    python -m rquant.research.montecarlo.cli sh600000 --tp 13.5 --sl 11.8
    python -m rquant.research.montecarlo.cli sh600000 --json   # 完整 JSON 输出
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional

import pandas as pd

from .forecaster import run_forecast


def _current_price_from_df(df: pd.DataFrame) -> float:
    """从 K 线最后一行取 close 作为当前价（caller 自行保证 as-of）"""
    if df is None or df.empty or "close" not in df.columns:
        return 0.0
    return float(df["close"].iloc[-1])


def _default_tp_sl(price: float, tp: Optional[float], sl: Optional[float]) -> tuple[Optional[float], Optional[float]]:
    """TP/SL 兜底（±8% / -4%）"""
    if tp is None and price > 0:
        tp = round(price * 1.08, 2)
    if sl is None and price > 0:
        sl = round(price * 0.96, 2)
    return tp, sl


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="个股蒙特卡洛路径预测（GBM + 分位带 + TP/SL 命中）",
    )
    parser.add_argument("code", help="股票代码，如 sh600000")
    parser.add_argument("--days", type=int, default=20, help="预测天数（默认 20）")
    parser.add_argument("--sims", type=int, default=1000, help="模拟路径数（默认 1000）")
    parser.add_argument("--lookback", type=int, default=252, help="历史 lookback 天数（默认 252）")
    parser.add_argument("--tp", type=float, default=None, help="止盈价（不传则按现价 ×1.08 兜底）")
    parser.add_argument("--sl", type=float, default=None, help="止损价（不传则按现价 ×0.96 兜底）")
    parser.add_argument("--seed", type=int, default=42, help="随机种子（默认 42，便于复现）")
    parser.add_argument("--kline-days", type=int, default=400, help="拉 K 线天数（默认 400，需 > lookback）")
    parser.add_argument("--json", action="store_true", help="输出完整 JSON 而非摘要")
    parser.add_argument(
        "--live-price",
        type=float,
        default=None,
        help="覆盖当前价（盘中实时价），不传则用 K 线最后 close",
    )
    args = parser.parse_args(argv)

    # 延迟导入业务层（CLI 入口要尽量轻）
    from rquant.business.data import fetch_kline, get_stock

    code = args.code.strip().lower()

    # 拉 K 线
    try:
        df = fetch_kline(code, args.kline_days)
    except Exception as e:
        print(f"❌ K 线拉取失败 {code}: {e}", file=sys.stderr)
        return 2

    if df is None or df.empty:
        print(f"❌ 没有可用 K 线 {code}", file=sys.stderr)
        return 2

    # 当前价：caller 指定 > K 线最后 close
    if args.live_price is not None and args.live_price > 0:
        current_price = args.live_price
    else:
        current_price = _current_price_from_df(df)

    if current_price <= 0:
        print(f"❌ 当前价无效 {code}: {current_price}", file=sys.stderr)
        return 2

    # 名字（优先内存字典，fallback 到 code）
    name = get_stock(code).get("name") or code

    # TP/SL 兜底
    tp, sl = _default_tp_sl(current_price, args.tp, args.sl)

    out = run_forecast(
        df,
        current_price=current_price,
        forecast_days=args.days,
        simulations=args.sims,
        lookback_days=args.lookback,
        take_profit=tp,
        stop_loss=sl,
        seed=args.seed,
        code=code,
        name=name,
    )

    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    if "error" in out:
        print(f"❌ {out['error']}", file=sys.stderr)
        return 1

    # 摘要
    print("=" * 60)
    print(f"代码: {out['code']}  名称: {out['name']}")
    print(f"现价: ¥{out['current_price']:.2f}  末日: {out['last_date']}")
    print(f"参数: lookback={out['lookback_days_used']}天, forecast={out['forecast_days']}天, sims={out['simulations']}")
    print(f"μ(日 / 年化): {out['mu_daily']:.5f} / {out['mu_annualized']:.4f}")
    print(f"σ(日 / 年化): {out['sigma_daily']:.5f} / {out['sigma_annualized']:.4f}")
    if out.get("sigma_floored"):
        print("  ⚠ σ 用了兜底值（数据波动极小）")

    print(f"\n最终价分布（forecast={args.days}天）：")
    print(f"  P5   ¥{out['stats']['final_price_p05']:.2f}")
    print(f"  P50  ¥{out['stats']['final_price_median']:.2f}")
    print(f"  P95  ¥{out['stats']['final_price_p95']:.2f}")
    print(f"  预期收益（中位）: {out['stats']['expected_return_pct']:+.2f}%")
    print(f"  上涨概率: {out['stats']['prob_higher_pct']:.1f}%")
    if out["stats"]["prob_take_profit_pct"] is not None:
        print(f"  命中 TP ¥{out['take_profit']:.2f}: {out['stats']['prob_take_profit_pct']:.1f}%")
    if out["stats"]["prob_stop_loss_pct"] is not None:
        print(f"  命中 SL ¥{out['stop_loss']:.2f}: {out['stats']['prob_stop_loss_pct']:.1f}%")
    print(
        f"  最大回撤中位 / 95分位(更差): "
        f"{out['stats']['max_drawdown_median_pct']:.2f}% / "
        f"{out['stats']['max_drawdown_worst_5pct_pct']:.2f}%"
    )

    if out.get("warnings"):
        print("\n⚠ 警告:")
        for w in out["warnings"]:
            print(f"  - {w}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
