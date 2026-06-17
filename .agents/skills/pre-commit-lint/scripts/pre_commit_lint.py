"""pre-commit lint — 在 git commit 前运行 ruff，返回结构化 JSON 供 agent 消费。

用法:
    python scripts/pre_commit_lint.py          # 检查整个项目
    python scripts/pre_commit_lint.py a.py b.py # 只检查指定文件

输出 JSON 结构:
    {
      "check": { "passed": true, "errors": [...] },
      "format": { "passed": true, "unformatted": [...] },
      "all_pass": true
    }

退出码始终为 0（agent 通过 JSON 判断结果）。
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _run_ruff(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["ruff", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _parse_check_output(stdout: str) -> list[dict]:
    """解析 ruff check 的文本输出为结构化列表。"""
    if not stdout.strip():
        return []

    errors: list[dict] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^(.+?):(\d+):(\d+):\s*(\w+)\s+(.+)$", line)
        if m:
            errors.append({
                "file": m.group(1),
                "line": int(m.group(2)),
                "col": int(m.group(3)),
                "code": m.group(4),
                "message": m.group(5),
            })
    return errors


def _parse_format_output(stderr: str) -> list[str]:
    """解析 ruff format --check 输出，提取需要格式化的文件列表。"""
    unformatted: list[str] = []
    for line in stderr.splitlines():
        line = line.strip()
        if line.startswith("Would reformat:"):
            path = line[len("Would reformat:"):].strip()
            unformatted.append(path)
    return unformatted


def main() -> None:
    targets = sys.argv[1:] if len(sys.argv) > 1 else ["."]

    result_check = _run_ruff("check", *targets)
    errors = _parse_check_output(result_check.stdout)
    check_passed = len(errors) == 0

    result_fmt = _run_ruff("format", "--check", *targets)
    unformatted = _parse_format_output(result_fmt.stderr)
    fmt_passed = len(unformatted) == 0

    report = {
        "check": {"passed": check_passed, "errors": errors},
        "format": {"passed": fmt_passed, "unformatted": unformatted},
        "all_pass": check_passed and fmt_passed,
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
