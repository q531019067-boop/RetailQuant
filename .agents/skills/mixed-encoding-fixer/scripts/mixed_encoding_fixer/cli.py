# -*- coding: utf-8 -*-
"""fix_encoding 子命令：analyze / check / auto / apply。"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from mixed_encoding_fixer.detect import classify_line_bytes, count_encodings
from mixed_encoding_fixer.errors import emit_error, emit_verbose
from mixed_encoding_fixer.io_bytes import read_and_split
from mixed_encoding_fixer.pipeline import (
    DEFAULT_CONTEXT_LINES,
    DEFAULT_MIX_THRESHOLD,
    LineCountMismatchError,
    NeedsReconstructionError,
    analyze_document,
    apply_fixed_lines_to_document,
    file_encoding_distribution_and_corruption,
    iter_fixes_jsonl,
    run_auto_write,
)
from mixed_encoding_fixer.local_repair import (
    run_local_repair,
    run_reverse_apply,
    run_try_decodings,
)
from mixed_encoding_fixer.recover import diff_to_fix_blocks, read_lines_as_unicode
from mixed_encoding_fixer.reverse_chains import (
    parse_line_ranges,
    reverse_try_from_text,
)
from mixed_encoding_fixer.suspect import build_suspect_report, build_suspect_report_from_rows

_LINE_LABEL_ORDER = ("ANSI", "GBK", "UTF-8", "MIX")
_FILE_SUGGESTIONS = ["Check file path", "Use absolute path"]


def _fail(code: str, message: str, suggestions: Optional[List[str]] = None) -> int:
    emit_error(code, message, suggestions or [])
    return 1


def _validate_mix(m: float) -> bool:
    return 0.0 <= m <= 1.0


def _require_mix(m: float) -> Optional[int]:
    if _validate_mix(m):
        return None
    return _fail("INVALID_PARAM", "mix-threshold must be between 0 and 1", ["Use -m in [0,1]"])


def _require_input_file(path: str) -> Optional[int]:
    if os.path.isfile(path):
        return None
    return _fail("FILE_NOT_FOUND", "Input file does not exist", _FILE_SUGGESTIONS)


def _print_json(obj: Dict[str, Any]) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def _target_optional(args: Any) -> Optional[str]:
    t = getattr(args, "target", None)
    return t.lower() if t else None


def _run_probe(input_path: str, mix_threshold: float, *, compact: bool = False, no_hints: bool = False) -> int:
    """Shared probe logic: read file once, output distribution + corruption JSON."""
    try:
        dist, corruption, n_dp = file_encoding_distribution_and_corruption(input_path, mix_threshold)
    except Exception as ex:
        return _fail(
            "INTERNAL_ERROR",
            str(ex),
            ["Verify file is readable", "If reproducible, report with a minimal sample"],
        )
    payload: Dict[str, Any] = {
        "status": "success",
        "input_file": input_path,
        "distribution": dist,
        "decode_dp_fallback_lines": n_dp,
        "corruption": {
            "replacement_utf8_triplet_count": corruption["replacement_utf8_triplet_count"],
            "lines_with_replacement_triplet": corruption["lines_with_replacement_triplet"],
            "total_bytes": corruption["total_bytes"],
            "total_lines": corruption["total_lines"],
            "strict_utf8_invalid_line_count": corruption["strict_utf8_invalid_line_count"],
            "verdict": corruption["verdict"],
            "auto_recommended": corruption["auto_recommended"],
        },
        "auto_recommended": corruption["auto_recommended"],
    }
    if not no_hints:
        payload["agent_next_steps_zh"] = _agent_next_steps_zh(corruption, n_dp)
    if compact:
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _line_distribution(path: str, mix_threshold: float) -> Dict[str, int]:
    rows, _, _ = read_and_split(path)
    cls = [classify_line_bytes(r[0], mix_threshold) for r in rows]
    counts = count_encodings(cls)
    return {k: counts.get(k, 0) for k in _LINE_LABEL_ORDER}


def cmd_analyze(args) -> int:
    if (e := _require_input_file(args.input_path)) is not None:
        return e
    if (e := _require_mix(args.mix_threshold)) is not None:
        return e
    tgt = _target_optional(args)
    emit_verbose(f"analyze: {args.input_path}", args.verbose)
    try:
        data = analyze_document(
            args.input_path,
            tgt,
            args.mix_threshold,
            args.context_lines,
            reconstruction_hints=getattr(args, "reconstruction_hints", False),
        )
    except Exception as ex:
        return _fail(
            "INTERNAL_ERROR",
            str(ex),
            [
                "Verify input path and permissions",
                "If reproducible, report with a minimal sample",
            ],
        )
    text = json.dumps({"status": "success", **data}, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    else:
        print(text)
    return 0


def cmd_check(args) -> int:
    if (e := _require_input_file(args.input_path)) is not None:
        return e
    if (e := _require_mix(args.mix_threshold)) is not None:
        return e
    use_json = args.output_format == "json" or getattr(args, "check_json", False)
    if use_json:
        return _run_probe(args.input_path, args.mix_threshold, no_hints=True)
    try:
        dist = _line_distribution(args.input_path, args.mix_threshold)
    except Exception as ex:
        return _fail(
            "INTERNAL_ERROR",
            str(ex),
            ["Verify file is readable", "If reproducible, report with a minimal sample"],
        )
    print("Encoding distribution:")
    for k in _LINE_LABEL_ORDER:
        print(f"  {k}: {dist[k]}")
    return 0


def _agent_next_steps_zh(corruption: Dict[str, Any], n_dp: int) -> List[str]:
    """面向 Agent 的下一步中文短句（经验规则，非算法输出）。"""
    v = corruption.get("verdict") or ""
    out: List[str] = []
    if v == "needs_reconstruction":
        out.append(
            "文件含 UTF-8 替换序列 EF BF BD（常见为曾用 U+FFFD 落盘），勿指望 auto 恢复中文语义。"
        )
        out.append(
            "仍可先本地试：try-decodings（整文件 gb18030/gbk）、local-repair（整文件尝试 + reverse-apply）；"
            "无 U+FFFD 的乱码行 reverse-apply 常能自动修。"
        )
        out.append(
            "先跑 suspect-lines 聚焦异常行；对无替换字节的乱码行可试 reverse-try / reverse-apply --only-suspect。"
        )
        out.append(
            "若有同逻辑行数的 UTF-8 参考稿（golden），可一步：fix_encoding recover <损坏> <golden> <输出>。"
        )
        out.append(
            "需看磁盘原始字节时用子命令 byte-inspect（含 EF BF BD 计数与前几行 hex），勿手写 python -c 读二进制。"
        )
        out.append("优先从 git/备份取源文件；无备份则对照文档重写注释；Lua 可跑 analyze --reconstruction-hints。")
    elif v == "mixed_binary_corruption":
        out.append("多行严格 UTF-8 失败且存在 MIX/DP 回退，auto 风险高。")
        out.append("建议 full analyze 查看 blocks，再 fixes.jsonl + apply 或结合上下文人工重建。")
    else:
        out.append(
            "损坏评估为可转码级：可先 local-repair 或 auto -t utf8/-t gbk，仍乱再 analyze / reverse-apply。"
        )
    if n_dp > 0:
        out.append(
            f"有 {n_dp} 行在名义编码下严格解码失败、已走行内 DP；详情见完整 analyze 的 statistics.hints。"
        )
    return out


def cmd_probe(args) -> int:
    """轻量诊断：不跑 analyze 全量块，只给分布 + corruption + 建议下一步。"""
    if (e := _require_input_file(args.input_path)) is not None:
        return e
    if (e := _require_mix(args.mix_threshold)) is not None:
        return e
    return _run_probe(
        args.input_path,
        args.mix_threshold,
        compact=getattr(args, "probe_compact", False),
        no_hints=getattr(args, "probe_no_hints", False),
    )


def cmd_byte_inspect(args) -> int:
    """原始字节级摘要：EF BF BD 计数、前几行 hex 前缀；供 Agent 替代手写 ``python -c``。"""
    if (e := _require_input_file(args.input_path)) is not None:
        return e
    rows, bom_info, raw_wo_bom = read_and_split(args.input_path)
    repl = b"\xef\xbf\xbd"
    triplet_count = raw_wo_bom.count(repl)
    bad_line_nums: List[int] = []
    for idx, (lb, _) in enumerate(rows, start=1):
        if repl in lb:
            bad_line_nums.append(idx)

    head_n = max(0, int(getattr(args, "byte_inspect_head_lines", 12)))
    hex_max = max(8, min(512, int(getattr(args, "byte_inspect_hex_bytes", 128))))
    max_bad = max(0, int(getattr(args, "byte_inspect_max_list", 300)))

    head_samples: List[Dict[str, Any]] = []
    for idx, (lb, _) in enumerate(rows[:head_n], start=1):
        snippet = lb[:hex_max]
        head_samples.append(
            {
                "line": idx,
                "byte_length": len(lb),
                "hex_prefix": snippet.hex(),
                "has_replacement_triplet": repl in lb,
            }
        )

    listed = bad_line_nums[:max_bad]
    payload: Dict[str, Any] = {
        "status": "success",
        "input_file": args.input_path,
        "bom": bom_info,
        "replacement_utf8_triplet_count": triplet_count,
        "lines_with_replacement_triplet": len(bad_line_nums),
        "lines_with_triplet_line_numbers": listed,
        "lines_with_triplet_truncated": len(bad_line_nums) > len(listed),
        "total_logical_lines": len(rows),
        "total_bytes_no_bom": len(raw_wo_bom),
        "head_line_byte_samples": head_samples,
        "agent_next_steps_zh": [
            "hex_prefix 为该行前若干字节的连续十六进制（两字符一字节）；含 efbfbd 即 UTF-8 替换字符 U+FFFD 落盘。",
            "若 triplet 计数很大且 probe 的 verdict 为 needs_reconstruction：优先 recover+golden / git 还原；无 golden 时按语义重写注释，勿依赖反复手写 python -c。",
        ],
    }
    if getattr(args, "byte_inspect_compact", False):
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_suspect_lines(args) -> int:
    """列出可疑行（替换字节、严格 UTF-8 失败、MIX、标签孤岛等）。"""
    if (e := _require_input_file(args.input_path)) is not None:
        return e
    if (e := _require_mix(args.mix_threshold)) is not None:
        return e
    try:
        data = build_suspect_report(args.input_path, args.mix_threshold)
    except Exception as ex:
        return _fail(
            "INTERNAL_ERROR",
            str(ex),
            ["Verify file is readable", "If reproducible, report with a minimal sample"],
        )
    _print_json(data)
    return 0


def cmd_reverse_try(args) -> int:
    """对指定行或「可疑行」尝试有限深度编码逆向链，输出打分最高的若干候选。"""
    if (e := _require_input_file(args.input_path)) is not None:
        return e
    if (e := _require_mix(args.mix_threshold)) is not None:
        return e
    max_depth = int(getattr(args, "reverse_max_depth", 3) or 3)
    top_k = int(getattr(args, "reverse_top_k", 5) or 5)
    if max_depth < 0:
        max_depth = 0
    if max_depth > 10:
        max_depth = 10
    if top_k < 1:
        top_k = 1
    if top_k > 50:
        top_k = 50

    try:
        rows, _bom, _raw = read_and_split(args.input_path)
    except Exception as ex:
        return _fail("INTERNAL_ERROR", str(ex), ["Verify file is readable"])

    n = len(rows)
    line_spec = getattr(args, "reverse_lines", None) or ""
    line_spec = line_spec.strip()

    if line_spec:
        target_lines = parse_line_ranges(line_spec, max_line=n)
    elif getattr(args, "reverse_all_non_ascii", False):
        target_lines = [i + 1 for i, (lb, _s) in enumerate(rows) if any(b > 0x7F for b in lb)]
    else:
        # Use pre-loaded rows instead of re-reading via build_suspect_report
        rep = build_suspect_report_from_rows(rows, args.mix_threshold, input_file=args.input_path)
        target_lines = [int(s["line"]) for s in rep.get("suspects") or []]

    results: List[Dict[str, Any]] = []
    for ln in target_lines:
        if ln < 1 or ln > n:
            continue
        lb = rows[ln - 1][0]
        start = lb.decode("utf-8", errors="replace")
        cands = reverse_try_from_text(start, max_depth=max_depth, top_k=top_k)
        results.append(
            {
                "line": ln,
                "input_preview": start[:200] + ("…" if len(start) > 200 else ""),
                "candidates": [
                    {
                        "text": c.text,
                        "score": c.score,
                        "chain": c.chain,
                    }
                    for c in cands
                ],
            }
        )

    out: Dict[str, Any] = {
        "status": "success",
        "input_file": args.input_path,
        "max_depth": max_depth,
        "top_k": top_k,
        "lines_tried": len(results),
        "results": results,
        "notes_zh": [
            "score 仅启发式（偏 CJK）；chain 为空表示原串在候选中。",
            "含 U+FFFD 的输入通常无法靠逆向恢复语义，请改用 golden/recover 或人工。",
        ],
    }
    _print_json(out)
    return 0


def cmd_try_decodings(args) -> int:
    """整文件 strict UTF-8 → gb18030/gbk（行数一致）→ replace；写出 UTF-8。"""
    if (e := _require_input_file(args.input_path)) is not None:
        return e
    try:
        detail = run_try_decodings(args.input_path, args.output_path)
    except OSError as ex:
        return _fail("IO_ERROR", str(ex), ["Check permissions and disk space"])
    except Exception as ex:
        return _fail(
            "INTERNAL_ERROR",
            str(ex),
            ["Verify input/output paths", "If reproducible, report with a minimal sample"],
        )
    _print_json(detail)
    return 0


def cmd_reverse_apply(args) -> int:
    """对解码后的行自动应用 reverse_try 最优链（无 U+FFFD 的行）。"""
    if (e := _require_input_file(args.input_path)) is not None:
        return e
    if (e := _require_mix(args.mix_threshold)) is not None:
        return e
    max_depth = int(getattr(args, "local_max_depth", 3) or 3)
    top_k = int(getattr(args, "local_top_k", 5) or 5)
    min_delta = float(getattr(args, "local_min_score_delta", 1.0) or 1.0)
    if max_depth < 0:
        max_depth = 0
    if max_depth > 10:
        max_depth = 10
    if top_k < 1:
        top_k = 1
    try:
        detail = run_reverse_apply(
            args.input_path,
            args.output_path,
            args.mix_threshold,
            max_depth=max_depth,
            top_k=top_k,
            min_score_delta=min_delta,
            only_suspect=getattr(args, "local_only_suspect", False),
            skip_whole_file_try=getattr(args, "reverse_apply_skip_whole", False),
        )
    except OSError as ex:
        return _fail("IO_ERROR", str(ex), ["Check permissions and disk space"])
    except Exception as ex:
        return _fail(
            "INTERNAL_ERROR",
            str(ex),
            ["Verify paths", "If reproducible, report with a minimal sample"],
        )
    _print_json(detail)
    return 0


def cmd_local_repair(args) -> int:
    """try-decodings + reverse-apply 一键流水线。"""
    if (e := _require_input_file(args.input_path)) is not None:
        return e
    if (e := _require_mix(args.mix_threshold)) is not None:
        return e
    max_depth = int(getattr(args, "local_max_depth", 3) or 3)
    top_k = int(getattr(args, "local_top_k", 5) or 5)
    min_delta = float(getattr(args, "local_min_score_delta", 1.0) or 1.0)
    if max_depth < 0:
        max_depth = 0
    if max_depth > 10:
        max_depth = 10
    if top_k < 1:
        top_k = 1
    try:
        detail = run_local_repair(
            args.input_path,
            args.output_path,
            args.mix_threshold,
            skip_try_decodings=getattr(args, "local_skip_try_decodings", False),
            skip_reverse_apply=getattr(args, "local_skip_reverse_apply", False),
            max_depth=max_depth,
            top_k=top_k,
            min_score_delta=min_delta,
            only_suspect=getattr(args, "local_only_suspect", False),
        )
    except OSError as ex:
        return _fail("IO_ERROR", str(ex), ["Check permissions and disk space"])
    except Exception as ex:
        return _fail(
            "INTERNAL_ERROR",
            str(ex),
            ["Verify paths", "If reproducible, report with a minimal sample"],
        )
    _print_json(detail)
    return 0


def cmd_auto(args) -> int:
    if (e := _require_input_file(args.input_path)) is not None:
        return e
    if (e := _require_mix(args.mix_threshold)) is not None:
        return e
    tgt = _target_optional(args)
    fail_nr = getattr(args, "fail_if_needs_reconstruction", False)
    try:
        data = run_auto_write(
            args.input_path,
            args.output_path,
            tgt,
            args.mix_threshold,
            context_lines=DEFAULT_CONTEXT_LINES,
            fail_if_needs_reconstruction=fail_nr,
        )
    except NeedsReconstructionError as ex:
        emit_error(
            "NEEDS_RECONSTRUCTION",
            "verdict is needs_reconstruction; output file not written (--fail-if-needs-reconstruction).",
            list(ex.corruption.get("suggestions") or []),
        )
        return 2
    except OSError as ex:
        return _fail("IO_ERROR", str(ex), ["Check permissions and disk space"])
    except Exception as ex:
        return _fail(
            "INTERNAL_ERROR",
            str(ex),
            [
                "Verify input/output paths",
                "If reproducible, report with a minimal sample",
            ],
        )
    corruption = data["corruption"]
    auto_ok = data["auto_recommended"]
    out: Dict[str, Any] = {
        "status": "success",
        "input_file": args.input_path,
        "output_file": args.output_path,
        "target_encoding": data["target_encoding"],
        "statistics": data["statistics"],
        "total_lines": data["total_lines"],
        "blocks_remaining": len(data["blocks"]),
        "corruption": corruption,
        "auto_recommended": auto_ok,
    }
    if not auto_ok:
        sug = corruption.get("suggestions") or []
        out["auto_discouraged_reason"] = (
            sug[0]
            if sug
            else "auto 不推荐用于本文件；请查看 corruption.verdict 与 corruption.suggestions。"
        )
    _print_json(out)
    return 0


def cmd_apply(args) -> int:
    if (e := _require_input_file(args.input_path)) is not None:
        return e
    if not os.path.isfile(args.fixes_file):
        return _fail(
            "FILE_NOT_FOUND",
            "Fixes file does not exist",
            ["Check fixes JSONL path"],
        )
    try:
        fixes = list(iter_fixes_jsonl(args.fixes_file))
    except Exception as ex:
        return _fail(
            "INVALID_FIXES",
            str(ex),
            ["Ensure fixes_file is UTF-8 JSONL with one object per line"],
        )
    try:
        detail = apply_fixed_lines_to_document(
            args.input_path,
            fixes,
            args.output_path,
            force=args.force,
            mix_threshold=DEFAULT_MIX_THRESHOLD,
        )
    except LineCountMismatchError as ex:
        return _fail(
            "MISMATCH_LINES",
            str(ex),
            [
                "Ensure fixed_lines length matches block line count",
                "Or pass --force to skip invalid blocks",
            ],
        )
    except OSError as ex:
        return _fail("IO_ERROR", str(ex), ["Check permissions and disk space"])
    except Exception as ex:
        return _fail(
            "INTERNAL_ERROR",
            str(ex),
            [
                "Verify input/fixes/output paths",
                "If reproducible, report with a minimal sample",
            ],
        )
    _print_json(
        {
            "status": "success",
            "message": "Fixes applied",
            "lines_fixed": detail["lines_fixed"],
            "blocks_applied": detail["blocks_applied"],
            "output_file": detail["output_file"],
            "target_encoding": detail["target_encoding"],
        }
    )
    return 0


def cmd_diff2fixes(args) -> int:
    if (e := _require_input_file(args.damaged_path)) is not None:
        return e
    if (e := _require_input_file(args.golden_path)) is not None:
        return e
    if (e := _require_mix(args.mix_threshold)) is not None:
        return e
    try:
        old_l = read_lines_as_unicode(
            args.damaged_path, golden=False, mix_threshold=args.mix_threshold
        )
        new_l = read_lines_as_unicode(
            args.golden_path, golden=True, mix_threshold=args.mix_threshold
        )
        blocks, meta = diff_to_fix_blocks(old_l, new_l)
    except ValueError as ex:
        return _fail(
            "LINE_COUNT_MISMATCH",
            str(ex),
            [
                "用与损坏稿相同的换行语义生成 golden（逻辑行数须一致）",
                "可先对两文件各跑一次 probe 看 total_lines（analyze 的 total_lines）",
            ],
        )
    except Exception as ex:
        return _fail(
            "INTERNAL_ERROR",
            str(ex),
            ["Verify paths are readable UTF-8 / mixed-encoding files"],
        )
    try:
        with open(args.output_jsonl, "w", encoding="utf-8") as f:
            for b in blocks:
                f.write(json.dumps(b, ensure_ascii=False) + "\n")
    except OSError as ex:
        return _fail("IO_ERROR", str(ex), ["Check output path and permissions"])
    _print_json(
        {
            "status": "success",
            "output_file": args.output_jsonl,
            "damaged_file": args.damaged_path,
            "golden_file": args.golden_path,
            **meta,
        }
    )
    return 0


def cmd_recover(args) -> int:
    if (e := _require_input_file(args.damaged_path)) is not None:
        return e
    if (e := _require_input_file(args.golden_path)) is not None:
        return e
    if (e := _require_mix(args.mix_threshold)) is not None:
        return e
    try:
        old_l = read_lines_as_unicode(
            args.damaged_path, golden=False, mix_threshold=args.mix_threshold
        )
        new_l = read_lines_as_unicode(
            args.golden_path, golden=True, mix_threshold=args.mix_threshold
        )
        blocks, meta = diff_to_fix_blocks(old_l, new_l)
        detail = apply_fixed_lines_to_document(
            args.damaged_path,
            blocks,
            args.output_path,
            args.force,
            mix_threshold=args.mix_threshold,
        )
    except ValueError as ex:
        return _fail(
            "LINE_COUNT_MISMATCH",
            str(ex),
            [
                "golden 必须与损坏稿逻辑行数一致",
                "本 skill 的 case_study 提供 DaFuWeng 示例 golden 生成脚本",
            ],
        )
    except LineCountMismatchError as ex:
        return _fail(
            "MISMATCH_LINES",
            str(ex),
            ["内部错误：recover 生成的块行数应自洽，请报告复现步骤"],
        )
    except OSError as ex:
        return _fail("IO_ERROR", str(ex), ["Check permissions and disk space"])
    except Exception as ex:
        return _fail(
            "INTERNAL_ERROR",
            str(ex),
            ["Verify paths", "If reproducible, report with a minimal sample"],
        )
    _print_json(
        {
            "status": "success",
            "message": "Recovered from golden (diff + apply)",
            "output_file": detail["output_file"],
            "lines_fixed": detail["lines_fixed"],
            "blocks_applied": detail["blocks_applied"],
            "target_encoding": detail["target_encoding"],
            "damaged_file": args.damaged_path,
            "golden_file": args.golden_path,
            **meta,
        }
    )
    return 0
