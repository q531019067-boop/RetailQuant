#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""列出 Agent 推荐使用的 CLI 命令模板（避免手写 python -c / 路径猜错）。

默认 stdout 为 JSON；可用 ``--format lines`` 输出可直接粘贴到终端的行（已替换路径占位符）。

用法::

    python scripts/list_agent_commands.py --format json
    python scripts/list_agent_commands.py --format lines --skill-root "K:/path/to/mixed-encoding-fixer" --file "K:/a.lua" --out "K:/b.lua" --golden "K:/g.lua" --fixes "K:/fixes.jsonl" --file-b "K:/other.lua"
    python scripts/list_agent_commands.py --format ps1   # PowerShell 赋值 $SR + 示例

与 SKILL.md「Agent 工具指令」同步维护；工作流列表唯一源：``mixed_encoding_fixer/skill_meta.py`` 中 ``AGENT_WORKFLOWS``。
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import List

_SCRIPT_DIR = Path(__file__).resolve().parent
_sd = str(_SCRIPT_DIR)
if _sd not in sys.path:
    sys.path.insert(0, _sd)

from mixed_encoding_fixer.skill_meta import AGENT_WORKFLOWS  # noqa: E402


def _print_utf8(s: str, end: str = "\n") -> None:
    """Windows 管道下避免 sys.stdout 用系统代码页编码中文导致父进程 UTF-8 解码失败。"""
    sys.stdout.buffer.write((s + end).encode("utf-8"))


def _default_skill_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _tool_py(skill_root: Path) -> Path:
    return skill_root / "scripts" / "mixed_encoding_tool.py"


def _script_path(skill_root: Path, script: str) -> Path:
    return skill_root / "scripts" / script


def _substitute(
    argv: List[str],
    *,
    file_p: str,
    out_p: str,
    golden_p: str,
    fixes_p: str,
    file_b_p: str,
) -> List[str]:
    out: List[str] = []
    for a in argv:
        if a == "<FILE>":
            out.append(file_p)
        elif a == "<OUT>":
            out.append(out_p)
        elif a == "<GOLDEN>":
            out.append(golden_p)
        elif a == "<FIXES>":
            out.append(fixes_p)
        elif a == "<FILE_B>":
            out.append(file_b_p)
        else:
            out.append(a)
    return out


def _build_cmd(skill_root: Path, script: str, argv: List[str]) -> List[str]:
    exe = _script_path(skill_root, script)
    return [sys.executable, str(exe), *argv]


def main() -> int:
    ap = argparse.ArgumentParser(description="List agent CLI templates for mixed-encoding-fixer.")
    ap.add_argument(
        "--skill-root",
        default="",
        help="Skill root (default: infer from this script location)",
    )
    ap.add_argument("--file", default="<FILE>", metavar="PATH", help="Substitute <FILE>")
    ap.add_argument("--out", default="<OUT>", metavar="PATH", help="Substitute <OUT>")
    ap.add_argument("--golden", default="<GOLDEN>", metavar="PATH", help="Substitute <GOLDEN>")
    ap.add_argument("--fixes", default="<FIXES>", metavar="PATH", help="Substitute <FIXES> (apply / diff2fixes)")
    ap.add_argument(
        "--file-b", default="<FILE_B>", metavar="PATH", dest="file_b", help="Substitute <FILE_B> (compare_files)"
    )
    ap.add_argument("--format", choices=("json", "lines", "ps1"), default="json")
    args = ap.parse_args()

    sr = Path(args.skill_root).resolve() if args.skill_root else _default_skill_root()
    if not _tool_py(sr).is_file():
        sys.stderr.write(f"list_agent_commands: missing {_tool_py(sr)}\n")
        return 1

    rows = []
    for w in AGENT_WORKFLOWS:
        argv_sub = _substitute(
            w["argv"],
            file_p=args.file,
            out_p=args.out,
            golden_p=args.golden,
            fixes_p=args.fixes,
            file_b_p=args.file_b,
        )
        script = w.get("script", "mixed_encoding_tool.py")
        sp = _script_path(sr, script)
        if not sp.is_file():
            sys.stderr.write(f"list_agent_commands: missing {sp}\n")
            return 1
        cmd_list = _build_cmd(sr, script, argv_sub)
        rows.append(
            {
                "id": w["id"],
                "description_zh": w["desc"],
                "script": script,
                "argv_after_script": argv_sub,
                "cmd": cmd_list,
                "shell_posix": shlex.join(cmd_list),
                "shell_windows": subprocess.list2cmdline(cmd_list),
            }
        )

    if args.format == "json":
        _print_utf8(json.dumps({"skill_root": str(sr), "workflows": rows}, ensure_ascii=False, indent=2))
    elif args.format == "lines":
        for r in rows:
            _print_utf8(f"# {r['id']}: {r['description_zh']}")
            line = r["shell_windows"] if sys.platform == "win32" else r["shell_posix"]
            _print_utf8(line)
            _print_utf8("")
    else:
        # ps1: set variable and one example
        _print_utf8(f'$MEF_SKILL_ROOT = "{sr}"')
        _print_utf8(f'$MEF_TOOL = Join-Path $MEF_SKILL_ROOT "scripts/mixed_encoding_tool.py"')
        _print_utf8("# 示例 probe：")
        _print_utf8('python $MEF_TOOL probe "<FILE>"')

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
