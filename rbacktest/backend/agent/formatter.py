"""
回测数据压缩 —— 将前端传来的完整 results 对象压缩为 ~1500 token 的 LLM 友好文本。
"""

from __future__ import annotations

from typing import Any


def _fmt_int(v: Any) -> str:
    """安全格式化整数（防止 None / 非数字 crash）。"""
    try:
        return f"{int(v):,}"
    except (ValueError, TypeError):
        return str(v)


def format_backtest_context(
    results: dict[str, Any],
    params: dict[str, Any] | None = None,
) -> str:
    """将回测结果转换为结构化文本块。

    results: {"strategy_name": {"statistics": {...}, "daily": [...], "trades": [...]}}
    params: {"start": "...", "end": "...", "capital": ..., "vt_symbols": [...]}
    """
    lines: list[str] = []

    # 回测参数
    if params:
        lines.append("## 回测参数")
        lines.append(f"- 区间: {params.get('start', '?')} ~ {params.get('end', '?')}")
        lines.append(f"- 本金: ¥{_fmt_int(params.get('capital', 0))}")
        symbols = params.get("vt_symbols", []) or params.get("vt_symbols", [])
        lines.append(f"- 股票: {', '.join(symbols[:10])}{'...' if len(symbols) > 10 else ''}")
        lines.append("")

    strategy_names = list(results.keys())

    # 策略对比表
    if len(strategy_names) > 1:
        lines.append("## 策略对比")
        lines.append(f"| 指标 | {' | '.join(strategy_names)} |")
        lines.append(f"|------|{'|'.join(['------'] * len(strategy_names))}|")
        metric_keys = [
            ("total_return", "总收益率%"),
            ("annual_return", "年化收益%"),
            ("sharpe_ratio", "Sharpe"),
            ("sortino_ratio", "Sortino"),
            ("calmar_ratio", "Calmar"),
            ("max_ddpercent", "最大回撤%"),
            ("win_rate", "胜率%"),
            ("profit_factor", "盈亏比"),
            ("total_trade_count", "交易笔数"),
        ]
        for key, label in metric_keys:
            values = [f"{results[sn]['statistics'].get(key, 0):.2f}" for sn in strategy_names]
            lines.append(f"| {label} | {' | '.join(values)} |")
        lines.append("")

    # 每个策略详情
    for sn in strategy_names:
        s = results[sn].get("statistics", {})
        d = results[sn].get("daily", [])
        t = results[sn].get("trades", [])

        lines.append(f"## 策略: {sn}")
        lines.append(f"- 年化收益: {s.get('annual_return', 0):.2f}%")
        lines.append(
            f"- Sharpe: {s.get('sharpe_ratio', 0):.2f} | Sortino: {s.get('sortino_ratio', 0):.2f} | Calmar: {s.get('calmar_ratio', 0):.2f}"
        )
        lines.append(f"- 最大回撤: {s.get('max_ddpercent', 0):.2f}% | 回撤天数: {s.get('max_drawdown_duration', 0)}")
        lines.append(f"- 胜率: {s.get('win_rate', 0):.1f}% | 盈亏比: {s.get('profit_factor', 0):.2f}")
        lines.append(f"- 交易笔数: {s.get('total_trade_count', 0)} | 总手续费: ¥{s.get('total_commission', 0):.2f}")
        lines.append(f"- 结束资金: ¥{s.get('end_balance', 0):,.0f}")

        if d:
            # 压缩每日数据为关键统计
            max_dd_day = min(d, key=lambda x: x.get("ddpercent", 0)) if d else {}
            max_ret_day = max(d, key=lambda x: x.get("return", 0)) if d else {}
            lines.append(
                f"- 最大回撤日: {str(max_dd_day.get('date', ''))[:10]} ({max_dd_day.get('ddpercent', 0):.2f}%)"
            )
            lines.append(f"- 最高日收益: {str(max_ret_day.get('date', ''))[:10]} ({max_ret_day.get('return', 0):.2f}%)")

        if t:
            lines.append("- 交易明细（前 5 笔）：")
            for trade in t[:5]:
                lines.append(
                    f"  {str(trade.get('date', ''))[:10]} | {trade.get('symbol', '?')} | "
                    f"{trade.get('side', '?')} | ¥{trade.get('price', 0):.2f} | "
                    f"盈亏: ¥{(trade.get('pnl') or 0):,.0f}"
                )
        lines.append("")

    return "\n".join(lines)


def format_empty_context() -> str:
    """无回测数据时的提示文本，附带默认可用资源。"""
    try:
        from backend.backtest_engine import list_available_stocks

        stocks = list_available_stocks()
        stock_count = len(stocks)
        first_stock = stocks[0] if stocks else "600519.SSE"
        second_stock = stocks[1] if len(stocks) > 1 else "000858.SZSE"
        third_stock = stocks[2] if len(stocks) > 2 else "600036.SSE"
        sample_list = ", ".join(stocks[:5]) if len(stocks) >= 5 else ", ".join(stocks)
    except Exception:
        sample_list = "未知"
        first_stock = "600519.SSE"
        second_stock = "000858.SZSE"
        third_stock = "600036.SSE"
        stock_count = 0

    return f"""当前没有回测数据。你可以帮我跑回测来探索策略。按以下步骤操作：

## 你的可用资源
- 股票池: {stock_count} 只（例如 {sample_list}）
- 日期范围: 2023-01-01 ~ 2024-12-31
- 初始资金: ¥1,000,000

## 工作流程
1. 调用 get_strategy_info("") 获取所有策略列表
2. 选 3-5 只股票（如 [{first_stock}, {second_stock}, {third_stock}]），一次性跑完所有策略，不要逐个策略反复测
3. 用默认参数，start="2023-01-01", end="2024-12-31"
4. 汇总对比，给出排名和推荐
5. **拿到结果就输出，不要再重复跑已经测过的策略**
"""
