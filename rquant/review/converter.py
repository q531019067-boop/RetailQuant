"""
rquant.review.converter — 复盘数据格式转换

- JSON → Typst (.typ)  可被 typst CLI 编译为 PDF/PNG
- JSON → HTML (.html)  可直接在浏览器查看
"""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import date
from pathlib import Path

from config import config
from rquant.log import error, info, warning

REPORT_DIR = config.project_root / config.review.report_dir
_FONTS_DIR = Path(__file__).parent / "fonts"

# === 字体配置 ===
# 仓库内嵌 LXGW WenKai（霞鹜文楷），SIL OFL 开源。
# Typst 可模拟 Bold，*strong* / weight: "bold" 正常使用。
_TYPST_FONT = "LXGW WenKai"
_TYPST_FONT_MONO = "New Computer Modern"
# ================


def _today() -> str:
    return date.today().isoformat()


def _read_report(report_date: str | None = None) -> dict | None:
    report_date = report_date or _today()
    path = REPORT_DIR / f"{report_date}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _typst_escape(text: str) -> str:
    """转义 Typst 特殊字符"""
    return text.replace("\\", "\\\\").replace("#", "\\#")


def _conf_hex(confidence: float) -> str:
    """置信度 → 颜色 hex"""
    if confidence >= 80:
        return "#16a34a"
    if confidence >= 60:
        return "#b45309"
    return "#64748b"


def _booktabs(n_data_rows: int) -> str:
    """三线表 stroke：顶部 1.5pt + 表头下 0.5pt + 底部 1.5pt"""
    return (
        f"  stroke: (x, y) => "
        f'if y == 0 {{ (top: 1.5pt + rgb("#0f172a"), bottom: 0.5pt + rgb("#0f172a")) }} '
        f'else if y == {n_data_rows} {{ (bottom: 1.5pt + rgb("#0f172a")) }},'
    )


def to_typst(report_date: str | None = None) -> Path | None:
    """将复盘报告导出为 Typst 格式（.typ 文件，三线表排版）"""
    report = _read_report(report_date)
    if not report:
        error("review.converter", "复盘报告不存在，无法导出 Typst")
        return None

    report_date = report["date"]
    generated = report["generated_at"]
    pool_size = report["pool_size"]
    total_signals = report["total_signals"]
    top_stocks: list[dict] = report.get("top_stocks", [])
    accuracy: list[dict] = report.get("accuracy", [])
    fetch_errors: list[str] = report.get("fetch_errors", [])

    # Top-5 表格数据（7 列：排名/代码/名称/策略/置信度/交易参数/推荐理由）
    top_rows = []
    for i, s in enumerate(top_stocks, 1):
        code = s["code"]
        name = _typst_escape(s["name"])
        strategy = _typst_escape(s["strategy"])
        conf = s["confidence"]
        c = _conf_hex(conf)
        top_rows.append(
            f'  [{i}], [{code}], [{name}], [{strategy}], [#text(fill: rgb("{c}"), weight: "bold")[{conf}\\%]],'
        )

    # 推荐理由段落
    rationale_typ = ""
    if top_stocks:
        items = []
        for i, s in enumerate(top_stocks, 1):
            name = _typst_escape(s["name"])
            code = s["code"]
            strategy = _typst_escape(s["strategy"])
            reason = _typst_escape(s.get("reason", ""))
            price = s.get("current_price", "-")
            buy = s.get("suggested_buy", "-")
            sl = s.get("stop_loss", "-")
            tp = s.get("take_profit", "-")
            conf = s["confidence"]
            c = _conf_hex(conf)
            items.append(
                f'+ #text(fill: rgb("{c}"), weight: "bold")[{conf}\\%] '
                f"*{name}* ({code})  ——  {strategy}\n"
                f'  #text(size: 8.5pt, fill: rgb("#475569"))[现价 {price} / 买入 {buy} / 止损 {sl} / 止盈 {tp}]\n'
                f'  #text(size: 8.5pt, fill: rgb("#334155"))[{reason}]'
            )
        rationale_typ = "\n#v(8pt)\n" + "\n\n".join(items) + "\n"

    # 走势图
    charts_typ = _format_charts_typst(top_stocks)

    # 准确性表格数据
    acc_rows_list = []
    for acc in accuracy:
        hit = acc["hit"]
        total = acc["total"]
        rate = acc["hit_rate"]
        if rate >= 70:
            color = "#16a34a"
        elif rate >= 30:
            color = "#b45309"
        else:
            color = "#dc2626"
        detail = acc.get("detail", [])
        hit_codes = ", ".join(d["code"] for d in detail if d.get("today_signal_count", 0) > 0)
        miss_codes = ", ".join(d["code"] for d in detail if d.get("today_signal_count", 0) == 0)
        acc_rows_list.append(
            f"  [{acc['date']}], [{total}], [{hit}], "
            f'[#text(fill: rgb("{color}"), weight: "bold")[{rate}\\%]], '
            f"[{hit_codes}], [{miss_codes}],"
        )

    fetch_errors_typ = ""
    if fetch_errors:
        error_items = "\n".join(f'  #text(size: 9pt, fill: rgb("#dc2626"))[- {_typst_escape(e)}]' for e in fetch_errors)
        fetch_errors_typ = f"""= 数据拉取异常

#block(
  fill: rgb("#fef2f2"),
  stroke: 0.5pt + rgb("#fecaca"),
  radius: 4pt,
  inset: 10pt,
  [
    #text(size: 10pt, fill: rgb("#dc2626"), weight: "bold")[以下标的未能拉取数据:]
    #v(4pt)
{error_items}
  ]
)
"""

    accuracy_typ = ""
    if accuracy:
        accuracy_typ = f"""= 历史复盘准确性回顾

#figure(
  table(
{_booktabs(len(accuracy))}
    inset: (x: 8pt, y: 5pt),
    columns: (auto, auto, auto, auto, 1fr, 1fr),
    align: (center, center, center, center, left, left),
    table.header(
      [*日期*],
      [*推荐总数*],
      [*命中*],
      [*命中率*],
      [*持续信号*],
      [*衰减信号*],
    ),
{chr(10).join(acc_rows_list)}
  ),
  caption: [历史复盘推荐的持续准确性。],
  kind: table,
)
"""

    typ = f"""// rQuant Daily Review — {report_date}
// Automatically generated. Confidential. Not investment advice.

#set page(
  paper: "a4",
  margin: (top: 2cm, left: 1.8cm, right: 1.8cm, bottom: 1.5cm),
  height: auto,
)

#set text(font: ("{_TYPST_FONT}", "{_TYPST_FONT_MONO}"), lang: "zh", size: 9.5pt)
#set par(justify: true, leading: 0.55em)

// 标题样式
#show heading.where(level: 1): it => {{
  set text(size: 13pt, weight: "bold", fill: rgb("#0f172a"))
  it.body
  v(2pt)
  line(length: 100% - 4pt, stroke: (paint: rgb("#0f172a"), thickness: 1pt))
  v(10pt)
}}

= 每日量化复盘 — {report_date}

#text(size: 9pt, fill: rgb("#64748b"))[生成时间: {generated}   |   标的池: {pool_size} 只   |   信号总数: {total_signals} 条]

#v(8pt)

{fetch_errors_typ}

// ---------- Top-5 荐股 ----------

= 明日推荐买入标的 Top-5

#figure(
  table(
{_booktabs(len(top_stocks))}
    inset: (x: 5pt, y: 4pt),
    columns: (auto, auto, 1fr, 1fr, auto),
    align: (center, center, left, left, center),
    table.header(
      [*排名*],
      [*代码*],
      [*名称*],
      [*策略*],
      [*置信度*],
    ),
{chr(10).join(top_rows)}
  ),
  caption: [按置信度排序的前 5 个买入信号。],
  kind: table,
)

#v(6pt)

= 推荐理由

{rationale_typ}

{charts_typ}

{accuracy_typ}
"""

    out_path = REPORT_DIR / f"{report_date}.typ"
    out_path.write_text(typ, encoding="utf-8")
    info("review.converter", f"Typst 导出: {out_path}")
    return out_path


def _format_accuracy_html(accuracy: list[dict]) -> str:
    if not accuracy:
        return ""
    rows = ""
    for acc in accuracy:
        detail_rows = ""
        for d in acc.get("detail", []):
            status = "<b>Hit</b>" if d["today_signal_count"] > 0 else "Miss"
            detail_rows += (
                f"<tr><td>{status}</td><td>{d['code']}</td><td>{d['name']}</td>"
                f"<td>{d['prev_strategy']}</td><td>{d['prev_confidence']}</td>"
                f"<td>{d['today_max_confidence']}</td></tr>"
            )
        rows += (
            f"<tr><td rowspan='{acc['total'] + 1}' style='background:#f8fafc'>"
            f"<b>{acc['date']}</b><br>Hit Rate: {acc['hit']}/{acc['total']} ({acc['hit_rate']}%)</td>"
            f"<td colspan='5'></td></tr>"
            f"{detail_rows}"
        )
    return (
        "<h2>Historical Accuracy</h2>"
        "<table><tr><th>Date</th><th>Status</th><th>Code</th><th>Name</th>"
        "<th>Strategy</th><th>Prev Conf</th><th>Today Conf</th></tr>"
        f"{rows}</table>"
    )


def _format_top5_html(top_stocks: list[dict]) -> str:
    if not top_stocks:
        return "<p>No signals</p>"
    rows = ""
    for i, s in enumerate(top_stocks, 1):
        conf = s["confidence"]
        color = "#16a34a" if conf >= 80 else "#b45309" if conf >= 60 else "#64748b"
        rows += (
            f"<tr><td>{i}</td><td>{s['code']}</td><td>{s['name']}</td>"
            f"<td>{s['strategy']}</td>"
            f"<td style='color:{color};font-weight:bold'>{conf}%</td></tr>"
        )
    rationale = ""
    for i, s in enumerate(top_stocks, 1):
        sl = s.get("stop_loss", "-")
        tp = s.get("take_profit", "-")
        buy = s.get("suggested_buy", "-")
        price = s.get("current_price", "-")
        rationale += (
            f"<tr><td colspan='5' style='text-align:left;background:#fafafa;font-size:13px'>"
            f"<b>{i}. {s['name']} ({s['code']})</b> &mdash; {s['strategy']}<br>"
            f"Entry {buy} / Stop {sl} / Target {tp} / Price {price}<br>"
            f"{s.get('reason', '')}</td></tr>"
        )
    return (
        "<h2>Top 5 Buy Signals</h2>"
        "<table><tr><th>#</th><th>Code</th><th>Name</th><th>Strategy</th><th>Conf</th></tr>"
        f"{rows}{rationale}</table>"
    )


def _format_charts_html(top_stocks: list[dict]) -> str:
    """为 Top-5 股票嵌入近 90 日股价折线图（base64 内嵌）"""
    from rquant.review.chart import CHART_DIR, chart_to_base64

    items: list[str] = []
    for s in top_stocks:
        code = s["code"]
        svg_path = CHART_DIR / f"{code}_90d.svg"
        if svg_path.exists():
            b64 = chart_to_base64(svg_path)
            items.append(
                f'<div class="chart-card">'
                f'<img src="{b64}" alt="{s["name"]} 走势" style="width:100%;max-width:700px;display:block;margin:0 auto;">'
                f"</div>"
            )

    if not items:
        return ""

    return '<h2>Top-5 近 90 交易日走势</h2><div class="chart-grid">' + "".join(items) + "</div>"


def _format_charts_typst(top_stocks: list[dict]) -> str:
    """为 Top-5 股票生成 Typst 折线图嵌入代码"""
    from rquant.review.chart import CHART_DIR

    items: list[str] = []
    for s in top_stocks:
        code = s["code"]
        name = _typst_escape(s["name"])
        svg_path = CHART_DIR / f"{code}_90d.svg"
        if svg_path.exists():
            items.append(
                f"#figure(\n"
                f'  image("charts/{code}_90d.svg", width: 100%),\n'
                f"  caption: [{name} 近 90 交易日收盘价走势],\n"
                f"  kind: image,\n"
                f")"
            )
        else:
            items.append(f'#text(size: 9pt, fill: rgb("#94a3b8"))[{name}: 图表数据暂缺]')

    if not items:
        return ""

    return "= Top-5 近 90 交易日走势\n\n" + "\n\n#v(6pt)\n\n".join(items) + "\n"


def to_html(report_date: str | None = None) -> Path | None:
    """将复盘报告导出为 HTML 网页"""
    report = _read_report(report_date)
    if not report:
        error("review.converter", "复盘报告不存在，无法导出 HTML")
        return None

    report_date = report["date"]
    top_stocks: list[dict] = report.get("top_stocks", [])
    accuracy: list[dict] = report.get("accuracy", [])
    fetch_errors: list[str] = report.get("fetch_errors", [])

    error_section = ""
    if fetch_errors:
        error_items = "".join(f"<li>{e}</li>" for e in fetch_errors)
        error_section = f"<h2>拉取异常</h2><ul>{error_items}</ul>"

    charts_section = _format_charts_html(top_stocks)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>复盘报告 — {report_date}</title>
<style>
  body {{ font-family: -apple-system, "Microsoft YaHei", sans-serif; max-width: 1200px; margin: 40px auto; padding: 0 20px; color: #333; }}
  h1 {{ border-bottom: 2px solid #4a90d9; padding-bottom: 8px; }}
  h2 {{ color: #4a90d9; margin-top: 30px; }}
  table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
  th, td {{ border: 1px solid #ddd; padding: 8px 10px; text-align: center; font-size: 14px; }}
  th {{ background: #f5f5f5; }}
  tr:nth-child(even) {{ background: #fafafa; }}
  .meta {{ color: #888; font-size: 13px; }}
  ul {{ list-style: none; padding: 0; }}
  li {{ padding: 4px 0; color: #c0392b; font-size: 13px; }}
  .chart-grid {{ display: flex; flex-wrap: wrap; gap: 16px; justify-content: center; }}
  .chart-card {{ background: #fafafa; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; flex: 1 1 450px; max-width: 700px; }}
  .chart-card img {{ border-radius: 4px; }}
</style>
</head>
<body>
<h1>复盘报告 — {report_date}</h1>
<p class="meta">
  生成时间: {report["generated_at"]} &nbsp;|&nbsp;
  耗时: {report["elapsed_seconds"]}s &nbsp;|&nbsp;
  标的池: {report["pool_size"]} 只 &nbsp;|&nbsp;
  总信号: {report["total_signals"]} 条
</p>
{error_section}
{_format_top5_html(top_stocks)}
{charts_section}
{_format_accuracy_html(accuracy)}
</body>
</html>"""

    out_path = REPORT_DIR / f"{report_date}.html"
    out_path.write_text(html, encoding="utf-8")
    info("review.converter", f"HTML 导出: {out_path}")
    return out_path


def _typst_available() -> bool:
    return shutil.which("typst") is not None


def to_pdf(report_date: str | None = None) -> Path | None:
    """将复盘报告导出为 PDF（需系统安装 typst CLI）"""
    report_date = report_date or _today()
    typ_path = REPORT_DIR / f"{report_date}.typ"
    if not typ_path.exists():
        if to_typst(report_date) is None:
            return None

    if not _typst_available():
        warning("review.converter", "typst CLI 未安装，跳过 PDF 导出")
        return None

    pdf_path = REPORT_DIR / f"{report_date}.pdf"
    try:
        subprocess.run(
            ["typst", "compile", "--font-path", str(_FONTS_DIR), str(typ_path), str(pdf_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        info("review.converter", f"PDF 导出: {pdf_path}")
        return pdf_path
    except subprocess.CalledProcessError as e:
        error("review.converter", f"typst compile 失败: {e.stderr.strip()}")
        return None


def to_png(report_date: str | None = None) -> Path | None:
    """将复盘报告导出为单张长图 PNG（Typst 页面 height: auto 自动撑开）。

    需系统安装 typst CLI。返回 PNG 路径，失败返回 None。
    """
    report_date = report_date or _today()
    typ_path = REPORT_DIR / f"{report_date}.typ"
    if not typ_path.exists():
        if to_typst(report_date) is None:
            return None

    if not _typst_available():
        warning("review.converter", "typst CLI 未安装，跳过 PNG 导出")
        return None

    png_path = REPORT_DIR / f"{report_date}.png"
    try:
        subprocess.run(
            ["typst", "compile", "--font-path", str(_FONTS_DIR), str(typ_path), str(png_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        info("review.converter", f"PNG 导出: {png_path}")
        return png_path
    except subprocess.CalledProcessError as e:
        error("review.converter", f"typst compile 失败: {e.stderr.strip()}")
        return None


def convert_all(report_date: str | None = None) -> dict[str, Path | None]:
    """一次性导出 Typst + PDF + PNG"""
    return {
        "typst": to_typst(report_date),
        "pdf": to_pdf(report_date),
        "png": to_png(report_date),
    }
