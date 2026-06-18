# -*- coding: utf-8 -*-
"""损坏与可修复性评估（UTF-8 替换序列、严格 UTF-8、verdict）。"""

from __future__ import annotations

from typing import Any, Dict, List

REPLACEMENT_UTF8 = b"\xef\xbf\xbd"

# needs_reconstruction：任一满足
MIN_REPLACEMENT_TRIPLETS_ABSOLUTE = 3
MIN_REPLACEMENT_LINE_RATIO = 0.02
MIN_REPLACEMENT_BYTE_RATIO = 0.001

# mixed_binary_corruption
MIN_STRICT_UTF8_FAIL_LINE_RATIO = 0.10
MIN_STRICT_UTF8_FAIL_LINES = 3

# auto_recommended：decode DP 回退过多时仍标 false
MAX_DP_FALLBACK_FOR_AUTO_RECOMMENDED = 50

_VERDICT_NEEDS_RECONSTRUCTION = "needs_reconstruction"
_VERDICT_MIXED_BINARY = "mixed_binary_corruption"
_VERDICT_RECOVERABLE = "recoverable_by_transcode"

_SUGGEST_REPLACEMENT = (
    "检测到 UTF-8 替换字节序列 EF BF BD（Unicode 替换符编码），原文字节可能已丢失，勿指望 auto 能恢复语义。"
)
_SUGGEST_GIT = "优先从 git 历史、备份或导出机取未损坏的源文件。"
_SUGGEST_DOC = "若无备份，对照设计文档/常量表重写注释；勿凭猜测修改业务逻辑。"
_SUGGEST_LUA_HINTS = "Lua 可使用 analyze --reconstruction-hints 抽取连续 `--` 注释块供 LLM 重建。"
_SUGGEST_MIXED = "多行严格 UTF-8 解码失败且存在 MIX/DP 回退，可能为二进制级混合损坏；建议人工或 LLM 对照上下文重建。"


def _strict_utf8_line_fails(line_bytes: bytes) -> bool:
    if not line_bytes:
        return False
    try:
        line_bytes.decode("utf-8")
        return False
    except UnicodeDecodeError:
        return True


def _lines_with_replacement(line_bytes_list: List[bytes]) -> int:
    return sum(1 for lb in line_bytes_list if REPLACEMENT_UTF8 in lb)


def assess_corruption(
    raw_without_bom: bytes,
    line_bytes_list: List[bytes],
    orig_counts: Dict[str, int],
    decode_dp_fallback_lines: int,
) -> Dict[str, Any]:
    total_lines = len(line_bytes_list)
    total_bytes = len(raw_without_bom)
    triplet_count = raw_without_bom.count(REPLACEMENT_UTF8)
    lines_with_rep = _lines_with_replacement(line_bytes_list)
    strict_fail = sum(1 for lb in line_bytes_list if _strict_utf8_line_fails(lb))

    orig_mix = int(orig_counts.get("MIX", 0) or 0)

    needs_rec = False
    if triplet_count >= MIN_REPLACEMENT_TRIPLETS_ABSOLUTE:
        needs_rec = True
    elif triplet_count > 0 and total_lines > 0:
        if lines_with_rep / total_lines >= MIN_REPLACEMENT_LINE_RATIO:
            needs_rec = True
    if not needs_rec and total_bytes > 0:
        if triplet_count / total_bytes >= MIN_REPLACEMENT_BYTE_RATIO:
            needs_rec = True

    verdict = _VERDICT_RECOVERABLE
    suggestions: List[str] = []

    if needs_rec:
        verdict = _VERDICT_NEEDS_RECONSTRUCTION
        suggestions = [_SUGGEST_REPLACEMENT, _SUGGEST_GIT, _SUGGEST_DOC, _SUGGEST_LUA_HINTS]
    else:
        strict_ratio = strict_fail / total_lines if total_lines else 0.0
        mix_significant = orig_mix >= 1 or decode_dp_fallback_lines >= 1
        if (
            total_lines > 0
            and strict_fail >= MIN_STRICT_UTF8_FAIL_LINES
            and strict_ratio >= MIN_STRICT_UTF8_FAIL_LINE_RATIO
            and mix_significant
        ):
            verdict = _VERDICT_MIXED_BINARY
            suggestions = [_SUGGEST_MIXED, _SUGGEST_GIT, _SUGGEST_DOC]

    auto_recommended = (
        verdict == _VERDICT_RECOVERABLE and decode_dp_fallback_lines <= MAX_DP_FALLBACK_FOR_AUTO_RECOMMENDED
    )

    return {
        "replacement_utf8_triplet_count": triplet_count,
        "lines_with_replacement_triplet": lines_with_rep,
        "total_bytes": total_bytes,
        "total_lines": total_lines,
        "strict_utf8_invalid_line_count": strict_fail,
        "verdict": verdict,
        "suggestions": suggestions,
        "auto_recommended": auto_recommended,
    }


def collect_lua_comment_spans(unicode_lines: List[str]) -> List[Dict[str, Any]]:
    """连续以 `--` 开头的逻辑行（1-based 行号）合并为块。"""
    spans: List[Dict[str, Any]] = []
    i = 0
    n = len(unicode_lines)
    while i < n:
        stripped = unicode_lines[i].lstrip(" \t")
        if stripped.startswith("--"):
            start = i
            chunk = [unicode_lines[i]]
            j = i + 1
            while j < n:
                s2 = unicode_lines[j].lstrip(" \t")
                if s2.startswith("--"):
                    chunk.append(unicode_lines[j])
                    j += 1
                else:
                    break
            spans.append(
                {
                    "start_line": start + 1,
                    "end_line": j,
                    "lines": chunk,
                }
            )
            i = j
        else:
            i += 1
    return spans
