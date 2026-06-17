"""Git 提交预检 — 检查 git status、冲突、大文件，输出结构化 JSON。

用法:
    python scripts/git_commit_check.py              # 检查当前仓库
    python scripts/git_commit_check.py --json       # JSON 输出（默认）
    python scripts/git_commit_check.py --text       # 文本输出（人类可读）

输出 JSON 结构:
    {
      "staged": [{"status": "M", "path": "..."}, ...],
      "unstaged": [{"status": "M", "path": "..."}, ...],
      "untracked": ["path", ...],
      "conflicts": ["path", ...],
      "large_files": [{"path": "...", "size_mb": 1.5}, ...],
      "warnings": ["提示信息", ...],
      "all_clear": true|false
    }
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent

# 不提示提交的忽略模式
IGNORE_PATTERNS = [
    "__pycache__/",
    "*.pyc",
    ".venv/",
    "venv/",
    ".pytest_cache/",
    ".ruff_cache/",
    "*.egg-info/",
    ".DS_Store",
    "Thumbs.db",
    "cache/rquant.db-shm",
    "cache/rquant.db-wal",
]

# 大文件阈值 (bytes)
LARGE_FILE_THRESHOLD = 1_000_000  # 1 MB


def _run_git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def _should_ignore(path: str) -> bool:
    """检查路径是否匹配忽略模式。"""
    import fnmatch
    for pattern in IGNORE_PATTERNS:
        if fnmatch.fnmatch(path, pattern) or pattern in path:
            return True
    return False


def get_staged_changes() -> list[dict]:
    """获取暂存区变更 (git diff --cached --name-status)。"""
    result = _run_git("diff", "--cached", "--name-status")
    files = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t", 1)
        if len(parts) == 2:
            status, path = parts
            if not _should_ignore(path):
                files.append({"status": status, "path": path})
    return files


def get_unstaged_changes() -> list[dict]:
    """获取工作区变更 (git diff --name-status)。"""
    result = _run_git("diff", "--name-status")
    files = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t", 1)
        if len(parts) == 2:
            status, path = parts
            if not _should_ignore(path):
                files.append({"status": status, "path": path})
    return files


def get_untracked_files() -> list[str]:
    """获取未跟踪文件 (git ls-files --others --exclude-standard)。"""
    result = _run_git("ls-files", "--others", "--exclude-standard")
    files = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if line and not _should_ignore(line):
            files.append(line)
    return files


def check_conflicts() -> list[str]:
    """检测冲突标记 (git diff --check)。"""
    result = _run_git("diff", "--check")
    conflicts = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if line and "leftover conflict marker" in line.lower():
            # 格式: path:line: leftover conflict marker
            parts = line.split(":", 1)
            if parts:
                conflicts.append(parts[0])
    if not conflicts and result.returncode != 0:
        # git diff --check 非零退出码也意味着存在问题
        for line in result.stderr.splitlines():
            conflicts.append(line.strip())
    return conflicts


def check_large_files(staged: list[dict]) -> list[dict]:
    """检查暂存区大文件 (>1MB)。"""
    large = []
    for entry in staged:
        path = entry["path"]
        full_path = ROOT / path
        if full_path.is_file():
            try:
                size = full_path.stat().st_size
                if size > LARGE_FILE_THRESHOLD:
                    large.append({
                        "path": path,
                        "size_mb": round(size / 1_000_000, 2),
                    })
            except OSError:
                pass
    return large


def generate_warnings(
    staged: list[dict],
    unstaged: list[dict],
    untracked: list[str],
    conflicts: list[str],
    large_files: list[dict],
) -> list[str]:
    """生成警告信息。"""
    warnings = []

    if not staged:
        warnings.append("暂存区为空，没有任何文件待提交")

    if unstaged:
        names = [f["path"] for f in unstaged[:5]]
        suffix = " ..." if len(unstaged) > 5 else ""
        warnings.append(
            f"存在 {len(unstaged)} 个未暂存的变更: {', '.join(names)}{suffix}"
        )

    if untracked:
        names = untracked[:5]
        suffix = " ..." if len(untracked) > 5 else ""
        warnings.append(
            f"存在 {len(untracked)} 个未跟踪文件: {', '.join(names)}{suffix}"
        )

    if large_files:
        for lf in large_files:
            warnings.append(f"大文件: {lf['path']} ({lf['size_mb']} MB)")

    return warnings


def main() -> None:
    text_mode = "--text" in sys.argv

    staged = get_staged_changes()
    unstaged = get_unstaged_changes()
    untracked = get_untracked_files()
    conflicts = check_conflicts()
    large_files = check_large_files(staged)
    warnings = generate_warnings(staged, unstaged, untracked, conflicts, large_files)

    all_clear = (
        len(conflicts) == 0
        and len(large_files) == 0
        and len(staged) > 0
    )

    result = {
        "staged": staged,
        "unstaged": unstaged,
        "untracked": untracked,
        "conflicts": conflicts,
        "large_files": large_files,
        "warnings": warnings,
        "all_clear": all_clear,
    }

    if text_mode:
        print(f"暂存区变更: {len(staged)} 个文件")
        for f in staged:
            print(f"  {f['status']}\t{f['path']}")
        if unstaged:
            print(f"\n未暂存变更: {len(unstaged)} 个文件")
            for f in unstaged[:10]:
                print(f"  {f['status']}\t{f['path']}")
            if len(unstaged) > 10:
                print(f"  ... 还有 {len(unstaged) - 10} 个")
        if untracked:
            print(f"\n未跟踪文件: {len(untracked)} 个")
            for f in untracked[:10]:
                print(f"  ?\t{f}")
        if conflicts:
            print(f"\n冲突文件 ({len(conflicts)} 个):")
            for f in conflicts:
                print(f"  !! {f}")
        if large_files:
            print(f"\n大文件 (>1MB):")
            for lf in large_files:
                print(f"  !! {lf['path']} ({lf['size_mb']} MB)")
        if warnings:
            print(f"\n提示:")
            for w in warnings:
                print(f"  - {w}")
        print(f"\n预检{'通过' if all_clear else '未通过'}")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
