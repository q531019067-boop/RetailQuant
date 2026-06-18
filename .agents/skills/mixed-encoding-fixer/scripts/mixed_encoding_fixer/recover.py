# -*- coding: utf-8 -*-
"""diff2fixes / recover：用 UTF-8 参考稿与损坏稿对齐行号，生成 fixes 或一步写出修复文件。"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

from mixed_encoding_fixer.detect import classify_line_bytes
from mixed_encoding_fixer.io_bytes import read_and_split
from mixed_encoding_fixer.pipeline import (
    DEFAULT_MIX_THRESHOLD,
    _build_unicode_lines,
    apply_fixed_lines_to_document,
)


def read_lines_as_unicode(path: str, *, golden: bool, mix_threshold: float) -> List[str]:
    """golden=True 时按 UTF-8 严格解码每行逻辑行；False 时与 apply 相同（分类 + DP 解码）。"""
    raw_rows, _, _ = read_and_split(path)
    if golden:
        out: List[str] = []
        for b, _ in raw_rows:
            try:
                out.append(b.decode("utf-8"))
            except UnicodeDecodeError:
                out.append(b.decode("utf-8", errors="replace"))
        return out
    line_bytes_list = [r[0] for r in raw_rows]
    cls = [classify_line_bytes(b, mix_threshold) for b in line_bytes_list]
    return _build_unicode_lines(line_bytes_list, cls, mix_threshold, None)


def diff_to_fix_blocks(old_lines: List[str], new_lines: List[str]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    if len(old_lines) != len(new_lines):
        raise ValueError(
            f"line count mismatch: damaged={len(old_lines)} golden={len(new_lines)}; "
            "golden 必须与损坏稿逻辑行数一致（同一 read_and_split 语义）。"
        )
    blocks: List[Dict[str, Any]] = []
    i = 0
    n = len(old_lines)
    while i < n:
        if old_lines[i] == new_lines[i]:
            i += 1
            continue
        start = i
        while i < n and old_lines[i] != new_lines[i]:
            i += 1
        blocks.append(
            {
                "block_id": len(blocks),
                "start_line": start + 1,
                "end_line": i,
                "fixed_lines": new_lines[start:i],
            }
        )
    changed = sum(b["end_line"] - b["start_line"] + 1 for b in blocks)
    meta = {"total_lines": n, "changed_line_count": changed, "block_count": len(blocks)}
    return blocks, meta
