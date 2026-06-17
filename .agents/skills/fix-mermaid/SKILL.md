---
name: fix-mermaid
description: 批量检测并修复 markdown 中的 mermaid 语法错误。当用户提到 mermaid 语法错误、mermaid 渲染失败、parse error 时使用。
user-invocable: true
allowed-tools:
  - Bash(python *)
  - Bash(npx *)
  - Read
  - Write
  - Edit
  - Glob
  - Grep
---

# /fix-mermaid — Mermaid 语法检测与修复

纯 Python 实现，零依赖。支持所有 mermaid diagram 类型（flowchart、sequenceDiagram、classDiagram 等）。

## 用法

```bash
python scripts/fix_mermaid.py "<目录>" --check-only   # 仅检测
python scripts/fix_mermaid.py "<目录>"                 # 检测+修复
python scripts/fix_mermaid.py "<目录>" --mmdc          # 检测+修复+mmdc验证
```

## 快速参考

- **11条规则** → `references/rules.md`
- **12条踩坑教训** → `references/lessons.md`
- **使用示例** → `examples/usage.md`

## 文件结构

```
fix-mermaid/
├── SKILL.md                    ← 本文件
├── scripts/
│   └── fix_mermaid.py          ← 检测/修复脚本
├── references/
│   ├── rules.md                ← 11条规则详解
│   └── lessons.md              ← 踩坑教训
└── examples/
    └── usage.md                ← 使用示例
```
