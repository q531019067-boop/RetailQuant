# -*- coding: utf-8 -*-
"""本地启发式修复：整文件编码尝试、逆向链自动落盘（减少对 LLM 的依赖）。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from mixed_encoding_fixer.detect import classify_line_bytes
from mixed_encoding_fixer.io_bytes import read_and_split, split_raw_bytes, write_output_lines
from mixed_encoding_fixer.pipeline import _build_unicode_lines
from mixed_encoding_fixer.reverse_chains import (
    reverse_try_from_text,
    score_recovery_candidate,
    select_reverse_apply_candidate,
)
from mixed_encoding_fixer.suspect import build_suspect_report, build_suspect_report_from_rows


def whole_file_decode_strategy(raw_body: bytes) -> Tuple[str, bytes]:
    """
    返回 (策略名, 保持原换行结构的 UTF-8 字节正文)。

    - 整段 strict UTF-8：返回 (utf-8-strict, raw_body)。
    - 否则尝试 gb18030 / gbk；仅当转 UTF-8 后逻辑行数与原文一致时采用，避免错位。
    - 否则 utf-8 replace 后 encode（utf-8-replace）。
    """
    try:
        raw_body.decode("utf-8")
        return ("utf-8-strict", raw_body)
    except UnicodeDecodeError:
        pass
    nlines_orig = len(split_raw_bytes(raw_body))
    for name, enc in (("gb18030", "gb18030"), ("gbk", "gbk")):
        try:
            s = raw_body.decode(enc)
        except UnicodeDecodeError:
            continue
        ub = s.encode("utf-8")
        if len(split_raw_bytes(ub)) == nlines_orig:
            return (name, ub)
    s = raw_body.decode("utf-8", errors="replace")
    return ("utf-8-replace", s.encode("utf-8"))


def _unicode_lines_from_utf8_rows(rows: List[Tuple[bytes, bytes]]) -> List[str]:
    return [lb.decode("utf-8") for lb, _sep in rows]


def build_unicode_lines_for_local_repair(
    path: str,
    mix_threshold: float,
    *,
    skip_whole_file_try: bool = False,
) -> Tuple[List[str], List[bytes], object, str]:
    """
    读盘并得到有效 Unicode 行（优先整文件 gbk/gb18030，再回退行级 pipeline）。
    返回 (unicode_lines, seps, bom_info, decode_strategy)。
    """
    rows, bom, raw_body = read_and_split(path)
    seps = [r[1] for r in rows]

    if not skip_whole_file_try:
        strat, body_utf8 = whole_file_decode_strategy(raw_body)
        rows2 = split_raw_bytes(body_utf8)
        if len(rows2) == len(rows) and strat in ("gb18030", "gbk", "utf-8-strict", "utf-8-replace"):
            return _unicode_lines_from_utf8_rows(rows2), seps, bom, strat

    line_bytes_list = [r[0] for r in rows]
    cls = [classify_line_bytes(b, mix_threshold) for b in line_bytes_list]
    lines = _build_unicode_lines(line_bytes_list, cls, mix_threshold, None)
    return lines, seps, bom, "pipeline"


def reverse_apply_lines(
    unicode_lines: List[str],
    *,
    line_numbers: Optional[Set[int]] = None,
    max_depth: int = 3,
    top_k: int = 5,
    min_score_delta: float = 1.0,
) -> Tuple[List[str], Dict[str, Any]]:
    """
    对不含 U+FFFD 的行尝试 reverse_try；在达到 score 阈值的前提下**优先更短逆向链**再落盘（抑制多步链噪声）。

    line_numbers: 1-based 行号集合；None 表示全部行。
    """
    out = list(unicode_lines)
    changed: List[int] = []
    skipped_fffd: List[int] = []
    for i, line in enumerate(unicode_lines):
        ln = i + 1
        if line_numbers is not None and ln not in line_numbers:
            continue
        if "\ufffd" in line:
            skipped_fffd.append(ln)
            continue
        orig_score = score_recovery_candidate(line, reference=line)
        eff_top_k = max(int(top_k), 48)
        cands = reverse_try_from_text(line, max_depth=max_depth, top_k=eff_top_k)
        if not cands:
            continue
        best = select_reverse_apply_candidate(
            cands,
            start_line=line,
            orig_score=orig_score,
            min_score_delta=min_score_delta,
        )
        if best is None:
            continue
        out[i] = best.text
        changed.append(ln)

    meta = {
        "lines_changed": len(changed),
        "changed_line_numbers": changed,
        "skipped_u_fffd_lines": skipped_fffd,
    }
    return out, meta


def _decode_try_decodings_rows(
    rows: List[Tuple[bytes, bytes]],
    raw_body: bytes,
) -> Tuple[str, List[str], List[bytes], Optional[str]]:
    """
    与 ``whole_file_decode_strategy`` 一致地得到 Unicode 逻辑行；行数不一致时逐行 UTF-8 replace。
    返回 (strategy, unicode_lines, seps, note)；note 仅在不一致分支有说明。
    """
    seps = [r[1] for r in rows]
    strat, body_utf8 = whole_file_decode_strategy(raw_body)
    rows_out = split_raw_bytes(body_utf8)
    if len(rows_out) != len(rows):
        lines = [r[0].decode("utf-8", errors="replace") for r in rows]
        return (
            "utf-8-replace-per-line",
            lines,
            seps,
            "整文件转码后行数与原文不一致，已按原结构逐行 UTF-8 replace 写出。",
        )
    return strat, _unicode_lines_from_utf8_rows(rows_out), seps, None


def run_try_decodings(path_in: str, path_out: str) -> Dict[str, Any]:
    """
    整文件尝试 utf-8 strict → gb18030/gbk（行数须一致）→ utf-8 replace；写出 UTF-8 目标文件。
    """
    rows, bom, raw_body = read_and_split(path_in)
    strat, unicode_lines, seps, note = _decode_try_decodings_rows(rows, raw_body)
    line_objs = [{"text": t} for t in unicode_lines]
    write_output_lines(path_out, line_objs, seps, "utf-8", keep_bom=True, bom_info=bom)
    out: Dict[str, Any] = {
        "status": "success",
        "strategy": strat,
        "output_file": path_out,
        "lines": len(rows),
    }
    if note:
        out["note"] = note
    return out


def run_reverse_apply(
    path_in: str,
    path_out: str,
    mix_threshold: float,
    *,
    max_depth: int = 3,
    top_k: int = 5,
    min_score_delta: float = 1.0,
    only_suspect: bool = False,
    skip_whole_file_try: bool = False,
) -> Dict[str, Any]:
    unicode_lines, seps, bom, strat = build_unicode_lines_for_local_repair(
        path_in, mix_threshold, skip_whole_file_try=skip_whole_file_try
    )
    line_numbers: Optional[Set[int]] = None
    if only_suspect:
        # Re-read once and reuse rows for both unicode lines and suspect detection
        rows, _bom2, raw_body = read_and_split(path_in)
        rep = build_suspect_report_from_rows(rows, mix_threshold, input_file=path_in)
        line_numbers = {int(s["line"]) for s in (rep.get("suspects") or [])}
    fixed, meta = reverse_apply_lines(
        unicode_lines,
        line_numbers=line_numbers,
        max_depth=max_depth,
        top_k=top_k,
        min_score_delta=min_score_delta,
    )
    line_objs = [{"text": t} for t in fixed]
    write_output_lines(path_out, line_objs, seps, "utf-8", keep_bom=True, bom_info=bom)
    return {
        "status": "success",
        "input_file": path_in,
        "output_file": path_out,
        "decode_strategy": strat,
        "target_encoding": "utf8",
        **meta,
    }


def run_local_repair(
    path_in: str,
    path_out: str,
    mix_threshold: float,
    *,
    skip_try_decodings: bool = False,
    skip_reverse_apply: bool = False,
    max_depth: int = 3,
    top_k: int = 5,
    min_score_delta: float = 1.0,
    only_suspect: bool = False,
) -> Dict[str, Any]:
    """组合：整文件编码尝试 + reverse-apply，一次写出。"""
    unicode_lines, seps, bom, strat = build_unicode_lines_for_local_repair(
        path_in,
        mix_threshold,
        skip_whole_file_try=skip_try_decodings,
    )
    meta_reverse: Dict[str, Any] = {}
    if not skip_reverse_apply:
        line_numbers: Optional[Set[int]] = None
        if only_suspect:
            # Re-read once and reuse rows for both unicode lines and suspect detection
            rows, _bom2, _raw = read_and_split(path_in)
            rep = build_suspect_report_from_rows(rows, mix_threshold, input_file=path_in)
            line_numbers = {int(s["line"]) for s in (rep.get("suspects") or [])}
        unicode_lines, meta_reverse = reverse_apply_lines(
            unicode_lines,
            line_numbers=line_numbers,
            max_depth=max_depth,
            top_k=top_k,
            min_score_delta=min_score_delta,
        )

    line_objs = [{"text": t} for t in unicode_lines]
    write_output_lines(path_out, line_objs, seps, "utf-8", keep_bom=True, bom_info=bom)
    out: Dict[str, Any] = {
        "status": "success",
        "input_file": path_in,
        "output_file": path_out,
        "decode_strategy": strat,
        "target_encoding": "utf8",
    }
    out.update(meta_reverse)
    return out
