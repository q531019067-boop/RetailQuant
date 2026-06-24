"""
rQuant 复盘手动触发脚本

用法：
    uv run python scripts/review.py          # 执行一次完整复盘
    uv run python -m scripts.review          # 同上

复盘流程：分析 → 格式转换（Typst + HTML）→ 邮件发送
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rquant.review import run_full_review  # noqa: E402

if __name__ == "__main__":
    result = run_full_review(force=True)
    if result:
        print(f"复盘完成 → {result['date']}")
        if result.get("top_stocks"):
            print("\nTop-5 推荐标的:")
            for i, s in enumerate(result["top_stocks"], 1):
                print(f"  {i}. {s['code']} {s['name']} | {s['strategy']} | 置信度={s['confidence']} | {s['reason']}")
        if result.get("accuracy"):
            print("\n历史准确性:")
            for acc in result["accuracy"]:
                print(f"  {acc['date']}  命中率: {acc['hit']}/{acc['total']} ({acc['hit_rate']}%)")
    else:
        print("复盘未执行（模块未启用或标的池为空）")
