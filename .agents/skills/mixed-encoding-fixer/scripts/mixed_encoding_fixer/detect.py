# -*- coding: utf-8 -*-
"""单行编码检测与主编码统计（FR-03、FR-04）。"""


def is_likely_gbk(data: bytes, threshold: float = 0.8) -> bool:
    non_ascii = 0
    valid_pairs = 0
    i = 0
    while i < len(data):
        b = data[i]
        if b <= 0x7F:
            i += 1
            continue
        non_ascii += 1
        if 0x81 <= b <= 0xFE and i + 1 < len(data):
            b2 = data[i + 1]
            if (0x40 <= b2 <= 0x7E) or (0x80 <= b2 <= 0xFE):
                valid_pairs += 1
                i += 2
                continue
        i += 1
    if non_ascii == 0:
        return False
    score = valid_pairs / (non_ascii / 2)
    return score >= threshold


def classify_line_bytes(line_bytes: bytes, threshold: float = 0.8) -> str:
    if not line_bytes:
        return "ANSI"
    if all(b <= 0x7F for b in line_bytes):
        return "ANSI"
    try:
        t = line_bytes.decode("utf-8")
    except UnicodeDecodeError:
        pass
    else:
        if any(ord(ch) > 127 for ch in t):
            return "UTF-8"
    if is_likely_gbk(line_bytes, threshold):
        return "GBK"
    return "MIX"


def count_encodings(classifications):
    d = {"ANSI": 0, "GBK": 0, "UTF-8": 0, "MIX": 0}
    for c in classifications:
        d[c] = d.get(c, 0) + 1
    return d


def main_encoding_from_counts(counts: dict) -> str:
    gbk = counts.get("GBK", 0)
    utf = counts.get("UTF-8", 0)
    if gbk == 0 and utf == 0:
        return "utf8"
    if gbk > utf:
        return "gbk"
    return "utf8"
