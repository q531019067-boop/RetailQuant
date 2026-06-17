---
name: sourcecode-fix-encoding
description: 根据 Git HEAD 或备份文件对比，修复源码文件中的编码乱码与注释乱码。当用户提到"乱码修复""编码修复""根据Git恢复注释""根据备份恢复注释"时使用。
user-invocable: true
allowed-tools:
  - Bash(python *)
  - Bash(git *)
  - Read
  - Write
  - Grep
---

# /sourcecode-fix-encoding — 基于 Git/备份 的乱码修复

用于修复源码文件（`.cpp/.h/.py/.lua/.md` 等）的编码乱码问题：

- **Git 模式**：以 `git show HEAD:<file>` 的内容作为参考，恢复注释并纠正编码。
- **备份模式**：以指定备份文件/目录作为参考。

核心原则：**编码修复**与**注释修复**独立执行，保证代码结构不被破坏。

## 用法

```bash
# 1) Git模式：处理目录下 git 已修改文件
python .agents/skills/sourcecode-fix-encoding/scripts/fix_encoding.py <FILE_OR_DIR>

# 2) 单文件修复
python .agents/skills/sourcecode-fix-encoding/scripts/fix_encoding.py path/to/file.cpp

# 3) 备份模式：以备份目录/文件作为参考
python .agents/skills/sourcecode-fix-encoding/scripts/fix_encoding.py <path> --backup <backup_dir>

# 4) 仅预览，不落盘
python .agents/skills/sourcecode-fix-encoding/scripts/fix_encoding.py <path> --backup <backup_dir> --dry-run

# 5) 自检
python .agents/skills/sourcecode-fix-encoding/scripts/fix_encoding.py --self-check
```

## 脚本表

| 脚本 | 用途 |
|------|------|
| `scripts/fix_encoding.py` | 主修复脚本（Git + 备份双模式） |

## 参考文档表

| 主题 | 文件 | 内容 |
|------|------|------|
| 执行规则 | `references/rules.md` | 执行规则与注意事项 |

## 示例表

| 场景 | 文件 | 内容 |
|------|------|------|
| 常见场景 | `examples/usage.md` | 各场景使用示例 |
