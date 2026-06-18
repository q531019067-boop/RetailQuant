#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""打印本 skill 根目录（含 scripts/、SKILL.md 的目录），供 Agent 拼出 mixed_encoding_tool 的绝对路径。

本脚本位于 ``<SKILL_ROOT>/scripts/``，故 ``SKILL_ROOT = Path(__file__).resolve().parent.parent``。

用法::

    python scripts/resolve_skill_root.py
    python scripts/resolve_skill_root.py --json

Agent：在仓库内可用相对路径执行，例如::

    python .cursor/skills/mixed-encoding-fixer/scripts/resolve_skill_root.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_sd = str(_SCRIPT_DIR)
if _sd not in sys.path:
    sys.path.insert(0, _sd)

from mixed_encoding_fixer.skill_meta import validate_skill_layout  # noqa: E402


def skill_root() -> Path:
    return Path(__file__).resolve().parent.parent


def main() -> int:
    ap = argparse.ArgumentParser(description="Print mixed-encoding-fixer skill root directory.")
    ap.add_argument("--json", action="store_true", help="stdout one-line JSON with skill_root (UTF-8 bytes)")
    args = ap.parse_args()
    root = skill_root()
    ok, msg = validate_skill_layout(root)
    if not ok:
        sys.stderr.write(f"resolve_skill_root: {msg}\n")
        return 1
    if args.json:
        line = json.dumps({"skill_root": str(root)}, ensure_ascii=False) + "\n"
        sys.stdout.buffer.write(line.encode("utf-8"))
    else:
        print(root, end="")
        if not str(root).endswith("\n"):
            print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
