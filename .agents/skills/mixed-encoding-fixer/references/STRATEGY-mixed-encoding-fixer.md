## 策略 2：mixed-encoding-fixer（mix 完整流程）

当目标不是源码，或源码但 **SVN 不可用且没有备份** 时，使用本策略。

### 常规简化流程

```bash
python "<SKILL_ROOT>/scripts/mixed_encoding_tool.py" probe "<FILE>"
python "<SKILL_ROOT>/scripts/mixed_encoding_tool.py" auto -t utf8 "<FILE>" "<FILE>.fixed"
Copy-Item "<FILE>.fixed" "<FILE>" -Force
```

### 完整老流程（逐步排查）

当你需要按“老流程”一步步推进（而不是只用三步 `probe -> auto -> 替换`）时，按下面顺序执行：

| 步骤 | 命令 | 目的 |
|------|------|------|
| 1 | `probe <FILE>` | 先拿 `verdict`、替换字符统计、下一步建议 |
| 2 | `byte-inspect <FILE>` | 看前几行 hex、EF BF BD 等落盘情况（替代手写 `python -c`） |
| 3 | `check --json <FILE>` | 看行级 ANSI/GBK/UTF-8/MIX 分布 |
| 4 | `suspect-lines <FILE>` | 把可疑行号集中出来 |
| 5 | `reverse-try <FILE>` | 针对可疑行尝试“逆向链”候选 |
| 6 | `reverse-apply <FILE> <OUT>` | 生成修复后的输出文件（不覆盖原文件） |
| 7 | `local-repair <FILE> <OUT>` | 一键：try-decodings + reverse-apply（适合整文件误标/轻度混合） |
| 8 | `try-decodings <FILE> <OUT>` | 尝试整文件解码策略（输出到新文件） |
| 9 | `detect <FILE> --json` | 只做整文件 strict 标签（gbk/utf8/mix/unknown），辅助判断 |
| 10 | `recover <DAMAGED> <GOLDEN> <OUT>` | 有 golden 时优先，一步恢复，精度高 |
| 11 | `diff2fixes <DAMAGED> <GOLDEN> <FIXES>` | 从 damaged/golden 生成 JSONL 补丁（便于审阅差异） |
| 12 | `apply <FILE> <FIXES> <OUT>` | 应用 JSONL 补丁写出新文件 |
| 13 | `compare_files.py <A> <B>` | 二进制一致性/哈希对比（替代手写 hash） |

对应命令示例（统一入口）：

```bash
python "<SKILL_ROOT>/scripts/mixed_encoding_tool.py" probe "<FILE>"
python "<SKILL_ROOT>/scripts/mixed_encoding_tool.py" byte-inspect "<FILE>"
python "<SKILL_ROOT>/scripts/mixed_encoding_tool.py" check --json "<FILE>"
python "<SKILL_ROOT>/scripts/mixed_encoding_tool.py" suspect-lines "<FILE>"
python "<SKILL_ROOT>/scripts/mixed_encoding_tool.py" reverse-try "<FILE>"
python "<SKILL_ROOT>/scripts/mixed_encoding_tool.py" reverse-apply "<FILE>" "<OUT>"
python "<SKILL_ROOT>/scripts/mixed_encoding_tool.py" local-repair "<FILE>" "<OUT>"
python "<SKILL_ROOT>/scripts/mixed_encoding_tool.py" recover "<DAMAGED>" "<GOLDEN>" "<OUT>"
python "<SKILL_ROOT>/scripts/mixed_encoding_tool.py" diff2fixes "<DAMAGED>" "<GOLDEN>" "<FIXES>"
python "<SKILL_ROOT>/scripts/mixed_encoding_tool.py" apply "<FILE>" "<FIXES>" "<OUT>"
python "<SKILL_ROOT>/scripts/compare_files.py" "<A>" "<B>"
```

