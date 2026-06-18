"""
Mermaid Syntax Fixer — Pure Python, zero dependencies
Usage: python fix_mermaid.py <directory> [--check-only] [--mmdc]

Modes:
  --check-only : Only report issues, don't fix
  --mmdc       : Also validate with mmdc (requires Node.js + @mermaid-js/mermaid-cli)
  (default)    : Fix all detectable issues

Examples:
  python fix_mermaid.py "Document/表现逻辑"
  python fix_mermaid.py "Document/表现逻辑" --check-only
  python fix_mermaid.py "Document/表现逻辑" --mmdc
"""

import glob, re, os, sys

# Fix Windows terminal encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def count_brackets(line):
    """Net open brackets/braces."""
    return (line.count("[") + line.count("{")) - (line.count("]") + line.count("}"))


# ============================================================
# Detection rules
# ============================================================


def check_rules(fp, text, le):
    """Rule-based check. Returns list of (line_num, problems, line_text)."""
    issues = []

    # R8: Orphan flowchart (no ```mermaid prefix)
    lines_all = text.split(le)
    in_mermaid = False
    for i, line in enumerate(lines_all):
        s = line.strip()
        if s == "```mermaid":
            in_mermaid = True
        elif s == "```" and in_mermaid:
            in_mermaid = False
        elif s.startswith("flowchart ") and not in_mermaid:
            issues.append((i + 1, ["R8: 缺 ```mermaid 前缀"], s[:80]))

    # R9: ``` attached to closing bracket
    for m in re.finditer(r"[\]\}]\`\`\`", text):
        ln = text[: m.start()].count(le) + 1
        issues.append((ln, ["R9: ``` 紧贴节点(缺换行)"], ""))

    # R7: "'...'" nested quotes (must check before block extraction)
    for m in re.finditer(r'"\'[\s\S]*?\'"', text):
        ln = text[: m.start()].count(le) + 1
        label = m.group(0)[:40].replace("\n", "\\n")
        issues.append((ln, [f"R7: 嵌套引号 {label}"], ""))

    # Per-block checks (ALL mermaid diagram types)
    for m in re.finditer(r"```mermaid\r?\n(([a-zA-Z]+[^\r\n]*\r?\n))((?:(?!```)[\s\S])*)```", text):
        header = m.group(2)
        body = m.group(3)
        block_start = text[: m.start()].count(le) + 2
        lines = body.split(le)
        is_flowchart = m.group(2).strip().startswith(("flowchart", "graph"))

        for i, line in enumerate(lines):
            ln = block_start + i
            probs = []

            # R1: <br/>
            if "<br" in line:
                probs.append("R1: <br/>")

            # R2/R3: Unbalanced brackets (flowchart only)
            if is_flowchart and count_brackets(line) != 0:
                probs.append("R2: 括号不配对")

            # R5: Nested [] inside quotes (flowchart only)
            if is_flowchart and re.search(r'\["[^"]*\[', line):
                probs.append("R5: 引号内嵌[]")

            # R4: Unquoted special chars in [...] labels (flowchart only)
            if is_flowchart:
                for seg in re.finditer(r'\[([^\]"]+)\]', line):
                    if re.search(r"[()<>:=\[\]{}/]", seg.group(1)):
                        probs.append(f"R4: 未引号[{seg.group(1)[:25]}]")

                # R4: Unquoted special chars in {...} labels
                for seg in re.finditer(r'\{([^}"]+)\}', line):
                    if re.search(r"[()<>:=\[\]{}/]", seg.group(1)):
                        probs.append(f"R4: 未引号{{{seg.group(1)[:25]}}}")

            # R6: Inner quotes in unquoted labels (flowchart only)
            if is_flowchart and re.search(r'\[[^"\]]*"[^"\]]*\]', line):
                probs.append("R6: 标签内含引号")

            # R11: Inner quotes in already-quoted labels ["...text"..."]
            if re.search(r'\["[^"]*"[^"]*"\]', line):
                probs.append("R11: 引号标签内含裸引号")

            # R12: sequenceDiagram messages with () not quoted
            if not is_flowchart and re.search(r"(?:->>|-->>|->|--):.*\(", line):
                msg = re.split(r"(?:->>|-->>|->|--):", line, 1)[-1].strip()
                if msg and not msg.startswith('"'):
                    probs.append("R12: 消息含()未引号")

            if probs:
                issues.append((ln, probs, line.strip()[:80]))

    return issues


# ============================================================
# Auto-fix
# ============================================================


def fix_file(fp, le):
    """Fix all mermaid issues. Returns True if changed."""
    with open(fp, "rb") as fh:
        raw = fh.read()
    text = raw.decode("utf-8")
    original = text

    # Pre-fix globally (before block extraction)

    # R7: Remove "'...'" (use [\s\S] for multiline!)
    text = re.sub(r"\"\'([\s\S]*?)\'\"", lambda m: '"' + m.group(1) + '"', text)

    # R9: Fix ``` attached to ] or }
    text = re.sub(r"([\]\}])\`\`\`", r"\1\n```", text)

    def fix_flowchart_block(m):
        header = m.group(1) + m.group(2)
        body = m.group(3)
        footer = m.group(4)
        is_flowchart = m.group(2).strip().startswith(("flowchart", "graph"))

        # R1: <br/> → \n (all diagram types)
        body = body.replace("<br/>", "\\n")
        body = body.replace("<br>", "\\n")

        # R11: Fix inner quotes in ALREADY-quoted labels (all diagram types)
        def fix_inner_quotes_quoted(match):
            before = match.group(1)
            after = match.group(2)
            return '["' + before + "'" + after + '"]'

        body = re.sub(r'\["([^"]*)"([^"]*)"\]', fix_inner_quotes_quoted, body)

        # R12: Quote sequenceDiagram messages containing () (parser treats () as actor ref)
        def fix_seq_msg(match):
            prefix = match.group(1)
            msg = match.group(2)
            if "(" in msg and not msg.startswith('"'):
                return prefix + '"' + msg + '"'
            return match.group(0)

        body = re.sub(r"((?:->>|-->>|->|--):)(.*?)(?=\r?\n|$)", fix_seq_msg, body)

        # R13: Merge multi-line Note over in sequenceDiagram
        if not is_flowchart:
            lines = body.split(le)
            fixed = []
            i = 0
            while i < len(lines):
                line = lines[i]
                if re.match(r"\s*Note over ", line) and ":" in line:
                    # Collect continuation lines (non-empty, non-directive)
                    parts = [line.rstrip()]
                    j = i + 1
                    while j < len(lines):
                        next_line = lines[j].strip()
                        if (
                            next_line
                            and not re.match(r"(?:Note |participant |\w+[-]+>)", next_line)
                            and not next_line.startswith("end")
                        ):
                            parts.append(next_line)
                            j += 1
                        else:
                            break
                    if len(parts) > 1:
                        note_prefix = parts[0].split(":")[0] + ":"
                        note_text = parts[0].split(":", 1)[1].strip()
                        for p in parts[1:]:
                            note_text += "\\n" + p
                        fixed.append(note_prefix + ' "' + note_text + '"')
                    else:
                        fixed.append(line)
                    i = j
                    continue
                else:
                    fixed.append(line)
                i += 1
            body = le.join(fixed)

        # R2/R3: Merge multi-line node labels (flowchart only)
        if is_flowchart:
            lines = body.split(le)
            fixed = []
            i = 0
            while i < len(lines):
                line = lines[i]
                net = count_brackets(line)
                if net < 0 and fixed:
                    fixed[-1] = fixed[-1] + "\\n" + line.strip()
                elif net > 0:
                    parts = [line]
                    acc = net
                    j = i + 1
                    while j < len(lines) and acc > 0:
                        parts.append(lines[j].strip())
                        acc += count_brackets(lines[j])
                        j += 1
                    fixed.append("\\n".join(parts))
                    i = j
                    continue
                else:
                    fixed.append(line)
                i += 1
            body = le.join(fixed)

            # R4: Quote labels with special chars
            def quote_label(match):
                prefix, label, suffix = match.group(1), match.group(2), match.group(3)
                if label.startswith('"') and label.endswith('"'):
                    return match.group(0)
                if re.search(r"[()<>:=\[\]{}/]", label):
                    return f'{prefix}"{label}"{suffix}'
                return match.group(0)

            body = re.sub(r'(\[)([^\]"]+)(\])', quote_label, body)
            body = re.sub(r'(\{)([^}"]+)(\})', quote_label, body)

            # R5: Replace [] inside quoted labels with ()
            def fix_nested(match):
                inner = match.group(1).replace("[", "(").replace("]", ")")
                return '["' + inner + '"]'

            body = re.sub(r'\["([^"]*(?:\[[^\]]*\])[^"]*)"\]', fix_nested, body)

            # R6: Fix inner quotes in unquoted labels
            def fix_inner_quotes(match):
                label = match.group(1)
                if '"' in label:
                    label = label.replace('"', "'")
                    return '["' + label + '"]'
                return match.group(0)

            body = re.sub(r'\[([^\]"]*"[^\]]*)\]', fix_inner_quotes, body)

        # R11: Fix inner quotes in ALREADY-quoted labels ["...text"..."]
        def fix_inner_quotes_quoted(match):
            before = match.group(1)
            after = match.group(2)
            return '["' + before + "'" + after + '"]'

        body = re.sub(r'\["([^"]*)"([^"]*)"\]', fix_inner_quotes_quoted, body)

        return header + body + footer

    text = re.sub(
        r"(```mermaid\r?\n)((?:flowchart|sequenceDiagram|classDiagram|graph|stateDiagram|erDiagram|gantt|pie|journey|mindmap|timeline|quadrantChart|block-beta|sankey-beta)[^\r\n]*\r?\n)((?:(?!```)[\s\S])*)(```)",
        fix_flowchart_block,
        text,
    )

    if text != original:
        with open(fp, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        return True
    return False


# ============================================================
# mmdc validation (optional, requires Node.js)
# ============================================================


def find_mmdc():
    """Try to find mmdc. Returns command list or None."""
    import subprocess

    for npx in ["npx.cmd", "npx"]:
        try:
            r = subprocess.run(
                [npx, "--yes", "@mermaid-js/mermaid-cli", "--version"], capture_output=True, timeout=30, shell=True
            )
            if r.returncode == 0:
                return [npx, "--yes", "@mermaid-js/mermaid-cli"]
        except Exception:
            pass
    return None


def check_mmdc(fp, text, le):
    """Validate with mmdc. Returns list of (line_num, error_msg)."""
    import subprocess, tempfile

    issues = []
    mmdc_base = find_mmdc()
    if not mmdc_base:
        return issues

    for m in re.finditer(r"(```mermaid\r?\n)(flowchart [^\r\n]*\r?\n)((?:(?!```)[\s\S])*)(```)", text):
        ftype = m.group(2)
        body = m.group(3)
        content = ftype + body.rstrip()
        if content.endswith("```"):
            content = content[:-3].rstrip()
        block_start = text[: m.start()].count(le) + 2

        with tempfile.NamedTemporaryFile(mode="w", suffix=".mmd", delete=False, encoding="utf-8") as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        out_path = tempfile.mktemp(suffix=".svg")
        try:
            cmd = mmdc_base + ["-i", tmp_path, "-o", out_path, "-b", "transparent"]
            result = subprocess.run(cmd, capture_output=True, timeout=30, shell=True)
            if result.returncode != 0:
                stderr = result.stderr.decode("utf-8", errors="replace")
                line_match = re.search(r"[Ll]ine (\d+)", stderr)
                actual_line = block_start + int(line_match.group(1)) if line_match else block_start
                for sline in stderr.split("\n"):
                    sline = sline.strip()
                    if sline and "at " not in sline and "file:///" not in sline:
                        issues.append((actual_line, sline[:120]))
                        break
                else:
                    issues.append((actual_line, "Parse error"))
        except Exception:
            pass
        finally:
            os.unlink(tmp_path)
            if os.path.exists(out_path):
                os.unlink(out_path)

    return issues


# ============================================================
# Main
# ============================================================


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    directory = sys.argv[1]
    check_mode = "--check-only" in sys.argv
    use_mmdc = "--mmdc" in sys.argv

    os.chdir(directory)
    md_files = sorted(f for f in glob.glob("*.md") if not f.startswith("_"))

    total_blocks = 0
    total_issues = 0
    fixed_files = 0

    print(f"扫描: {directory} ({len(md_files)} 文件)")
    if use_mmdc:
        mmdc = find_mmdc()
        print(f"mmdc: {mmdc or '未找到 (跳过)'}")
    print()

    for fp in md_files:
        with open(fp, "rb") as fh:
            raw = fh.read()
        le = "\r\n" if b"\r\n" in raw else "\n"
        text = raw.decode("utf-8")

        blocks = len(re.findall(r"```mermaid\r?\nflowchart", text))
        total_blocks += blocks
        if not blocks:
            continue

        # Rule check
        rule_issues = check_rules(fp, text, le)

        # mmdc check (optional)
        mmdc_issues = []
        if use_mmdc:
            mmdc_issues = check_mmdc(fp, text, le)

        all_issues = rule_issues + [(ln, [msg], "") for ln, msg in mmdc_issues]

        if all_issues:
            total_issues += len(all_issues)
            print(f"{fp}:")
            for item in all_issues:
                if len(item) == 3:
                    ln, probs, ctx = item
                    print(f"  L{ln}: {', '.join(probs)}  {ctx}")
                else:
                    ln, msg = item
                    print(f"  L{ln}: mmdc: {msg}")

        if not check_mode and (rule_issues or mmdc_issues):
            if fix_file(fp, le):
                fixed_files += 1
                print(f"  -> 已修复")

    print(f"\n{'=' * 40}")
    print(f"mermaid 块: {total_blocks}")
    print(f"发现问题: {total_issues}")
    if not check_mode:
        print(f"修复文件: {fixed_files}")

    # Post-fix mmdc validation
    if use_mmdc and not check_mode and fixed_files > 0:
        print(f"\n修复后 mmdc 验证...")
        remaining = 0
        for fp in md_files:
            with open(fp, "rb") as fh:
                raw = fh.read()
            le = "\r\n" if b"\r\n" in raw else "\n"
            text = raw.decode("utf-8")
            post = check_mmdc(fp, text, le)
            if post:
                remaining += len(post)
                print(f"  {fp}: {len(post)} 个需手动修复")
                for ln, msg in post:
                    print(f"    L{ln}: {msg}")
        if remaining == 0:
            print("  全部通过!")
        else:
            print(f"  {remaining} 个需手动修复")


if __name__ == "__main__":
    main()
