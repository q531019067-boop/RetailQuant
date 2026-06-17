# -*- coding: utf-8 -*-
"""二进制读取、分行、写出（FR-01、FR-02、FR-10 写出部分）。"""


def split_raw_bytes(raw: bytes):
    """按 CRLF / CR / LF 切分为 (line_bytes, sep) 列表（不含 BOM 处理）。"""
    lines = []
    start = 0
    i = 0
    n = len(raw)
    while i < n:
        if raw[i] == 0x0D:
            if i + 1 < n and raw[i + 1] == 0x0A:
                sep = b"\r\n"
                line_bytes = raw[start:i]
                lines.append((line_bytes, sep))
                start = i + 2
                i = start
                continue
            sep = b"\r"
            line_bytes = raw[start:i]
            lines.append((line_bytes, sep))
            start = i + 1
            i = start
            continue
        if raw[i] == 0x0A:
            sep = b"\n"
            line_bytes = raw[start:i]
            lines.append((line_bytes, sep))
            start = i + 1
            i = start
            continue
        i += 1
    if start < n:
        lines.append((raw[start:], b""))
    return lines


def read_and_split(filepath):
    """返回 (行列表, bom_info, raw_without_bom)。raw_without_bom 为去 BOM 后的完整正文，供损坏统计。"""
    with open(filepath, "rb") as f:
        raw = f.read()
    bom_info = {"has_bom": False, "bom_type": None}
    if raw.startswith(b"\xef\xbb\xbf"):
        bom_info = {"has_bom": True, "bom_type": "utf8"}
        raw = raw[3:]
    raw_without_bom = raw
    lines = split_raw_bytes(raw)
    return lines, bom_info, raw_without_bom


def write_output_lines(filepath, line_objs, sep_list, target_encoding, keep_bom, bom_info):
    enc = "utf-8" if target_encoding in ("utf-8", "utf8") else target_encoding
    out_bytes = b""
    for line, sep in zip(line_objs, sep_list):
        text = line["text"]
        try:
            line_bytes = text.encode(enc)
        except UnicodeEncodeError:
            line_bytes = text.encode(enc, errors="replace")
        out_bytes += line_bytes + sep
    if keep_bom and bom_info.get("has_bom") and bom_info.get("bom_type") == "utf8":
        out_bytes = b"\xef\xbb\xbf" + out_bytes
    with open(filepath, "wb") as f:
        f.write(out_bytes)
