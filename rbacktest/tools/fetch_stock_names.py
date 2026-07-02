"""
下载 A 股股票名称列表，缓存到 data/stock_names.json。

用法：
    uv run python rbacktest/tools/fetch_stock_names.py           # 首次下载
    uv run python rbacktest/tools/fetch_stock_names.py --force   # 强制刷新

数据来源：akshare stock_info_a_code_name()
输出：{"updated": "2026-07-02", "names": {"600519.SSE": "贵州茅台", ...}}
"""

import json
import sys
from datetime import date
from pathlib import Path

import akshare as ak

RBACKTEST_DIR = Path(__file__).resolve().parent.parent
CACHE_PATH = RBACKTEST_DIR / "data" / "stock_names.json"


def fetch_and_save(force: bool = False) -> int:
    """拉取全 A 股代码→名称映射，写入缓存文件。返回写入的股票数。"""
    if CACHE_PATH.exists() and not force:
        print(f"[SKIP] 缓存已存在: {CACHE_PATH}（使用 --force 强制刷新）")
        with open(CACHE_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return len(data.get("names", {}))

    print("正在从 akshare 拉取 A 股名称列表...")
    try:
        df = ak.stock_info_a_code_name()
    except Exception as e:
        print(f"[ERROR] 拉取失败: {e}")
        return 0

    if df is None or df.empty:
        print("[ERROR] akshare 返回空数据")
        return 0

    names: dict[str, str] = {}
    for _, row in df.iterrows():
        code = str(row.get("code", "")).strip()
        name = str(row.get("name", "")).strip()
        if not code or not name:
            continue
        # akshare 返回的 code 是纯数字，需要补交易所后缀
        if code.startswith(("60", "68")):
            vt_code = f"{code}.SSE"
        elif code.startswith(("00", "30")):
            vt_code = f"{code}.SZSE"
        elif code.startswith(("8", "4")):
            vt_code = f"{code}.BJ"
        else:
            continue
        names[vt_code] = name

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "updated": str(date.today()),
        "count": len(names),
        "names": names,
    }
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"[OK] 已缓存 {len(names)} 只股票名称 → {CACHE_PATH}")
    return len(names)


if __name__ == "__main__":
    force = "--force" in sys.argv
    count = fetch_and_save(force)
    if count == 0:
        sys.exit(1)
