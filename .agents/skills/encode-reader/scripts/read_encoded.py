"""多编码文件安全读取 — 自动检测编码，正确解码输出 UTF-8。

用法:
    python read_encoded.py <file>                 # 自动检测编码并输出
    python read_encoded.py <file> --detect-only   # 仅检测编码
    python read_encoded.py <file> --start 100 --lines 50  # 分页读取
    python read_encoded.py <file> --encoding gbk  # 强制指定编码
    python read_encoded.py <file> --output out.txt  # 写入文件（推荐，绕过终端编码问题）

输出: UTF-8 文本到 stdout 或指定文件，元信息到 stderr。
注意: Windows PowerShell 的 > 重定向会破坏编码，推荐使用 --output 参数。
"""

from __future__ import annotations

import sys
from pathlib import Path


def detect_encoding(filepath: str) -> str:
    """检测文件编码，返回编码名称。"""
    # 1) 尝试 chardet
    try:
        import chardet

        with open(filepath, "rb") as f:
            raw = f.read(100_000)
        result = chardet.detect(raw)
        encoding = result.get("encoding")
        confidence = result.get("confidence", 0)
        if encoding and confidence > 0.7:
            return encoding
    except ImportError:
        pass
    except Exception:
        pass

    # 2) 尝试 UTF-8 BOM
    try:
        with open(filepath, "rb") as f:
            head = f.read(4)
        if head[:3] == b"\xef\xbb\xbf":
            return "utf-8-sig"
        if head[:2] == b"\xff\xfe":
            return "utf-16-le"
        if head[:2] == b"\xfe\xff":
            return "utf-16-be"
    except Exception:
        pass

    # 3) 尝试 UTF-8
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            f.read(50_000)
        return "utf-8"
    except UnicodeDecodeError:
        pass

    # 4) 尝试中文编码系列
    for enc in ["gb18030", "gbk", "gb2312"]:
        try:
            with open(filepath, "r", encoding=enc) as f:
                f.read(50_000)
            return enc
        except UnicodeDecodeError:
            continue

    # 5) 兜底 Latin-1
    return "latin-1"


def read_with_encoding(
    filepath: str,
    encoding: str,
    start: int | None = None,
    lines: int | None = None,
) -> str:
    """用指定编码读取文件内容。"""
    with open(filepath, "r", encoding=encoding, errors="replace") as f:
        if start is None and lines is None:
            return f.read()

        content = f.readlines()
        if start is not None:
            start = max(1, start) - 1  # 转为 0-based
            content = content[start:]

        if lines is not None:
            content = content[:lines]

        return "".join(content)


def main() -> None:
    args = sys.argv[1:]

    detect_only = "--detect-only" in args
    args = [a for a in args if a != "--detect-only"]

    specified_enc: str | None = None
    start_line: int | None = None
    max_lines: int | None = None
    output_path: str | None = None

    # 解析命名参数
    remaining = []
    i = 0
    while i < len(args):
        if args[i] == "--encoding" and i + 1 < len(args):
            specified_enc = args[i + 1]
            i += 2
        elif args[i] == "--start" and i + 1 < len(args):
            start_line = int(args[i + 1])
            i += 2
        elif args[i] == "--lines" and i + 1 < len(args):
            max_lines = int(args[i + 1])
            i += 2
        elif args[i] == "--output" and i + 1 < len(args):
            output_path = args[i + 1]
            i += 2
        else:
            remaining.append(args[i])
            i += 1

    if not remaining:
        print(
            "用法: python read_encoded.py <文件路径> [--detect-only] [--encoding xxx] [--start N] [--lines N]",
            file=sys.stderr,
        )
        sys.exit(1)

    filepath = remaining[0]
    if not Path(filepath).is_file():
        print(f"错误: 文件不存在 — {filepath}", file=sys.stderr)
        sys.exit(1)

    # 检测或使用指定编码
    encoding = specified_enc or detect_encoding(filepath)
    print(f"[编码: {encoding}]", file=sys.stderr)

    if detect_only:
        sys.exit(0)

    # 读取并输出
    try:
        content = read_with_encoding(filepath, encoding, start_line, max_lines)

        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"[已写入: {output_path}]", file=sys.stderr)
        else:
            sys.stdout.write(content)
    except Exception as e:
        print(f"读取失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
