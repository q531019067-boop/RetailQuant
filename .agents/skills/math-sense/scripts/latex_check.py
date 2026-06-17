#!/usr/bin/env python3
"""
latex_check.py — Markdown 数学公式格式检查与修复

源自 md-math-check skill，检测并修复 .md 文件中 LaTeX 公式的常见渲染问题。

用法:
    python latex_check.py --op "check" --file document.md
    python latex_check.py --op "fix" --file document.md --output fixed.md
    echo '$E=mc^2$' | python latex_check.py --op "check"

支持的操作:
    check, fix
"""
import sys, json, re, argparse, os

# ====================== 检测规则 ======================

RULES = [
    {
        "id": "R1_thousands_separator",
        "name": "千位分隔符 {,}",
        "severity": "error",
        "auto_fix": True,
        "desc": "LaTeX 中的 {,} 会被误解析为分组，应直接用无分隔数字。"
               "例如 1{,}000{,}000 → 1000000",
        "pattern": re.compile(r'(\d+)\{,\}(\d+)'),
        "fix": lambda m: m.group(1) + m.group(2),
    },
    {
        "id": "R2_table_pipe",
        "name": "表格内 \\mid 或 \\|",
        "severity": "error",
        "auto_fix": True,
        "desc": "Markdown 表格内 | 会与列分隔符冲突。"
               "将 \\mid 替换为 \\vert，或移出表格使用 $$ 块。",
        "detect_table_pipe": True,  # 特殊处理
    },
    {
        "id": "R3_sigma_vs_sum",
        "name": "\\Sigma 误用为求和",
        "severity": "warning",
        "auto_fix": True,
        "desc": "\\Sigma 是大写希腊字母 Σ，求和运算符应为 \\sum。"
               "\\sum 在行内和行间自动调整大小，\\Sigma 不会。",
        "pattern": re.compile(r'\\Sigma\s*_'),
        "fix": lambda m: m.group(0).replace('\\Sigma', '\\sum'),
    },
    {
        "id": "R4_inline_frac_chinese",
        "name": "行内公式含 \\frac + 中文 \\text",
        "severity": "warning",
        "auto_fix": False,
        "desc": "行内 $...$ 中同时使用 \\frac 和 \\text{中文} 会导致高度过大、渲染溢出。"
               "建议改为 $$...$$ 块级公式，或将中文移出公式用纯文本表达。",
    },
    {
        "id": "R5_display_math_newline",
        "name": "$$ 未独占一行",
        "severity": "error",
        "auto_fix": True,
        "desc": "块级公式 $$...$$ 前后应有空行，且 $$ 应独占一行。"
               "正确的格式为：空行 + $$ + 公式内容 + $$ + 空行。",
    },
    {
        "id": "R6_dollar_spacing",
        "name": "$ 前后空格不当",
        "severity": "warning",
        "auto_fix": True,
        "desc": "行内公式 $ 前不应有空格，$ 后不应紧跟空格（除非是标点）。"
               "正确格式为：文字$公式$文字。",
    },
    {
        "id": "R7_unpaired_dollar",
        "name": "未配对的 $",
        "severity": "error",
        "auto_fix": False,
        "desc": "奇数个 $ 表示有未闭合的公式。"
               "检查是否漏写了闭合的 $，或者是否将 $$ 误写为 $。",
    },
    {
        "id": "R9_env_pairing",
        "name": "LaTeX 环境未配对",
        "severity": "error",
        "auto_fix": False,
        "desc": "\\begin{aligned/cases/...} 必须有对应的 \\end{...}，且两者必须在同一 $$ 块内。"
               "最常见的错误是 $$ 插入了 \\begin 和 \\end 之间，打断了环境。",
    },
    {
        "id": "R10_non_latex_math",
        "name": "非 LaTeX 数学符号",
        "severity": "warning",
        "auto_fix": False,
        "desc": "检测到应该用 LaTeX 但没用的情况。"
               "C(n,k) 应改为 \\binom{n}{k}，10^6 在正文中应改为 $10^6$，"
               "x_i 在正文中应改为 $x_i$。",
    },
    {
        "id": "R8_mathrm_chinese",
        "name": "\\mathrm/\\textrm 含中文",
        "severity": "warning",
        "auto_fix": True,
        "desc": "\\mathrm{} 和 \\textrm{} 不支持中文字符（字体缺失），"
               "应替换为 \\text{}。",
        "pattern": re.compile(r'\\(?:mathrm|textrm)\{([^}]*[\u4e00-\u9fff]+[^}]*)\}'),
        "fix": lambda m: '\\text{' + m.group(1) + '}',
    },
]


def detect_table_pipe_issues(text):
    """检测表格内的 | 冲突"""
    issues = []
    lines = text.split('\n')
    in_table = False
    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()
        # 检测表格行
        if stripped.startswith('|') and stripped.endswith('|'):
            in_table = True
            if re.search(r'(?<!\\)\|', stripped[1:-1]):  # 表格内已有 |
                # 检查是否有 \mid 或 \|
                if '\\mid' in stripped or '\\|' in stripped:
                    issues.append({
                        "rule": "R2_table_pipe",
                        "line": lineno,
                        "content": stripped[:80],
                        "msg": "表格内检测到 \\mid 或 \\|，可能与列分隔符冲突",
                        "fix_suggestion": "将 \\mid 替换为 \\vert，或将公式移出表格",
                    })
        elif in_table and not stripped.startswith('|'):
            in_table = False
    return issues


def check_text(text, filename="<stdin>"):
    """运行所有检测规则"""
    all_issues = []
    lines = text.split('\n')

    # R2 表格管道（特殊处理）
    all_issues.extend(detect_table_pipe_issues(text))

    # R4 行内 frac + 中文
    for lineno, line in enumerate(lines, 1):
        # 找所有 $...$ 行内公式
        inline_maths = re.findall(r'(?<!\$)\$([^$]+?)\$(?!\$)', line)
        for m in inline_maths:
            if '\\frac' in m and re.search(r'\\text\{[^}]*[\u4e00-\u9fff]', m):
                all_issues.append({
                    "rule": "R4_inline_frac_chinese",
                    "line": lineno,
                    "content": m[:80],
                    "msg": "行内公式同时含 \\frac 和中文 \\text，建议改为块级公式或纯文本",
                })

    # R5 $$ 未独占一行
    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()
        # $$ 前后有文字
        if '$$' in line and not re.match(r'^\s*\$\$\s*$', line):
            if re.search(r'\S.*\$\$', line) or re.search(r'\$\$.*\S', line):
                all_issues.append({
                    "rule": "R5_display_math_newline",
                    "line": lineno,
                    "content": stripped[:80],
                    "msg": "$$ 应与内容分开，独占一行，前后加空行",
                })

    # R7 未配对 $
    in_display = False
    dollar_count = 0
    for lineno, line in enumerate(lines, 1):
        # 跳过代码块
        if line.strip().startswith('```'):
            continue
        singles = re.findall(r'(?<!\$)\$(?!\$)', line)
        dollar_count += len(singles)
        doubles = re.findall(r'\$\$', line)
        in_display = (in_display + len(doubles)) % 2 != 0
    if dollar_count % 2 != 0:
        all_issues.append({
            "rule": "R7_unpaired_dollar",
            "line": 0,
            "content": "",
            "msg": f"检测到奇数个行内 $ ({dollar_count})，存在未闭合的公式",
        })
    if in_display:
        all_issues.append({
            "rule": "R7_unpaired_dollar",
            "line": 0,
            "content": "",
            "msg": "块级公式 $$ 未闭合",
        })

    # R9 LaTeX 环境配对检查
    env_stack = []
    for lineno, line in enumerate(lines, 1):
        begins = re.findall(r'\\begin\{(\w+)\}', line)
        ends = re.findall(r'\\end\{(\w+)\}', line)
        for env in begins:
            env_stack.append((env, lineno))
        for env in ends:
            if not env_stack:
                all_issues.append({
                    "rule": "R9_env_pairing",
                    "line": lineno,
                    "content": line.strip()[:80],
                    "msg": f"多余的 \\end{{{env}}}，没有对应的 \\begin{{{env}}}",
                })
            elif env_stack[-1][0] != env:
                all_issues.append({
                    "rule": "R9_env_pairing",
                    "line": lineno,
                    "content": line.strip()[:80],
                    "msg": f"\\end{{{env}}} 与 \\begin{{{env_stack[-1][0]}}} 不匹配（第{env_stack[-1][1]}行），可能被 $$ 打断",
                })
                env_stack.pop()
            else:
                env_stack.pop()
    for env, lineno in env_stack:
        all_issues.append({
            "rule": "R9_env_pairing",
            "line": lineno,
            "content": f"\\begin{{{env}}}",
            "msg": f"\\begin{{{env}}}（第{lineno}行）没有对应的 \\end{{{env}}}，可能被 $$ 打断",
        })

    # R10 非LaTeX数学符号检测
    # Track whether we're inside a $$ display math block
    in_display_block = False
    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()
        # Toggle display math state
        if stripped.startswith('$$') and not stripped.startswith('$$\\begin'):
            in_display_block = not in_display_block
            continue
        # Skip lines inside $$ blocks and code blocks
        if in_display_block or stripped.startswith('```'):
            continue
        # Skip lines that are already inside inline $...$
        # Only flag patterns that appear in plain text paragraphs
        non_latex_patterns = [
            (r'(?<!\$)\bC\(\d+,\s*\d+\)(?!.*\$)', 'C(n,k)', '\\binom{n}{k}'),
            (r'(?<!\$)\b\d+\^\{?\d+\}?\b(?!.*\$)', '10^6/10^{12}', '$10^6$/$10^{12}$'),
            (r'(?<!\$)\b[a-z]_[a-z0-9]\b(?!.*\$)', 'x_i', '$x_i$'),
        ]
        for pat, example, suggestion in non_latex_patterns:
            matches = re.findall(pat, line)
            for m in matches[:2]:
                # Double-check: is this match inside an inline $...$?
                pos = line.find(m)
                before = line[:pos] if pos >= 0 else ''
                if before.count('$') % 2 == 1:
                    continue  # Inside inline math, skip
                all_issues.append({
                    "rule": "R10_non_latex_math",
                    "line": lineno,
                    "content": m[:60],
                    "msg": f"'{m[:40]}' 应使用 LaTeX：{example} → {suggestion}",
                })

    # 通用规则 (R1, R3, R6, R8)
    for rule in RULES:
        if 'pattern' not in rule:
            continue
        pat = rule['pattern']
        for lineno, line in enumerate(lines, 1):
            if line.strip().startswith('```'):
                continue
            for m in pat.finditer(line):
                all_issues.append({
                    "rule": rule['id'],
                    "line": lineno,
                    "content": m.group(0)[:80],
                    "msg": rule['desc'],
                })

    # 按行号排序
    all_issues.sort(key=lambda x: x['line'])
    return all_issues


def fix_text(text):
    """自动修复可修复的问题"""
    fixed = text
    lines = fixed.split('\n')
    fixes_applied = 0

    # R1: 千位分隔符
    pattern_r1 = re.compile(r'(\d+)\{,\}(\d+)')
    fixed = pattern_r1.sub(lambda m: m.group(1) + m.group(2), fixed)
    fixes_applied += len(pattern_r1.findall(text))

    # R3: \Sigma → \sum
    pattern_r3 = re.compile(r'\\Sigma(\s*_)')
    fixed = pattern_r3.sub(r'\\sum\1', fixed)
    fixes_applied += len(pattern_r3.findall(text))

    # R8: \mathrm/\textrm 含中文 → \text
    pattern_r8 = re.compile(r'\\(?:mathrm|textrm)\{([^}]*[\u4e00-\u9fff]+[^}]*)\}')
    fixed = pattern_r8.sub(r'\\text{\1}', fixed)
    fixes_applied += len(pattern_r8.findall(text))

    # R5: $$ 独占一行
    # Pre-skip: never modify lines with LaTeX environments
    def _has_env(line):
        return '\\begin{' in line or '\\end{' in line
    new_lines = []
    for i, line in enumerate(fixed.split('\n')):
        stripped = line.strip()
        # Skip LaTeX environments — they live inside $$ blocks
        if '\\begin{' in stripped or '\\end{' in stripped:
            new_lines.append(line)
            continue
        if re.match(r'^\s*\S.*\$\$', line):
            # 文字后紧跟 $$
            content = re.sub(r'\$\$', '', line)
            before = lines[i - 1].strip() if i > 0 else ''
            if before and not before.startswith('$$') and before != '':
                new_lines[-1] = new_lines[-1] + '\n' if new_lines else ''
            new_lines.append('\n$$')
            new_lines.append(content.strip())
            new_lines.append('$$')
            fixes_applied += 1
        elif re.match(r'\$\$.*\S', line):
            # Also skip if line contains LaTeX environments
            if '\\begin{' in stripped or '\\end{' in stripped:
                new_lines.append(line)
                continue
            content = re.sub(r'\$\$', '', line)
            new_lines.append('$$')
            new_lines.append(content.strip())
            new_lines.append('$$')
            fixes_applied += 1
        else:
            new_lines.append(line)
    fixed = '\n'.join(new_lines)

    return fixed, fixes_applied


def main():
    parser = argparse.ArgumentParser(
        description="Markdown 数学公式格式检查与修复",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python latex_check.py --op "check" --file doc.md
  python latex_check.py --op "fix" --file doc.md --output fixed.md
  echo '$E=mc^2$' | python latex_check.py --op "check"
""")
    parser.add_argument('--op', '-o', choices=['check', 'fix'], default='check', help='操作')
    parser.add_argument('--file', '-f', help='Markdown 文件路径')
    parser.add_argument('--output', help='修复后输出文件路径')
    parser.add_argument('--compact', '-c', action='store_true', help='紧凑输出')
    parser.add_argument('json_input', nargs='?', help='JSON 输入')

    args = parser.parse_args()

    # 读取输入
    text = ''
    filename = '<stdin>'
    if args.file:
        filename = args.file
        with open(args.file, 'r', encoding='utf-8') as f:
            text = f.read()
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    elif args.json_input:
        data = json.loads(args.json_input)
        text = data.get('text', '')
        filename = data.get('file', '<stdin>')

    if not text:
        print(json.dumps({"ok": False, "error": "无输入文本"}, ensure_ascii=False))
        sys.exit(1)

    if args.op == 'check':
        issues = check_text(text, filename)
        errors = sum(1 for i in issues if 'error' in (RULES_DICT.get(i['rule'], {}).get('severity', '') or ''))
        warnings = len(issues) - errors
        output = {
            "ok": True,
            "file": filename,
            "total_issues": len(issues),
            "errors": errors,
            "warnings": warnings,
            "issues": issues,
        }
        print(json.dumps(output, ensure_ascii=False, indent=None if args.compact else 2))
        if errors > 0:
            sys.exit(1)

    elif args.op == 'fix':
        issues_before = check_text(text, filename)
        fixed_text, fixes = fix_text(text)
        issues_after = check_text(fixed_text, filename)

        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(fixed_text)
            output = {
                "ok": True, "file": filename, "output": args.output,
                "issues_before": len(issues_before),
                "issues_after": len(issues_after),
                "fixes_applied": fixes,
            }
        else:
            output = {
                "ok": True, "file": filename,
                "fixed_text": fixed_text,
                "issues_before": len(issues_before),
                "issues_after": len(issues_after),
                "fixes_applied": fixes,
            }
        print(json.dumps(output, ensure_ascii=False, indent=None if args.compact else 2))


# 用于 severity 判断
RULES_DICT = {r['id']: r for r in RULES}

if __name__ == '__main__':
    main()