# 使用示例（mixed-encoding-fixer）

以下命令假设当前目录为 skill 根目录（包含 `SKILL.md` 和 `scripts/`）。

## 示例1：常规三步修复（推荐）

```bash
python scripts/mixed_encoding_tool.py probe path/to/file.txt
python scripts/mixed_encoding_tool.py auto -t utf8 path/to/file.txt path/to/file.txt.fixed
Copy-Item path/to/file.txt.fixed path/to/file.txt -Force
```

## 示例2：先看分布再决定

```bash
python scripts/mixed_encoding_tool.py check --json path/to/file.txt
python scripts/mixed_encoding_tool.py suspect-lines path/to/file.txt
```

## 示例3：有 golden 时用 recover

```bash
python scripts/mixed_encoding_tool.py recover path/to/damaged.txt path/to/golden.txt path/to/recovered.txt
python scripts/compare_files.py path/to/recovered.txt path/to/golden.txt
```

## 示例4：复杂乱码补充诊断

```bash
python scripts/mixed_encoding_tool.py byte-inspect path/to/file.txt
python scripts/mixed_encoding_tool.py analyze --reconstruction-hints path/to/file.txt
```

## 示例5：源代码优先（source-fix）

```bash
# 先 dry-run 看会改哪些内容
python scripts/mixed_encoding_tool.py source-fix "K:/Sword11/Source/Common/SO3World/Src/KLuaConstList.cpp" --dry-run

# 单文件直接修复（SVN 模式）
python scripts/mixed_encoding_tool.py source-fix "K:/Sword11/Source/Common/SO3World/Src/KLuaConstList.cpp"

# 目录批量修复（先 dry-run，再执行）
python scripts/mixed_encoding_tool.py source-fix "K:/Sword11/Source/Common/SO3World/Src" --dry-run
python scripts/mixed_encoding_tool.py source-fix "K:/Sword11/Source/Common/SO3World/Src"
```

## 示例6：PowerShell 执行规范

```powershell
python scripts/mixed_encoding_tool.py probe "K:\demo\a.txt"
python scripts/mixed_encoding_tool.py auto -t utf8 "K:\demo\a.txt" "K:\demo\a.fixed.txt"
Copy-Item "K:\demo\a.fixed.txt" "K:\demo\a.txt" -Force
```

不要使用 `&&` 串联，按行执行即可。
