#!/usr/bin/env python3
"""
Math formula auto-fixer for Markdown files.

Automatically fixes common LaTeX math formula issues in .md files.
Supports stdout output or in-place file modification.
"""

import argparse
import io
import os
import re
import sys


def fix_content(content: str) -> str:
    """对 Markdown 内容执行所有自动修复，返回修复后的文本。"""
    lines = content.split("\n")
    result = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # ----------------------------------------------------------
        # 修复 1: 在 $$ 块级公式前后补充空行
        # ----------------------------------------------------------
        stripped = line.strip()

        # 检测 $$ 开始行：前面没有空行
        if stripped.startswith("$$") and not stripped.startswith("$$$$"):
            # 如果前一行存在且非空，插入空行
            if result and result[-1].strip() != "":
                result.append("")
            result.append(line)

            # 找到配对的 $$ 结束行，在其后补充空行
            if not stripped.endswith("$$"):
                # $$ 开始在单独行，找结束行
                j = i + 1
                while j < len(lines):
                    if "$$" in lines[j]:
                        # 结束行后面如果没有空行则补充
                        if j + 1 < len(lines) and lines[j + 1].strip() != "":
                            result.append(lines[j])
                            result.append("")
                            i = j + 1
                            break
                        else:
                            result.append(lines[j])
                            i = j + 1
                            break
                    else:
                        result.append(lines[j])
                        j += 1
                else:
                    i += 1
                continue
            else:
                # $$ 在同一行（单行块公式），后面补空行
                if i + 1 < len(lines) and lines[i + 1].strip() != "":
                    result.append("")
                i += 1
                continue

        # ----------------------------------------------------------
        # 修复 2: 移除 $ 后面/前面的多余空格
        # ----------------------------------------------------------
        fixed_line = fix_math_spacing(line)

        # ----------------------------------------------------------
        # 修复 3-6: 公式内部的修复（需要识别公式范围）
        # ----------------------------------------------------------
        fixed_line = fix_inline_math(fixed_line)
        fixed_line = fix_block_math_in_line(fixed_line)

        # ----------------------------------------------------------
        # 修复 7: 表格中的 \mid → \vert
        # ----------------------------------------------------------
        if stripped.startswith("|"):
            fixed_line = fix_table_math(fixed_line)

        result.append(fixed_line)
        i += 1

    return "\n".join(result)


def fix_math_spacing(line: str) -> str:
    """移除 $ 和公式内容之间的多余空格。"""
    # $ 后面的空格: "$ x$" → "$x$"
    line = re.sub(r"\$\s+([^$\s])", r"$\1", line)
    # $ 前面的空格: "$x $" → "$x$"
    line = re.sub(r"([^$\s])\s+\$", r"\1$", line)
    return line


def fix_inline_math(line: str) -> str:
    """修复行内公式中的常见问题。"""
    def _fix_math_content(m):
        prefix = m.group(1)  # 开头的 $
        content = m.group(2)  # 公式内容
        suffix = m.group(3)  # 结尾的 $

        # 修复 {,} 千分位模式 → 移除逗号
        content = re.sub(r"\{,\}", "", content)

        # 修复 \Sigma → \sum
        content = content.replace("\\Sigma", "\\sum")

        # 修复 \mathrm{中文} → \text{中文}
        content = re.sub(
            r"\\mathrm\{([^}]*[\u4e00-\u9fff][^}]*)\}",
            r"\\text{\1}",
            content,
        )

        # 修复 \textrm{中文} → \text{中文}
        content = re.sub(
            r"\\textrm\{([^}]*[\u4e00-\u9fff][^}]*)\}",
            r"\\text{\1}",
            content,
        )

        return prefix + content + suffix

    # 匹配 $...$ 行内公式（非 $$）
    line = re.sub(
        r"(\$)([^\$]+?)(\$)",
        _fix_math_content,
        line,
    )
    return line


def fix_block_math_in_line(line: str) -> str:
    """修复同一行内 $$...$$ 块公式中的内容。"""
    def _fix_block_content(m):
        content = m.group(1)

        # 修复 {,}
        content = re.sub(r"\{,\}", "", content)

        # 修复 \Sigma → \sum
        content = content.replace("\\Sigma", "\\sum")

        # 修复 \mathrm{中文} → \text{中文}
        content = re.sub(
            r"\\mathrm\{([^}]*[\u4e00-\u9fff][^}]*)\}",
            r"\\text{\1}",
            content,
        )

        content = re.sub(
            r"\\textrm\{([^}]*[\u4e00-\u9fff][^}]*)\}",
            r"\\text{\1}",
            content,
        )

        return "$$" + content + "$$"

    line = re.sub(r"\$\$(.+?)\$\$", _fix_block_content, line)
    return line


def fix_table_math(line: str) -> str:
    """修复表格行中的公式问题。"""
    # \mid → \vert（在表格中 | 有特殊含义）
    if "\\mid" in line:
        line = line.replace("\\mid", "\\vert")
    return line


def fix_multiline_block_math(content: str) -> str:
    """修复跨行的 $$...$$ 块级公式内容。"""
    def _fix_block(m):
        block = m.group(0)
        inner = m.group(1)

        # 修复 {,}
        inner = re.sub(r"\{,\}", "", inner)

        # 修复 \Sigma → \sum
        inner = inner.replace("\\Sigma", "\\sum")

        # 修复 \mathrm{中文} → \text{中文}
        inner = re.sub(
            r"\\mathrm\{([^}]*[\u4e00-\u9fff][^}]*)\}",
            r"\\text{\1}",
            inner,
        )

        inner = re.sub(
            r"\\textrm\{([^}]*[\u4e00-\u9fff][^}]*)\}",
            r"\\text{\1}",
            inner,
        )

        return "$$" + inner + "$$"

    content = re.sub(r"\$\$(.+?)\$\$", _fix_block, content, flags=re.DOTALL)
    return content


def main():
    # 在 Windows 上将 stdout/stderr 设置为 UTF-8，避免中文输出报错
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="自动修复 Markdown 文件中的 LaTeX 数学公式问题",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s document.md                 # 输出到 stdout
  %(prog)s document.md --in-place      # 直接修改原文件
  %(prog)s document.md -o fixed.md     # 输出到指定文件
  %(prog)s *.md --in-place             # 批量修复
        """,
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="要修复的 .md 文件",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="直接修改原文件（谨慎使用）",
    )
    parser.add_argument(
        "-o", "--output",
        help="输出文件路径（仅对单个文件有效）",
    )

    args = parser.parse_args()

    if args.output and len(args.files) > 1:
        print("[ERROR] -o/--output 只能用于单个文件", file=sys.stderr)
        sys.exit(1)

    if args.output and args.in_place:
        print("[ERROR] --in-place 和 -o 不能同时使用", file=sys.stderr)
        sys.exit(1)

    for filepath in args.files:
        if not os.path.isfile(filepath):
            print(f"[WARN] 文件不存在，跳过: {filepath}", file=sys.stderr)
            continue

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
        except (OSError, UnicodeDecodeError) as e:
            print(f"[ERROR] 无法读取文件 {filepath}: {e}", file=sys.stderr)
            continue

        # 执行修复（行级 + 多行块级公式）
        fixed = fix_content(content)
        fixed = fix_multiline_block_math(fixed)

        if args.in_place:
            if fixed != content:
                try:
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(fixed)
                    print(f"[FIXED] {filepath}")
                except OSError as e:
                    print(f"[ERROR] 无法写入文件 {filepath}: {e}", file=sys.stderr)
            else:
                print(f"[OK] {filepath} (无需修复)")
        elif args.output:
            try:
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(fixed)
                print(f"[FIXED] {filepath} -> {args.output}")
            except OSError as e:
                print(f"[ERROR] 无法写入文件 {args.output}: {e}", file=sys.stderr)
        else:
            sys.stdout.write(fixed)


if __name__ == "__main__":
    main()
