#!/usr/bin/env python3
"""
同步 docs/*.md 标题下的 git 元数据（H1 下方 blockquote + --- 分隔）。

默认格式::

    > 创建人：      Lyuan741
    > 创建时间：    2026-06-17 23:08
    > 最后修改人：  Lyuan741
    > 最后修改时间：2026-06-24 03:19

    ---

用法::

    python scripts/sync_docs_meta.py              # 更新 docs/ 下全部 .md
    python scripts/sync_docs_meta.py --check      # 仅检查，不写文件
    python scripts/sync_docs_meta.py --commit-prep  # 提交前：仅变更的 docs/*.md，最后修改人=当前 git 用户
    python scripts/sync_docs_meta.py docs/大纲.md  # 指定文件
    python scripts/sync_docs_meta.py --print      # 打印各文件 git 信息
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# 4 行 blockquote 元数据（key 列对齐，允许 > 后多空格）
BLOCKQUOTE_META_RE = re.compile(
    r"^> *创建人[：:].*\n"
    r"^> *创建时间[：:].*\n"
    r"^> *最后修改人[：:].*\n"
    r"^> *最后修改时间[：:].*\n",
    re.MULTILINE,
)
HTML_META_RE = re.compile(
    r"<!-- 创建人:.*?-->\n<!-- 创建时间:.*?-->\n<!-- 最后修改人:.*?-->\n<!-- 最后修改时间:.*?-->\n",
    re.MULTILINE,
)
PLAIN_META_RE = re.compile(
    r"^创建人[：:].*\n创建时间[：:].*\n最后修改人[：:].*\n最后修改时间[：:].*\n",
    re.MULTILINE,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"

_META_LABELS = ("创建人：", "创建时间：", "最后修改人：", "最后修改时间：")
_LABEL_WIDTH = max(len(label) for label in _META_LABELS)


def git_author_date(path: str, *, first: bool) -> tuple[str, str]:
    """返回 (author, date_str)，date 格式 YYYY-MM-DD HH:MM。"""
    fmt = ["git", "log", "-1", "--format=%an|%ad", "--date=format:%Y-%m-%d %H:%M", "--", path]
    if first:
        fmt = [
            "git",
            "log",
            "--diff-filter=A",
            "--follow",
            "-1",
            "--format=%an|%ad",
            "--date=format:%Y-%m-%d %H:%M",
            "--",
            path,
        ]
    out = subprocess.run(fmt, capture_output=True, text=True, encoding="utf-8", cwd=PROJECT_ROOT)
    line = out.stdout.strip()
    if not line or "|" not in line:
        return ("unknown", "unknown")
    author, date = line.split("|", 1)
    return author, date


def build_meta_block(creator: str, created: str, editor: str, edited: str) -> str:
    rows = zip(_META_LABELS, (creator, created, editor, edited), strict=True)
    lines = [f"> {label}{' ' * (_LABEL_WIDTH - len(label))}{value}" for label, value in rows]
    return "\n".join(lines) + "\n\n---\n\n"


def strip_existing_meta(text: str) -> str:
    text = BLOCKQUOTE_META_RE.sub("", text)
    text = HTML_META_RE.sub("", text)
    text = PLAIN_META_RE.sub("", text)
    return text


def insert_meta_after_h1(text: str, block: str) -> str:
    """在首个 H1 标题后插入元数据块（标题与 blockquote 之间保留一个空行）。"""
    text = strip_existing_meta(text)
    lines = text.splitlines(keepends=True)
    if not lines or not lines[0].startswith("# "):
        raise ValueError("文件缺少 H1 标题")

    title = lines[0] if lines[0].endswith("\n") else lines[0] + "\n"
    rest = lines[1:]
    while rest and rest[0].strip() == "":
        rest = rest[1:]
    if rest and rest[0].strip() == "---":
        rest = rest[1:]
        while rest and rest[0].strip() == "":
            rest = rest[1:]

    return title + "\n" + block + "".join(rest)


def git_current_user() -> str:
    out = subprocess.run(
        ["git", "config", "user.name"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=PROJECT_ROOT,
    )
    name = out.stdout.strip()
    return name or "unknown"


def changed_docs_in_git() -> list[Path]:
    """工作区/暂存区/未跟踪的 docs/*.md。"""
    paths: set[str] = set()
    for args in (
        ["git", "diff", "--name-only"],
        ["git", "diff", "--cached", "--name-only"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ):
        out = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", cwd=PROJECT_ROOT)
        for line in out.stdout.splitlines():
            line = line.strip().replace("\\", "/")
            if line.startswith("docs/") and line.endswith(".md"):
                paths.add(line)
    return sorted(PROJECT_ROOT / p for p in paths)


def sync_file(
    path: Path,
    *,
    check: bool = False,
    editor: str | None = None,
    edited: str | None = None,
) -> tuple[bool, str]:
    """返回 (needs_update, message)。"""
    rel = path.relative_to(PROJECT_ROOT).as_posix()
    creator, created = git_author_date(rel, first=True)
    if editor is None or edited is None:
        editor, edited = git_author_date(rel, first=False)
    new_block = build_meta_block(creator, created, editor, edited)

    old_text = path.read_text(encoding="utf-8")
    new_text = insert_meta_after_h1(old_text, new_block)

    if new_text == old_text:
        return False, f"OK  {rel}  (已是最新)"

    if check:
        return True, f"STALE  {rel}  创建={creator} {created}  修改={editor} {edited}"

    path.write_text(new_text, encoding="utf-8")
    return True, f"UPD  {rel}  创建={creator} {created}  修改={editor} {edited}"


def main() -> int:
    parser = argparse.ArgumentParser(description="同步 docs/*.md 的 git 元数据（blockquote + ---）")
    parser.add_argument("paths", nargs="*", help="指定文件或目录，默认 docs/")
    parser.add_argument("--check", action="store_true", help="仅检查，不写文件")
    parser.add_argument(
        "--commit-prep",
        action="store_true",
        help="提交前模式：仅处理 git 变更的 docs/*.md，最后修改人=当前 git 用户，最后修改时间=当前时间",
    )
    parser.add_argument("--print", dest="print_only", action="store_true", help="打印 git 信息")
    args = parser.parse_args()

    targets: list[Path] = []
    if args.commit_prep:
        targets = changed_docs_in_git()
        if not targets:
            print("无变更的 docs/*.md，跳过")
            return 0
    elif args.paths:
        for p in args.paths:
            path = Path(p)
            if not path.is_absolute():
                path = PROJECT_ROOT / path
            if path.is_dir():
                targets.extend(sorted(path.rglob("*.md")))
            elif path.is_file():
                targets.append(path)
            else:
                print(f"跳过不存在: {p}", file=sys.stderr)
    else:
        targets = sorted(DOCS_DIR.rglob("*.md"))

    if not targets:
        print("没有找到 .md 文件", file=sys.stderr)
        return 1

    stale = 0
    commit_user = git_current_user() if args.commit_prep else None
    commit_time = datetime.now().strftime("%Y-%m-%d %H:%M") if args.commit_prep else None
    for path in targets:
        rel = path.relative_to(PROJECT_ROOT).as_posix()
        if args.print_only:
            c, cd = git_author_date(rel, first=True)
            e, ed = git_author_date(rel, first=False)
            print(f"{rel}\n  创建: {c}  {cd}\n  修改: {e}  {ed}")
            continue
        try:
            changed, msg = sync_file(
                path,
                check=args.check,
                editor=commit_user,
                edited=commit_time,
            )
            print(msg)
            if changed:
                stale += 1
        except ValueError as exc:
            print(f"SKIP  {rel}  {exc}", file=sys.stderr)
            stale += 1

    if args.print_only:
        return 0
    if args.check and stale:
        print(f"\n{stale} 个文件需要更新，运行不带 --check 即可覆写", file=sys.stderr)
        return 1
    print(f"\n完成：{len(targets)} 个文件，更新 {stale} 个")
    return 0


if __name__ == "__main__":
    sys.exit(main())
