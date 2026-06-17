---
name: encode-reader
description: 多编码文件安全读取工具。自动检测 GBK / GB2312 / UTF-8 / Latin-1 等编码并正确解码输出。当用户需要读取非 UTF-8 编码文件、遇到乱码、打开 GBK 文件时使用。触发词：乱码、编码、GBK、GB2312、读取乱码文件。
user-invocable: true
allowed-tools:
  - Bash(python *)
  - Read
  - Grep
---

# 多编码文件读取

安全读取 GBK / GB2312 / UTF-8 / Latin-1 等编码文件，自动检测并正确输出 UTF-8 文本。

## 快速使用

```bash
# 读取文件（自动检测编码）
python .agents/skills/encode-reader/scripts/read_encoded.py <文件路径>

# 只检测编码，不输出内容
python .agents/skills/encode-reader/scripts/read_encoded.py <文件路径> --detect-only

# 指定起始行和行数
python .agents/skills/encode-reader/scripts/read_encoded.py <文件路径> --start 100 --lines 50

# 强制指定编码（跳过检测）
python .agents/skills/encode-reader/scripts/read_encoded.py <文件路径> --encoding gbk
```

## 检测顺序

脚本按以下优先级尝试解码：

1. `chardet` 库（如已安装，最准确）
2. UTF-8（带 BOM 和不带 BOM）
3. GBK / GB2312 / GB18030
4. Latin-1（兜底）

输出始终为 **UTF-8** 文本。

## 脚本表

| 脚本 | 用途 |
|------|------|
| `scripts/read_encoded.py` | 多编码文件读取，输出 UTF-8 |
