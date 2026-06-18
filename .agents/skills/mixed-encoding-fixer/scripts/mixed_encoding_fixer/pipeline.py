# -*- coding: utf-8 -*-
"""分析、自动修复、块收集、应用修复（FR-05～FR-07、FR-09～FR-11）。"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from mixed_encoding_fixer.corruption import assess_corruption, collect_lua_comment_spans
from mixed_encoding_fixer.detect import (
    classify_line_bytes,
    count_encodings,
    main_encoding_from_counts,
)
from mixed_encoding_fixer.dp_fix import fix_mix_line_dp
from mixed_encoding_fixer.io_bytes import read_and_split, write_output_lines

DEFAULT_MIX_THRESHOLD = 0.8
DEFAULT_CONTEXT_LINES = 5
_DP_SEG_LEN = 64

_LINE_LABEL_ORDER = ("ANSI", "GBK", "UTF-8", "MIX")


class NeedsReconstructionError(Exception):
    """auto 在 --fail-if-needs-reconstruction 且 verdict 为 needs_reconstruction 时抛出。"""

    def __init__(self, corruption: Dict[str, Any]):
        super().__init__("needs_reconstruction")
        self.corruption = corruption


def file_encoding_distribution_and_corruption(
    path: str, mix_threshold: float
) -> Tuple[Dict[str, int], Dict[str, Any], int]:
    """单次读盘 + 行级分类 + DP 回退计数，供 check --json、probe 与轻量诊断。

    返回 (distribution, corruption, decode_dp_fallback_lines)。
    """
    raw_rows, _bom, raw_body = read_and_split(path)
    line_bytes_list = [r[0] for r in raw_rows]
    orig_cls = [classify_line_bytes(b, mix_threshold) for b in line_bytes_list]
    orig_counts = count_encodings(orig_cls)
    dp_fallback_stats: Dict[str, int] = {}
    _build_unicode_lines(line_bytes_list, orig_cls, mix_threshold, dp_fallback_stats)
    n_dp = int(dp_fallback_stats.get("count", 0))
    corruption = assess_corruption(raw_body, line_bytes_list, orig_counts, n_dp)
    dist = {k: int(orig_counts.get(k, 0)) for k in _LINE_LABEL_ORDER}
    return dist, corruption, n_dp


_CLASS_TO_CODEC = {"ANSI": "ascii", "UTF-8": "utf-8", "GBK": "gbk"}

_HINTS_FIXED = (
    "target_encoding 由按行 GBK 与 UTF-8 的计数（票数）决定，ANSI 行不计票；可能与整文件 detect_encoding 的标签不一致。",
    "行级标签（ANSI/GBK/UTF-8/MIX）为启发式；MIX=0 不代表行内没有混合字节或损坏。",
)


def _statistics_hints(n_dp_fallback: int) -> List[str]:
    hints = list(_HINTS_FIXED)
    if n_dp_fallback > 0:
        hints.append(
            f"有 {n_dp_fallback} 行在名义编码（行级标签）下严格解码失败，已回退行内 DP；"
            "此后 after_auto_fix 中 MIX 仍可能为 0。"
        )
    return hints


def bytes_to_unicode(
    line_bytes: bytes,
    classification: str,
    mix_threshold: float,
    dp_fallback_stats: Optional[Dict[str, int]] = None,
) -> str:
    codec = _CLASS_TO_CODEC.get(classification)
    if codec is not None:
        try:
            return line_bytes.decode(codec)
        except UnicodeDecodeError:
            if dp_fallback_stats is not None:
                dp_fallback_stats["count"] = dp_fallback_stats.get("count", 0) + 1
            return fix_mix_line_dp(line_bytes, max_seg_len=_DP_SEG_LEN)
    return fix_mix_line_dp(line_bytes, max_seg_len=_DP_SEG_LEN)


def target_enc_name(target_key: str) -> str:
    return "utf-8" if target_key == "utf8" else "gbk"


def restore_indent(original_line: str, fixed_line: str) -> str:
    """原行为空（或仅空白）时保留 fixed_line 自带缩进，便于插入 ``end`` 等结构行。"""
    if not original_line.strip():
        return fixed_line
    m = re.match(r"^[ \t]*", original_line)
    indent = m.group(0) if m else ""
    return indent + fixed_line.lstrip(" \t")


def collect_llm_blocks(
    lines: List[Dict[str, Any]],
    unrepairable_indices: List[int],
    context_lines: int,
) -> List[Dict[str, Any]]:
    used = set()
    blocks = []
    for idx in unrepairable_indices:
        if idx in used:
            continue
        start = max(0, idx - context_lines)
        end = min(len(lines) - 1, idx + context_lines)
        block_lines = [lines[i]["text"] for i in range(start, end + 1)]
        blocks.append(
            {
                "block_id": len(blocks),
                "start_line": start + 1,
                "end_line": end + 1,
                "lines": block_lines,
            }
        )
        used.update(range(start, end + 1))
    return blocks


def _build_unicode_lines(
    line_bytes_list: List[bytes],
    classifications: List[str],
    mix_threshold: float,
    dp_fallback_stats: Optional[Dict[str, int]] = None,
) -> List[str]:
    return [bytes_to_unicode(b, c, mix_threshold, dp_fallback_stats) for b, c in zip(line_bytes_list, classifications)]


def _after_stats(unicode_lines: List[str], tgt_enc: str, mix_threshold: float) -> Tuple[Dict[str, int], List[str]]:
    after_cls = []
    for u in unicode_lines:
        bb = u.encode(tgt_enc, errors="replace")
        after_cls.append(classify_line_bytes(bb, mix_threshold))
    return count_encodings(after_cls), after_cls


def _analyze_core(
    path: str,
    target_encoding: Optional[str],
    mix_threshold: float,
    context_lines: int,
) -> Dict[str, Any]:
    raw_rows, bom, raw_body = read_and_split(path)
    line_bytes_list = [r[0] for r in raw_rows]
    seps = [r[1] for r in raw_rows]
    orig_cls = [classify_line_bytes(b, mix_threshold) for b in line_bytes_list]
    orig_counts = count_encodings(orig_cls)
    tgt_key = target_encoding or main_encoding_from_counts(orig_counts)
    if tgt_key not in ("utf8", "gbk"):
        tgt_key = "utf8"
    tgt_enc = target_enc_name(tgt_key)
    dp_fallback_stats: Dict[str, int] = {}
    unicode_lines = _build_unicode_lines(line_bytes_list, orig_cls, mix_threshold, dp_fallback_stats)
    after_counts, after_cls = _after_stats(unicode_lines, tgt_enc, mix_threshold)
    unrepairable = [i for i, c in enumerate(after_cls) if c == "MIX"]
    line_dicts = [{"text": unicode_lines[i]} for i in range(len(unicode_lines))]
    blocks = collect_llm_blocks(line_dicts, unrepairable, context_lines)
    warnings: List[Dict[str, Any]] = []
    total = len(line_bytes_list) or 1
    if orig_counts.get("MIX", 0) / total > 0.3:
        warnings.append(
            {
                "warning": "high_mix_ratio",
                "message": "More than 30% lines are MIX. Consider lowering mix-threshold with -m or enabling auto-fix.",
                "suggested_action": "Run with auto to apply heuristic fixes first, or reduce -m to 0.6",
            }
        )
    if unrepairable:
        warnings.append(
            {
                "warning": "still_mix_after_auto",
                "message": "Some lines remain MIX after heuristic repair; use blocks for LLM or increase -c context.",
                "suggested_action": "Increase --context-lines or inspect blocks manually.",
            }
        )
    n_dp = int(dp_fallback_stats.get("count", 0))
    stats = {
        "original": orig_counts,
        "after_auto_fix": after_counts,
        "decode_dp_fallback_lines": n_dp,
        "hints": _statistics_hints(n_dp),
    }
    corruption = assess_corruption(raw_body, line_bytes_list, orig_counts, n_dp)
    if corruption["verdict"] == "needs_reconstruction":
        warnings.append(
            {
                "warning": "unrecoverable_replacement_bytes",
                "message": "File contains UTF-8 replacement triplets EF BF BD; original bytes may be lost.",
                "suggested_action": "Do not rely on auto; restore from VCS/backup or rewrite text (e.g. comments) from docs.",
            }
        )
    return {
        "path": path,
        "nlines": len(line_bytes_list),
        "tgt_key": tgt_key,
        "stats": stats,
        "blocks": blocks,
        "warnings": warnings,
        "unicode_lines": unicode_lines,
        "seps": seps,
        "bom": bom,
        "corruption": corruption,
    }


def analyze_document(
    path: str,
    target_encoding: Optional[str],
    mix_threshold: float,
    context_lines: int,
    reconstruction_hints: bool = False,
) -> Dict[str, Any]:
    d = _analyze_core(path, target_encoding, mix_threshold, context_lines)
    out: Dict[str, Any] = {
        "input_file": d["path"],
        "total_lines": d["nlines"],
        "target_encoding": d["tgt_key"],
        "statistics": d["stats"],
        "blocks": d["blocks"],
        "warnings": d["warnings"],
        "corruption": d["corruption"],
        "auto_recommended": d["corruption"]["auto_recommended"],
    }
    if reconstruction_hints and d["path"].lower().endswith(".lua"):
        out["reconstruction_hints"] = {"comment_spans": collect_lua_comment_spans(d["unicode_lines"])}
    return out


def auto_fix_document(
    path: str,
    target_encoding: Optional[str],
    mix_threshold: float,
    context_lines: int,
) -> Dict[str, Any]:
    d = _analyze_core(path, target_encoding, mix_threshold, context_lines)
    return {
        "input_file": d["path"],
        "total_lines": d["nlines"],
        "target_encoding": d["tgt_key"],
        "statistics": d["stats"],
        "blocks": d["blocks"],
        "warnings": d["warnings"],
        "lines_out": [{"text": t} for t in d["unicode_lines"]],
        "seps": d["seps"],
        "bom_info": d["bom"],
        "corruption": d["corruption"],
        "auto_recommended": d["corruption"]["auto_recommended"],
    }


def run_auto_write(
    path_in: str,
    path_out: str,
    target_encoding: Optional[str],
    mix_threshold: float,
    context_lines: int,
    fail_if_needs_reconstruction: bool = False,
) -> Dict[str, Any]:
    data = auto_fix_document(path_in, target_encoding, mix_threshold, context_lines)
    c = data["corruption"]
    if fail_if_needs_reconstruction and c["verdict"] == "needs_reconstruction":
        raise NeedsReconstructionError(c)
    write_output_lines(
        path_out,
        data["lines_out"],
        data["seps"],
        target_enc_name(data["target_encoding"]),
        keep_bom=True,
        bom_info=data["bom_info"],
    )
    return data


class LineCountMismatchError(Exception):
    def __init__(self, block_id, expected, got):
        super().__init__(f"block {block_id}: expected {expected} lines, got {got}")
        self.block_id = block_id
        self.expected = expected
        self.got = got


def apply_fixed_lines_to_document(
    input_path: str,
    fixes: List[Dict[str, Any]],
    output_path: str,
    force: bool,
    mix_threshold: float = DEFAULT_MIX_THRESHOLD,
) -> Dict[str, Any]:
    raw_rows, bom, _ = read_and_split(input_path)
    line_bytes_list = [r[0] for r in raw_rows]
    seps = [r[1] for r in raw_rows]
    classifications = [classify_line_bytes(b, mix_threshold) for b in line_bytes_list]
    unicode_lines = _build_unicode_lines(line_bytes_list, classifications, mix_threshold, None)
    original = list(unicode_lines)
    total_fixed = 0
    blocks_applied = 0
    for fix in sorted(fixes, key=lambda x: x.get("start_line", 0)):
        sl = fix["start_line"] - 1
        el = fix["end_line"] - 1
        fl = fix["fixed_lines"]
        need = el - sl + 1
        if need != len(fl):
            if not force:
                raise LineCountMismatchError(fix.get("block_id", -1), need, len(fl))
            continue
        for k, pos in enumerate(range(sl, el + 1)):
            if 0 <= pos < len(unicode_lines):
                unicode_lines[pos] = restore_indent(original[pos], fl[k])
                total_fixed += 1
        blocks_applied += 1
    tgt_key = main_encoding_from_counts(count_encodings(classifications))
    tgt_enc = target_enc_name(tgt_key if tgt_key else "utf8")
    write_output_lines(
        output_path,
        [{"text": t} for t in unicode_lines],
        seps,
        tgt_enc,
        keep_bom=True,
        bom_info=bom,
    )
    return {
        "lines_fixed": total_fixed,
        "blocks_applied": blocks_applied,
        "output_file": output_path,
        "target_encoding": tgt_key,
    }


def iter_fixes_jsonl(path: str):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)
