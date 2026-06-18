# -*- coding: utf-8 -*-
"""按行标记「可疑乱码行」：替换字节、严格 UTF-8 失败、行级标签孤岛、MIX 等。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from mixed_encoding_fixer.corruption import REPLACEMENT_UTF8
from mixed_encoding_fixer.detect import classify_line_bytes
from mixed_encoding_fixer.io_bytes import read_and_split


def _strict_utf8_fails(line_bytes: bytes) -> bool:
    if not line_bytes:
        return False
    try:
        line_bytes.decode("utf-8")
        return False
    except UnicodeDecodeError:
        return True


def _preview_line(line_bytes: bytes, limit: int = 160) -> str:
    chunk = line_bytes[:limit]
    return chunk.decode("utf-8", errors="replace")


def build_suspect_report_from_rows(
    rows: List[Tuple[bytes, bytes]],
    mix_threshold: float,
    *,
    input_file: str = "<preloaded>",
    bom_info: Optional[str] = None,
    raw_without_bom: Optional[bytes] = None,
) -> Dict[str, Any]:
    """
    核心逻辑：接受预加载的行数据，避免重复读盘。
    rows: 来自 read_and_split 的 (line_bytes, sep) 列表。
    """
    labels: List[str] = [classify_line_bytes(r[0], mix_threshold) for r in rows]
    n = len(rows)
    suspects: List[Dict[str, Any]] = []

    for i, (lb, _sep) in enumerate(rows):
        reasons: List[str] = []
        if REPLACEMENT_UTF8 in lb:
            reasons.append("replacement_utf8")
        if _strict_utf8_fails(lb):
            reasons.append("strict_utf8_invalid")
        cur = labels[i]
        if cur == "MIX":
            reasons.append("line_label_mix")

        # 标签孤岛：与上一行、下一行标签均不同（且本行非纯 ANSI），常见于合并进一段 UTF-8 里的 GBK 行
        if i > 0 and i + 1 < n:
            prev_l, next_l = labels[i - 1], labels[i + 1]
            if cur not in ("ANSI",) and prev_l != cur and next_l != cur:
                reasons.append("label_island_vs_neighbors")

        if not reasons:
            continue

        suspects.append(
            {
                "line": i + 1,
                "reasons": reasons,
                "line_label": cur,
                "preview": _preview_line(lb),
                "has_replacement_triplet": REPLACEMENT_UTF8 in lb,
            }
        )

    triplet_total = raw_without_bom.count(REPLACEMENT_UTF8) if raw_without_bom is not None else 0
    return {
        "status": "success",
        "input_file": input_file,
        "total_lines": n,
        "suspect_line_count": len(suspects),
        "bom": bom_info or "unknown",
        "replacement_triplet_total": triplet_total,
        "suspects": suspects,
        "notes_zh": [
            "可疑行由字节级启发式汇总，非语义判定；宜结合 suspect-lines 结果对单行跑 reverse-try。",
            "含 replacement_utf8 的行可能已丢字节，逆向链不一定能恢复，需 golden/文档。",
        ],
    }


def build_suspect_report(path: str, mix_threshold: float) -> Dict[str, Any]:
    """
    仅标「与周围或字节特征不一致」的行，便于合并冲突/局部错存场景聚焦处理。
    """
    rows, bom_info, raw_without_bom = read_and_split(path)
    return build_suspect_report_from_rows(
        rows,
        mix_threshold,
        input_file=path,
        bom_info=bom_info,
        raw_without_bom=raw_without_bom,
    )
