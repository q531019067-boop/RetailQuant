# Agent 工具指令索引

完整规则见 `../SKILL.md`。本文件只保留高频可复制命令。

## 1) 确定 SKILL_ROOT

所有命令中的 `<SKILL_ROOT>` 需替换为本 skill 目录的实际路径。

```bash
python "<SKILL_DIR>/scripts/resolve_skill_root.py" --json
```

或由 agent 框架直接提供路径（Cursor/Claude Code/Trae/Codex 各自注入）。

## 2) 决策优先级（按顺序判断）

```
有 SVN 或备份？ → source-fix "<FILE_OR_DIR>" [--backup "<DIR>"]
无参考基准？   → probe "<FILE>" → 根据 verdict 选择 auto / recover / local-repair
```

## 3) 常用命令（已按优先级排序）

```bash
# === 策略 1：源码 + SVN/备份 ===
python "<SKILL_ROOT>/scripts/mixed_encoding_tool.py" source-fix "<FILE_OR_DIR>" --dry-run
python "<SKILL_ROOT>/scripts/mixed_encoding_tool.py" source-fix "<FILE_OR_DIR>" [--backup "<BACKUP>"]

# === 策略 2：诊断 + 修复 ===
python "<SKILL_ROOT>/scripts/mixed_encoding_tool.py" probe "<FILE>"
python "<SKILL_ROOT>/scripts/mixed_encoding_tool.py" auto -t utf8 "<FILE>" "<FILE>.fixed"
python "<SKILL_ROOT>/scripts/mixed_encoding_tool.py" local-repair "<FILE>" "<FILE>.repaired"
python "<SKILL_ROOT>/scripts/mixed_encoding_tool.py" recover "<DAMAGED>" "<GOLDEN>" "<OUT>"
python "<SKILL_ROOT>/scripts/mixed_encoding_tool.py" analyze -c 5 -o report.json "<FILE>"

# === 辅助 ===
python "<SKILL_ROOT>/scripts/compare_files.py" "<A>" "<B>"
```

## 4) 硬性约束

- **先 probe 再修复**，禁止跳过诊断。
- **不手写 `python -c`** 做字节/哈希统计。
- **不直接覆盖原文件**，先输出到新文件再替换。
- PowerShell **不用 `&&`** 串命令，分行执行或使用 `;`。
