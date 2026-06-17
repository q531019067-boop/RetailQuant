#!/usr/bin/env python3
"""
Math formula checker for Markdown files.

Scans .md files for common LaTeX math formula issues and reports them
with line numbers and severity levels.
"""

import argparse
import io
import os
import re
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class Severity(Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"


@dataclass
class Issue:
    line_no: int
    severity: Severity
    rule: str
    description: str
    snippet: str


# ---------------------------------------------------------------------------
# 正则表达式定义
# ---------------------------------------------------------------------------

# 匹配 $$...$$ 块级公式（跨行）
BLOCK_MATH_RE = re.compile(r"\$\$(.+?)\$\$", re.DOTALL)

# 匹配 $...$ 行内公式（非 $$）
INLINE_MATH_RE = re.compile(r"(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)")

# {,} 千分位模式 — 在公式中出现 {,} 表示错误的千分位写法
THOUSANDS_SEP_RE = re.compile(r"\{,\}")

# \Sigma（应使用 \sum）
SIGMA_RE = re.compile(r"\\Sigma")

# \frac 同时包含 \text{} 含中文 CJK 字符
FRAC_TEXT_CJK_RE = re.compile(
    r"\\frac\{[^}]*\}\{[^}]*\\text\{[^}]*[\u4e00-\u9fff][^}]*\}[^}]*\}"
)

# $$ 未独占行 — 前面或后面紧接非空白文本
BLOCK_NOT_ALONE_BEFORE_RE = re.compile(r"[^\s]\$\$")
BLOCK_NOT_ALONE_AFTER_RE = re.compile(r"\$\$[^\s]")

# $ 后面或前面紧跟空格
SPACE_AFTER_DOLLAR_RE = re.compile(r"\$\s+[^$\s]")
SPACE_BEFORE_DOLLAR_RE = re.compile(r"[^\s]\s+\$")

# \mathrm{} 或 \textrm{} 包含 CJK 字符
MATHRM_CJK_RE = re.compile(
    r"\\(?:mathrm|textrm)\{[^}]*[\u4e00-\u9fff][^}]*\}"
)

# 表格行检测
TABLE_ROW_RE = re.compile(r"^\s*\|", re.MULTILINE)

# \mid 或裸 | 在表格公式中
MID_IN_TABLE_RE = re.compile(r"\\mid")
BARE_PIPE_IN_MATH_RE = re.compile(r"(?<!\\)\|")


def find_inline_math_spans(line: str):
    """找出一行中所有 $...$ 行内公式的 (start, end) 位置。"""
    spans = []
    i = 0
    while i < len(line):
        if line[i] == '$':
            # 跳过 $$
            if i + 1 < len(line) and line[i + 1] == '$':
                i += 2
                continue
            # 找配对的 $
            j = i + 1
            while j < len(line):
                if line[j] == '$' and (j == 0 or line[j - 1] != '\\'):
                    spans.append((i, j + 1))
                    i = j + 1
                    break
                j += 1
            else:
                i += 1
        else:
            i += 1
    return spans


def get_math_content(line: str) -> list[str]:
    """提取一行中所有行内公式内容。"""
    return [line[s:e] for s, e in find_inline_math_spans(line)]


def check_file(filepath: str) -> list[Issue]:
    """检查单个文件，返回所有问题列表。"""
    issues = []

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            lines = content.split("\n")
    except (OSError, UnicodeDecodeError) as e:
        print(f"[WARN] 无法读取文件 {filepath}: {e}", file=sys.stderr)
        return issues

    # ------------------------------------------------------------------
    # 全文级检查
    # ------------------------------------------------------------------

    # 检查 $$ 块级公式是否独占行
    for line_no, line in enumerate(lines, 1):
        # 检查 $$ 前面是否有非空白字符
        for m in re.finditer(r"\$\$", line):
            pos = m.start()
            # 如果这是行内 $$formula$$ 的第二个 $$，跳过
            # 简化处理：检查前后是否有非空白
            if pos > 0 and line[pos - 1] not in (' ', '\t', ''):
                issues.append(Issue(
                    line_no=line_no,
                    severity=Severity.ERROR,
                    rule="block-math-not-alone",
                    description="$$ 前面有文本，块级公式必须独占一行",
                    snippet=line.strip(),
                ))
            end_pos = m.end()
            if end_pos < len(line) and line[end_pos] not in (' ', '\t', ''):
                issues.append(Issue(
                    line_no=line_no,
                    severity=Severity.ERROR,
                    rule="block-math-not-alone",
                    description="$$ 后面有文本，块级公式必须独占一行",
                    snippet=line.strip(),
                ))

    # ------------------------------------------------------------------
    # 逐行检查
    # ------------------------------------------------------------------
    in_table = False

    for line_no, line in enumerate(lines, 1):
        stripped = line.strip()

        # 跟踪是否在表格中
        if stripped.startswith('|'):
            in_table = True
        elif in_table and not stripped.startswith('|') and stripped != '':
            in_table = False

        # 提取行内公式
        math_spans = find_inline_math_spans(line)

        for start, end in math_spans:
            math_text = line[start:end]
            inner = math_text[1:-1]  # 去掉首尾 $

            # 规则 1: {,} 千分位模式
            if THOUSANDS_SEP_RE.search(inner):
                issues.append(Issue(
                    line_no=line_no,
                    severity=Severity.ERROR,
                    rule="thousands-separator",
                    description="公式中使用了 {,} 千分位模式，应移除逗号",
                    snippet=math_text,
                ))

            # 规则 2: \mid 在表格中
            if in_table and MID_IN_TABLE_RE.search(inner):
                issues.append(Issue(
                    line_no=line_no,
                    severity=Severity.ERROR,
                    rule="mid-in-table",
                    description="表格中的公式使用了 \\mid，应替换为 \\vert",
                    snippet=math_text,
                ))

            # 规则 2b: 裸 | 在表格公式中
            if in_table and BARE_PIPE_IN_MATH_RE.search(inner):
                issues.append(Issue(
                    line_no=line_no,
                    severity=Severity.ERROR,
                    rule="pipe-in-table-math",
                    description="表格公式中的 | 会与表格语法冲突，应替换为 \\vert",
                    snippet=math_text,
                ))

            # 规则 3: \Sigma 应使用 \sum
            if SIGMA_RE.search(inner):
                issues.append(Issue(
                    line_no=line_no,
                    severity=Severity.WARNING,
                    rule="sigma-vs-sum",
                    description="使用了 \\Sigma，建议替换为 \\sum（求和符号）",
                    snippet=math_text,
                ))

            # 规则 4: 行内公式含 \frac + \text{} 含中文
            if FRAC_TEXT_CJK_RE.search(inner):
                issues.append(Issue(
                    line_no=line_no,
                    severity=Severity.WARNING,
                    rule="complex-inline-math",
                    description="行内公式同时包含 \\frac 和含中文的 \\text{}，建议转为块级公式或文字",
                    snippet=math_text,
                ))

            # 规则 6: $ 后或前有空格
            inner_stripped = inner
            if inner_stripped != inner_stripped.strip():
                issues.append(Issue(
                    line_no=line_no,
                    severity=Severity.WARNING,
                    rule="math-spacing",
                    description="$ 与公式内容之间有多余空格",
                    snippet=math_text,
                ))

            # 规则 8: \mathrm{} 或 \textrm{} 含中文
            if MATHRM_CJK_RE.search(inner):
                issues.append(Issue(
                    line_no=line_no,
                    severity=Severity.WARNING,
                    rule="mathrm-cjk",
                    description="\\mathrm{} 或 \\textrm{} 包含中文字符，应使用 \\text{}",
                    snippet=math_text,
                ))

        # 规则 7: 不匹配的 $（忽略 $$ 后奇数个 $）
        # 去掉所有 $$ 后检查剩余 $ 的数量
        line_no_dollar = line.replace('$$', '')
        dollar_count = line_no_dollar.count('$')
        if dollar_count % 2 != 0:
            issues.append(Issue(
                line_no=line_no,
                severity=Severity.ERROR,
                rule="unmatched-dollar",
                description=f"该行有奇数个 $（{dollar_count}个），存在未匹配的 $",
                snippet=line.strip(),
            ))

    return issues


def scan_directory(directory: str, recursive: bool = False) -> list[tuple[str, list[Issue]]]:
    """扫描目录中的 .md 文件。"""
    results = []
    path = Path(directory)

    if recursive:
        md_files = sorted(path.rglob("*.md"))
    else:
        md_files = sorted(path.glob("*.md"))

    for md_file in md_files:
        issues = check_file(str(md_file))
        if issues:
            results.append((str(md_file), issues))

    return results


SEVERITY_COLOR = {
    Severity.ERROR: "\033[91m",   # 红色
    Severity.WARNING: "\033[93m", # 黄色
}
RESET_COLOR = "\033[0m"


def print_results(results: list[tuple[str, list[Issue]]], use_color: bool = True):
    """打印检查结果。"""
    total_errors = 0
    total_warnings = 0

    for filepath, issues in results:
        print(f"\n{'='*60}")
        print(f"文件: {filepath}")
        print(f"{'='*60}")

        for issue in sorted(issues, key=lambda x: x.line_no):
            color = SEVERITY_COLOR.get(issue.severity, "") if use_color else ""
            reset = RESET_COLOR if use_color else ""
            print(
                f"  {color}{issue.severity.value}{reset} "
                f"L{issue.line_no} [{issue.rule}]"
            )
            print(f"    {issue.description}")
            print(f"    >> {issue.snippet}")
            print()

            if issue.severity == Severity.ERROR:
                total_errors += 1
            else:
                total_warnings += 1

    # 总结
    print(f"\n{'='*60}")
    print(f"扫描完成: {len(results)} 个文件, "
          f"{total_errors} 个错误, {total_warnings} 个警告")
    print(f"{'='*60}")

    return total_errors, total_warnings


def main():
    # 在 Windows 上将 stdout/stderr 设置为 UTF-8，避免中文输出报错
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="扫描 Markdown 文件中的 LaTeX 数学公式问题",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s document.md                    # 检查单个文件
  %(prog)s docs/                          # 检查目录下的 .md 文件
  %(prog)s docs/ -r                       # 递归检查目录
  %(prog)s document.md --no-color         # 无颜色输出
        """,
    )
    parser.add_argument(
        "path",
        help="要检查的 .md 文件或目录路径",
    )
    parser.add_argument(
        "-r", "--recursive",
        action="store_true",
        help="递归扫描子目录",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="禁用彩色输出",
    )

    args = parser.parse_args()
    target = args.path

    if not os.path.exists(target):
        print(f"[ERROR] 路径不存在: {target}", file=sys.stderr)
        sys.exit(1)

    use_color = not args.no_color and sys.stdout.isatty()

    if os.path.isfile(target):
        issues = check_file(target)
        results = [(target, issues)] if issues else []
    elif os.path.isdir(target):
        results = scan_directory(target, recursive=args.recursive)
    else:
        print(f"[ERROR] 无效路径: {target}", file=sys.stderr)
        sys.exit(1)

    if not results:
        print("未发现问题。")
        sys.exit(0)

    total_errors, total_warnings = print_results(results, use_color=use_color)

    # 如果有 ERROR 级别问题，返回非零退出码
    sys.exit(1 if total_errors > 0 else 0)


if __name__ == "__main__":
    main()
