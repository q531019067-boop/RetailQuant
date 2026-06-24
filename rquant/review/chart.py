"""
rquant.review.chart — 股价走势图表生成

为复盘报告中的 Top-5 标的生成近 90 个交易日收盘价折线图。
图表以 SVG 形式保存到 reports/charts/ 目录，供 HTML/Typst 内嵌。
"""

from __future__ import annotations

import base64
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # 必须在 import pyplot 之前，锁定非交互后端

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.font_manager import FontProperties
import pandas as pd

from config import config
from rquant.log import info, warning

REPORT_DIR = config.project_root / config.review.report_dir
CHART_DIR = REPORT_DIR / "charts"
CHART_DIR.mkdir(parents=True, exist_ok=True)

# 内嵌中文字体（LXGW WenKai 霞鹜文楷，SIL OFL 开源，随仓库分发）
_FONTS_DIR = Path(__file__).parent / "fonts"
_FONT_KAI = _FONTS_DIR / "LXGWWenKai-Regular.ttf"

_KAI_PROP = FontProperties(fname=str(_FONT_KAI)) if _FONT_KAI.exists() else None

# 通用设置
plt.rcParams["axes.unicode_minus"] = False


def _truncate_code(code: str) -> str:
    """sh600519 → 600519"""
    return code[2:] if code.startswith(("sh", "sz")) else code


def plot_single_stock(
    code: str,
    name: str,
    df: pd.DataFrame,
    days: int = 90,
) -> Path | None:
    """为单只股票生成收盘价折线图，返回 SVG 路径。

    Args:
        code: 股票代码（如 sh600519）
        name: 股票名称
        df: K 线 DataFrame，需含 date, close 列
        days: 展示最近多少个交易日

    Returns:
        SVG 文件路径，失败返回 None
    """
    if df is None or df.empty or "close" not in df.columns:
        warning("review.chart", f"{code} 无有效数据，跳过图表")
        return None

    df = df.copy()
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")

    # 取最近 N 个交易日
    df = df.tail(days)
    if len(df) < 5:
        warning("review.chart", f"{code} 数据不足（{len(df)} 行），跳过图表")
        return None

    close = df["close"].to_numpy()
    dates = df["date"].to_numpy() if "date" in df.columns else range(len(df))
    y_min, y_max = close.min(), close.max()
    padding = (y_max - y_min) * 0.08 or y_max * 0.02
    price_range = y_max - y_min

    fig, ax = plt.subplots(figsize=(8, 3.2))
    ax.plot(dates, close, color="#2563eb", linewidth=1.2, zorder=2)

    # 填充区域（与 plot 共用同一 dates 数组，避免 X 轴类型混乱）
    ax.fill_between(
        dates,
        close,
        y_min - padding,
        alpha=0.08,
        color="#2563eb",
    )

    # 标注首尾价格
    first_price, last_price = close[0], close[-1]
    change = last_price - first_price
    change_pct = (change / first_price) * 100
    change_color = "#16a34a" if change >= 0 else "#dc2626"
    change_sign = "+" if change >= 0 else ""

    ax.annotate(
        f"{first_price:.2f}",
        xy=(dates[0], first_price),
        xytext=(8, 8),
        textcoords="offset points",
        fontsize=8,
        color="#64748b",
        fontproperties=_KAI_PROP,
    )
    ax.annotate(
        f"{last_price:.2f}  ({change_sign}{change_pct:.1f}%)",
        xy=(dates[-1], last_price),
        xytext=(-8, 8),
        textcoords="offset points",
        fontsize=9,
        color=change_color,
        ha="right",
        fontproperties=_KAI_PROP,
    )

    # 坐标轴美化
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#e2e8f0")
    ax.spines["bottom"].set_color("#e2e8f0")
    ax.tick_params(colors="#94a3b8", labelsize=7)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.2f"))
    ax.set_ylim(y_min - padding, y_max + padding)

    # X 轴日期格式化
    if "date" in df.columns:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))

    ax.set_title(
        f"{name}  ({_truncate_code(code)})",
        fontsize=12,
        color="#0f172a",
        pad=10,
        fontproperties=_KAI_PROP,
    )

    # 区间统计副标题
    if price_range > 0:
        ax.text(
            0.5,
            1.02,
            f"近 {len(df)} 交易日  |  区间 {y_min:.2f} – {y_max:.2f}  |  波幅 {price_range / y_min * 100:.1f}%",
            transform=ax.transAxes,
            fontsize=7,
            color="#94a3b8",
            ha="center",
            fontproperties=_KAI_PROP,
        )

    # tick 标签字体
    if _KAI_PROP:
        for label in ax.get_xticklabels():
            label.set_fontproperties(_KAI_PROP)
        for label in ax.get_yticklabels():
            label.set_fontproperties(_KAI_PROP)

    fig.tight_layout(pad=1.5)

    out_path = CHART_DIR / f"{code}_90d.svg"
    fig.savefig(out_path, format="svg", bbox_inches="tight", facecolor="white")
    plt.close(fig)

    info("review.chart", f"图表已生成: {out_path}")
    return out_path


def chart_to_base64(svg_path: Path) -> str:
    """将 SVG 文件编码为 base64 data URI（供 HTML 内嵌）"""
    data = svg_path.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:image/svg+xml;base64,{b64}"


def plot_top_stocks_charts(top_stocks: list[dict], kline_data: dict[str, pd.DataFrame]) -> dict[str, Path]:
    """为 Top-5 列表中的每只股票生成折线图。

    Args:
        top_stocks: Top-5 信号列表，每项含 code, name
        kline_data: {code: DataFrame} 的 K 线数据映射

    Returns:
        {code: svg_path} 映射
    """
    result: dict[str, Path] = {}
    for s in top_stocks:
        code = s["code"]
        name = s.get("name", code)
        df = kline_data.get(code)
        if df is None:
            warning("review.chart", f"{code} 缺少 K 线数据，跳过图表")
            continue
        path = plot_single_stock(code, name, df)
        if path:
            result[code] = path
    return result
