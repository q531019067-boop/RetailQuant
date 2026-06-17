---
name: md-math-check
description: 检查和修复 Markdown 文件中的 LaTeX 数学公式语法问题。当用户提到"公式""数学""渲染""LaTeX""MathJax"时使用。
user-invocable: true
allowed-tools:
  - Bash(python scripts/check_math.py *)
  - Bash(python scripts/fix_math.py *)
  - Read
  - Edit
  - Grep
  - Glob
---

# /md-math-check — Markdown 数学公式检查与修复

扫描 .md 文件中的 LaTeX 数学公式，检测常见渲染问题并自动修复。

## 快速使用

```bash
# 检查单个文件
python scripts/check_math.py <文件路径.md>

# 自动修复（生成修复后的文件）
python scripts/fix_math.py <文件路径.md>

# 检查整个目录
python scripts/check_math.py <目录> --recursive
```

## 工作流程

1. 用户提供 .md 文件路径
2. 运行 `check_math.py` 扫描问题
3. 根据报告手动修复，或运行 `fix_math.py` 自动修复
4. 用 Typora 等渲染器验证显示效果

## 检测规则速查

| # | 规则 | 严重度 | 自动修复 |
|---|------|--------|---------|
| 1 | `{,}` 千位分隔符 | Error | 替换为无分隔数字 |
| 2 | 表格内 `\mid` / `\|` | Error | 替换为 `\vert` 或移出表格 |
| 3 | `\Sigma` 误用为求和 | Warning | 替换为 `\sum` |
| 4 | 行内公式含 `\frac` + 中文 `\text` | Warning | 建议改块级或纯文本 |
| 5 | `$$` 未独占一行 | Error | 前后加空行 |
| 6 | `$` 前后有空格 | Warning | 去除空格 |
| 7 | 未配对的 `$` | Error | 标记位置 |
| 8 | `\mathrm{}` / `\textrm{}` 含中文 | Warning | 替换为 `\text{}` |

## 详细文档

- 公式语法规则 → `references/rules.md`
- 故障排除指南 → `references/troubleshooting.md`
- 中文兼容方案 → `references/chinese_compat.md`

## 示例

- 修复前后对比 → `examples/before_after.md`

## 文件结构

```
md-math-check/
├── SKILL.md                    ← 本文件
├── scripts/
│   ├── check_math.py           ← 扫描检查
│   └── fix_math.py             ← 自动修复
├── references/
│   ├── rules.md                ← 详细规则
│   ├── troubleshooting.md      ← 故障排除
│   └── chinese_compat.md       ← 中文兼容
└── examples/
    └── before_after.md         ← 修复示例
```
