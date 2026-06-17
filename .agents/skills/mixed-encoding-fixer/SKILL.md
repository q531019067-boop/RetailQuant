---
name: mixed-encoding-fixer
description: 修复 GBK/UTF-8 混合乱码。源码优先走 Git 对照修复；非源码走 probe→auto/recover 通用诊断修复流程。当用户提到"编码乱码""混合编码""GBK乱码""问号乱码"时使用。
user-invocable: true
allowed-tools:
  - Bash(python *)
  - Bash(git *)
  - Read
  - Write
  - Grep
---

# /mixed-encoding-fixer — 混合编码乱码修复

## 适用场景

- 文件出现 GBK/UTF-8 混合乱码（中文问号、乱码、`U+FFFD` 等）
- 终端或文件中异常字符（注释/文本不可读）
- 需要判断"可转码修复"还是需要参考基准重建

## 总决策树

```
第 1 步：目标文件类型是什么？
  │
  ├─ 有 Git 工作区可用 → 【策略 1】source-fix（Git 模式：git show HEAD 作参考）
  │
  └─ 无 Git 参考 / 非源码文本 → 【策略 2】探针诊断修复
       │
       ├─ verdict == "recoverable_by_transcode" → auto 修复
       ├─ verdict == "needs_reconstruction" 且有 golden → recover
       └─ 其余 → local-repair / suspect-lines
```

## 策略 1：source-fix（有 Git 参考时优先）

用 `sourcecode-fix-encoding` 的 `fix_encoding.py`，以 `git show HEAD:<file>` 为参考恢复注释并纠编码。

```bash
# Git 模式：只处理 git status 为已修改的文件
python .agents/skills/sourcecode-fix-encoding/scripts/fix_encoding.py <FILE_OR_DIR>

# 备份模式：以备份为参考
python .agents/skills/sourcecode-fix-encoding/scripts/fix_encoding.py <path> --backup <backup_dir>
```

## 策略 2：通用编码诊断修复

适用于无 Git 参考的普通文本文件。

### 第一步：probe 诊断（必须）

```bash
python .agents/skills/mixed-encoding-fixer/scripts/mixed_encoding_tool.py probe "<FILE>"
```

probe 输出 JSON，关键字段：

| 字段 | 含义 | agent 分支 |
|------|------|-----------|
| `corruption.verdict` | 损坏程度 | 见下文 |
| `corruption.auto_recommended` | 是否推荐 auto | true → auto |
| `corruption.replacement_utf8_triplet_count` | U+FFFD 数量 | >0 可能不可逆 |

### 第二步：按 verdict 选择修复

**2A. recoverable_by_transcode（最常见）**
```bash
python .agents/skills/mixed-encoding-fixer/scripts/mixed_encoding_tool.py auto -t utf8 "<FILE>" "<FILE>.fixed"
```

**2B. needs_reconstruction 且有 golden**
```bash
python .agents/skills/mixed-encoding-fixer/scripts/mixed_encoding_tool.py recover "<DAMAGED>" "<GOLDEN>" "<OUT>"
```

**2C. 其余情况**
```bash
python .agents/skills/mixed-encoding-fixer/scripts/mixed_encoding_tool.py local-repair "<FILE>" "<FILE>.repaired"
python .agents/skills/mixed-encoding-fixer/scripts/mixed_encoding_tool.py suspect-lines "<FILE>"
```

### 第三步：替换原文件

所有修复先输出到新文件，确认无误后覆盖；替换后再次 `probe` 验证。

## 快速指南

| 场景 | 操作 |
|------|------|
| 有 Git 参考的源码 | 用策略 1（source-fix） |
| GBK/UTF-8 混合，结构完整 | `auto -t utf8` |
| 有 golden 参考文件 | `recover` |
| 需要保留原编码 | `local-repair` |
| 只是需要正确读取 GBK 文件 | 用 `encode-reader` skill |

## 脚本表

| 脚本 | 用途 |
|------|------|
| `scripts/mixed_encoding_tool.py` | 统一入口：probe / auto / recover / local-repair |
| `scripts/fix_encoding.py` | Git/备份对照修复引擎（与 sourcecode-fix-encoding 共用） |
