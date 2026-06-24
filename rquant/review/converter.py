"""
rquant.review.converter — 复盘数据格式转换

- JSON → Typst (.typ)  Jinja2 模板渲染 → typst CLI 编译为 PDF/PNG
- JSON → HTML (.html)  可直接在浏览器查看
"""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from config import config
from rquant.log import error, info, warning

REPORT_DIR = config.project_root / config.review.report_dir
_FONTS_DIR = Path(__file__).parent / "fonts"

# === 字体配置 ===
_TYPST_FONT = "LXGW WenKai"
_TYPST_FONT_MONO = "New Computer Modern"

# === Jinja2 环境（${var} 避免与 Typst {{ }} 冲突）===
_TEMPLATE_DIR = Path(__file__).parent / "templates"
_jinja = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    variable_start_string="${",
    variable_end_string="}",
    autoescape=False,
)


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


def _conf_hex(confidence: float) -> str:
    """置信度 → 颜色 hex"""
    if confidence >= 80:
        return "#16a34a"
    if confidence >= 60:
        return "#b45309"
    return "#64748b"


def _rate_hex(hit_rate: float) -> str:
    """命中率 → 颜色 hex"""
    if hit_rate >= 70:
        return "#16a34a"
    if hit_rate >= 30:
        return "#b45309"
    return "#dc2626"


def _prepare_stock(s: dict) -> dict:
    """补充 Typst 模板需要的衍生字段"""
    conf = s.get("confidence", 0)
    return {
        **s,
        "conf_hex": _conf_hex(conf),
        "current_price": s.get("current_price", "-"),
        "suggested_buy": s.get("suggested_buy", "-"),
        "stop_loss": s.get("stop_loss", "-"),
        "take_profit": s.get("take_profit", "-"),
        "reason": s.get("reason", ""),
    }


def _prepare_charts(top_stocks: list[dict]) -> list[dict]:
    """准备走势图数据（只保留有对应 SVG 的标的）"""
    from rquant.review.chart import CHART_DIR

    result = []
    for s in top_stocks:
        if (CHART_DIR / f"{s['code']}_90d.svg").exists():
            result.append({"code": s["code"], "name": s["name"]})
    return result


def to_typst(report_date: str | None = None) -> Path | None:
    """将复盘报告导出为 Typst 格式（Jinja2 模板渲染）"""
    report = _read_report(report_date)
    if not report:
        error("review.converter", "复盘报告不存在，无法导出 Typst")
        return None

    top_stocks = [_prepare_stock(s) for s in report.get("top_stocks", [])]

    accuracy = []
    for acc in report.get("accuracy", []):
        detail = acc.get("detail", [])
        accuracy.append(
            {
                "date": acc["date"],
                "total": acc["total"],
                "hit": acc["hit"],
                "hit_rate": acc["hit_rate"],
                "rate_hex": _rate_hex(acc["hit_rate"]),
                "hit_codes": ", ".join(d["code"] for d in detail if d.get("today_signal_count", 0) > 0),
                "miss_codes": ", ".join(d["code"] for d in detail if d.get("today_signal_count", 0) == 0),
            }
        )

    data = {
        "fonts": {"cjk": _TYPST_FONT, "mono": _TYPST_FONT_MONO},
        "report": report,
        "top_stocks": top_stocks,
        "charts": _prepare_charts(top_stocks),
        "accuracy": accuracy,
    }

    tmpl = _jinja.get_template("report.typ.j2")
    typ = tmpl.render(**data)

    out_path = REPORT_DIR / f"{report_date}.typ"
    out_path.write_text(typ, encoding="utf-8")
    info("review.converter", f"Typst 导出: {out_path}")
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
