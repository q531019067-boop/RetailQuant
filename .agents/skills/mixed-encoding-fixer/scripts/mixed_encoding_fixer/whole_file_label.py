# -*- coding: utf-8 -*-
"""整文件严格 UTF-8 / GBK 解码后的标签（与按行 fix_encoding 逻辑独立）。"""

from __future__ import annotations


def label_from_bytes(content: bytes) -> str:
    """返回 gbk / utf-8 / mix / right / unknown。"""
    if not content:
        return "right"

    try:
        utf8_text = content.decode("utf-8")
        is_utf8 = True
    except UnicodeDecodeError:
        utf8_text = None
        is_utf8 = False

    try:
        gbk_text = content.decode("gbk")
        is_gbk = True
    except UnicodeDecodeError:
        gbk_text = None
        is_gbk = False

    if is_utf8 and not is_gbk:
        return "utf-8"
    if is_gbk and not is_utf8:
        return "gbk"
    if is_utf8 and is_gbk:
        return _resolve_ambiguous_decode(utf8_text, gbk_text, content)
    return "unknown"


def _resolve_ambiguous_decode(utf8_text: str, gbk_text: str, raw: bytes) -> str:
    if utf8_text != gbk_text:
        return "mix"
    if utf8_text.isascii():
        return "right"
    if any("\u4e00" <= ch <= "\u9fff" for ch in utf8_text):
        return "utf-8" if _has_utf8_multibyte_pattern(raw) else "gbk"
    return "right"


def _has_utf8_multibyte_pattern(data: bytes) -> bool:
    i = 0
    n = len(data)
    while i < n:
        b = data[i]
        if b < 0x80:
            i += 1
            continue
        if 0xC0 <= b <= 0xDF:
            if i + 1 < n and 0x80 <= data[i + 1] <= 0xBF:
                return True
            i += 2
            continue
        if 0xE0 <= b <= 0xEF:
            if i + 2 < n and 0x80 <= data[i + 1] <= 0xBF and 0x80 <= data[i + 2] <= 0xBF:
                return True
            i += 3
            continue
        if 0xF0 <= b <= 0xF7:
            if (
                i + 3 < n
                and 0x80 <= data[i + 1] <= 0xBF
                and 0x80 <= data[i + 2] <= 0xBF
                and 0x80 <= data[i + 3] <= 0xBF
            ):
                return True
            i += 4
            continue
        i += 1
    return False
