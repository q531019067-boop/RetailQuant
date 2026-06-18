# -*- coding: utf-8 -*-
"""Shared metadata for mixed-encoding-fixer scripts."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

FIX_ENCODING_SUBCOMMANDS: frozenset[str] = frozenset(
    {
        "analyze",
        "apply",
        "auto",
        "byte-inspect",
        "check",
        "diff2fixes",
        "local-repair",
        "probe",
        "recover",
        "reverse-apply",
        "reverse-try",
        "suspect-lines",
        "try-decodings",
    }
)

AGENT_WORKFLOWS: List[Dict[str, Any]] = [
    {
        "id": "00-source-code-priority",
        "desc": "Source code first: delegate to sourcecode-fix-encoding",
        "argv": ["source-fix", "<FILE>"],
    },
    {"id": "01-probe", "desc": "Probe corruption summary and verdict", "argv": ["probe", "<FILE>"]},
    {
        "id": "02-byte-inspect",
        "desc": "Inspect bytes and EF BF BD statistics",
        "argv": ["byte-inspect", "--head-lines", "12", "<FILE>"],
    },
    {
        "id": "03-check-json",
        "desc": "Line-level ANSI/GBK/UTF-8/MIX distribution",
        "argv": ["check", "--json", "<FILE>"],
    },
    {"id": "04-suspect-lines", "desc": "List suspicious line numbers", "argv": ["suspect-lines", "<FILE>"]},
    {
        "id": "05-reverse-try",
        "desc": "Try reverse chains on suspicious lines",
        "argv": ["reverse-try", "--top-k", "5", "<FILE>"],
    },
    {
        "id": "06-reverse-apply",
        "desc": "Apply reverse-chain repairs to output file",
        "argv": ["reverse-apply", "<FILE>", "<OUT>"],
    },
    {
        "id": "07-local-repair",
        "desc": "One-shot try-decodings + reverse-apply",
        "argv": ["local-repair", "<FILE>", "<OUT>"],
    },
    {
        "id": "08-try-decodings",
        "desc": "Try whole-file decoding strategies",
        "argv": ["try-decodings", "<FILE>", "<OUT>"],
    },
    {"id": "09-detect-json", "desc": "Whole-file strict encoding label", "argv": ["detect", "<FILE>", "--json"]},
    {
        "id": "10-recover",
        "desc": "Recover from damaged + golden pair",
        "argv": ["recover", "<FILE>", "<GOLDEN>", "<OUT>"],
    },
    {
        "id": "11-analyze-hints",
        "desc": "Analyze with reconstruction hints",
        "argv": ["fix", "analyze", "--reconstruction-hints", "<FILE>"],
    },
    {
        "id": "12-probe-compact",
        "desc": "Compact probe output for logs",
        "argv": ["probe", "--compact", "--no-hints", "<FILE>"],
    },
    {
        "id": "13-auto-utf8",
        "desc": "Auto transcode to UTF-8 output file",
        "argv": ["auto", "-t", "utf8", "<FILE>", "<OUT>"],
    },
    {
        "id": "14-diff2fixes",
        "desc": "Generate fixes jsonl from damaged vs golden",
        "argv": ["diff2fixes", "<FILE>", "<GOLDEN>", "<FIXES>"],
    },
    {
        "id": "15-apply-fixes",
        "desc": "Apply fixes jsonl to input file",
        "argv": ["apply", "<FILE>", "<FIXES>", "<OUT>"],
    },
    {
        "id": "16-compare-files",
        "desc": "Compare two files by bytes and SHA256",
        "script": "compare_files.py",
        "argv": ["<FILE>", "<FILE_B>"],
    },
]


def validate_skill_layout(root: Path) -> tuple[bool, str]:
    tool = root / "scripts" / "mixed_encoding_tool.py"
    if not tool.is_file():
        return False, f"invalid layout, missing mixed_encoding_tool.py under {root}"
    return True, ""
