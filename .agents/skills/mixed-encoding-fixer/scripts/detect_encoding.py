#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
编码检测脚本：整文件标签 gbk / utf-8 / mix / right / unknown。
算法实现见 mixed_encoding_fixer.whole_file_label。
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from mixed_encoding_fixer.errors import emit_error
from mixed_encoding_fixer.whole_file_label import label_from_bytes
from mixed_encoding_fixer.win_console import try_reconfigure_stdio_utf8


def detect_encoding(file_path: str) -> str:
    """读取文件并返回整文件标签（读盘失败时返回 unknown）。"""
    try:
        with open(file_path, "rb") as f:
            return label_from_bytes(f.read())
    except OSError:
        return "unknown"


def _exit_code_for_label(label: str) -> int:
    if label == "mix":
        return 2
    if label == "unknown":
        return 3
    return 0


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="整文件编码标签：gbk / utf-8 / mix / right / unknown",
    )
    p.add_argument("file_path", help="文件路径")
    p.add_argument(
        "--json",
        action="store_true",
        help="仅向 stdout 输出一行 JSON（含 label、建议退出码）",
    )
    return p


def main() -> None:
    try_reconfigure_stdio_utf8()
    args = _build_arg_parser().parse_args()
    path = args.file_path

    if not os.path.isfile(path):
        if args.json:
            emit_error(
                "FILE_NOT_FOUND",
                "Input file does not exist",
                ["Check file path", "Use absolute path"],
            )
        else:
            print(f"错误: 文件不存在 {path}", file=sys.stderr)
        raise SystemExit(1)

    status = detect_encoding(path)
    code = _exit_code_for_label(status)

    if args.json:
        print(
            json.dumps(
                {
                    "status": "success",
                    "file": os.path.abspath(path),
                    "label": status,
                    "exit_code": code,
                },
                ensure_ascii=False,
            )
        )
        raise SystemExit(code)

    print(f"检测文件: {path}")
    print(f"编码状态: {status}")
    raise SystemExit(code)


if __name__ == "__main__":
    main()
