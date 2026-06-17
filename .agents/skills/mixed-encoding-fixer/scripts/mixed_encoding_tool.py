#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unified CLI entry for mixed-encoding-fixer."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_DIR = Path(__file__).resolve().parent
_FIX = _DIR / "fix_encoding.py"
_DETECT = _DIR / "detect_encoding.py"
_SOURCE_FIX_REL = Path("Source/Tools/AITools/SKILLS/sourcecode-fix-encoding/scripts/fix_encoding.py")

_sd = str(_DIR)
if _sd not in sys.path:
    sys.path.insert(0, _sd)

from mixed_encoding_fixer.skill_meta import FIX_ENCODING_SUBCOMMANDS as _FIX_SUBCOMMANDS  # noqa: E402


def _usage() -> str:
    return (
        "Usage:\n"
        "  python mixed_encoding_tool.py <subcommand> ...\n"
        "  python mixed_encoding_tool.py fix <subcommand> ...\n"
        "  python mixed_encoding_tool.py detect <file> [--json]\n"
        "  python mixed_encoding_tool.py source-fix <path> [--backup ...] [--dry-run]\n"
    )


def _resolve_source_fix_script() -> Path:
    return Path.cwd() / _SOURCE_FIX_REL


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        sys.stderr.write(_usage())
        return 1
    if not _FIX.is_file():
        sys.stderr.write(f"mixed_encoding_tool: missing {_FIX}\n")
        return 1
    if not _DETECT.is_file():
        sys.stderr.write(f"mixed_encoding_tool: missing {_DETECT}\n")
        return 1

    head = argv[0]
    tail = argv[1:]

    if head == "detect":
        return subprocess.call([sys.executable, str(_DETECT), *tail])

    if head == "fix":
        if not tail:
            sys.stderr.write("mixed_encoding_tool: `fix` needs a subcommand\n")
            return 1
        return subprocess.call([sys.executable, str(_FIX), *tail])

    if head == "source-fix":
        if not tail:
            sys.stderr.write("mixed_encoding_tool: `source-fix` needs a file or directory path\n")
            return 1
        source_fix = _resolve_source_fix_script()
        if not source_fix.is_file():
            sys.stderr.write(f"mixed_encoding_tool: missing sourcecode-fix-encoding script {source_fix}\n")
            return 1
        return subprocess.call([sys.executable, str(source_fix), *tail])

    if head in _FIX_SUBCOMMANDS:
        return subprocess.call([sys.executable, str(_FIX), *argv])

    sys.stderr.write(f"mixed_encoding_tool: unknown subcommand {head!r}\n{_usage()}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
