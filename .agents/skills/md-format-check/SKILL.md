---
name: md-format-check
description: 批量检测并修复 Markdown 文件中的格式语法错误。当用户提到"表格渲染不出来""md 格式错误""markdown 语法问题"时使用。
user-invocable: true
---

# Markdown 格式检查与修复

**目标**：批量检测 Markdown 文件中的格式语法错误，并自动修复。

## 适用场景

当用户说"表格渲染不出来"、"md 格式不对"、"markdown 语法错误"时，调用本 skill。

## 常见错误类型

| 错误类型 | 症状 | 修复方法 | 详见 |
|----------|------|----------|------|
| 表格在代码块内 | 表格显示为代码而非表格 | 移除代码块标记 | `references/table-in-codeblock.md` |
| 表格前缺空行 | 表格不渲染或与上文粘连 | 表格前加空行 | `references/table-blank-line.md` |
| 列数不匹配 | 表格渲染错乱 | 对齐列数 | `references/table-column-mismatch.md` |
| 分隔符格式错 | 表格不识别 | 修正分隔符格式 | `references/table-separator.md` |

## 参考文档表

| 主题 | 文件 | 内容 |
|------|------|------|
| 表格被代码块包裹 | `references/table-in-codeblock.md` | 错误原因、检测方法、修复方法 |
| 表格空行规范 | `references/table-blank-line.md` | 表格前后必须有空行的原因和检测 |
| 列数不匹配 | `references/table-column-mismatch.md` | 列数检测和修复方法 |
| 分隔符格式 | `references/table-separator.md` | 正确的分隔符写法 |

## 示例表

| 场景 | 文件 | 内容 |
|------|------|------|
| 典型错误案例 | `examples/typical-errors.md` | 各类错误的反面和正确写法对比 |

## 检查流程

1. 扫描目标目录下所有 `.md` 文件
2. 对每个文件执行以下检查：
   - 表格是否被代码块包裹
   - 表格前后是否有空行
   - 表格列数是否一致
   - 分隔符格式是否正确
3. 输出检查报告
4. 按用户指示修复问题

## 检查命令

```bash
# 检查表格是否在代码块内
grep -n '```' file.md | while read line; do
  linenum=$(echo "$line" | cut -d: -f1)
  nextline=$((linenum + 1))
  nextcontent=$(sed -n "${nextline}p" file.md")
  if echo "$nextcontent" | grep -q "^|"; then
    echo "Line $linenum: table inside code block"
  fi
done

# 检查表格前是否有空行
grep -n "^|" file.md | while read line; do
  linenum=$(echo "$line" | cut -d: -f1)
  prevline=$((linenum - 1))
  prevcontent=$(sed -n "${prevline}p" file.md")
  if [ -n "$prevcontent" ] && ! echo "$prevcontent" | grep -q "^|" && ! echo "$prevcontent" | grep -q "^$"; then
    echo "Line $linenum: table without blank line before"
  fi
done

# 检查列数是否匹配
awk '/^\|/ {
  n = split($0, a, "|") - 1
  if (prev_n > 0 && n != prev_n) {
    printf "Line %d: column count mismatch (%d vs %d)\n", NR, prev_n, n
  }
  prev_n = n
} !/^\|/ { prev_n = 0 }' file.md
```
