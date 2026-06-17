#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""比较两个文件的二进制内容是否一致（供 Agent 替代手写 ``python -c`` 做 hash/len）。

stdout 为一行 JSON：``equal``, ``size_a``, ``size_b``, ``sha256_a``, ``sha256_b``。
任一路径不存在或非文件时 stderr JSON，退出码 2。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def _digest(p: Path) -> tuple[int, str]:
    h = hashlib.sha256()
    n = 0
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
            n += len(chunk)
    return n, h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description="Compare two files (bytes + SHA-256).")
    ap.add_argument("path_a", type=Path)
    ap.add_argument("path_b", type=Path)
    args = ap.parse_args()
    for label, p in ("path_a", args.path_a), ("path_b", args.path_b):
        if not p.is_file():
            err = {"error_code": "NOT_A_FILE", "path": str(p), "label": label}
            sys.stderr.write(json.dumps(err, ensure_ascii=False) + "\n")
            return 2
    sa, ha = _digest(args.path_a)
    sb, hb = _digest(args.path_b)
    out = {
        "equal": sa == sb and ha == hb,
        "size_a": sa,
        "size_b": sb,
        "sha256_a": ha,
        "sha256_b": hb,
    }
    sys.stdout.buffer.write(json.dumps(out, ensure_ascii=False).encode("utf-8"))
    sys.stdout.buffer.write(b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
