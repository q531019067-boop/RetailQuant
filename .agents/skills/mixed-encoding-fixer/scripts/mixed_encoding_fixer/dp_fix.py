# -*- coding: utf-8 -*-
"""MIX 行 DP 修复（FR-06）。"""


def fix_mix_line_dp(line_bytes: bytes, max_seg_len: int = 64) -> str:
    n = len(line_bytes)
    if n == 0:
        return ""
    try:
        return line_bytes.decode("utf-8")
    except UnicodeDecodeError:
        pass
    utf8_cache = {}
    gbk_cache = {}

    def utf8_score(seg: bytes) -> float:
        if seg in utf8_cache:
            return utf8_cache[seg]
        try:
            text = seg.decode("utf-8")
        except UnicodeDecodeError:
            utf8_cache[seg] = float("-inf")
            return float("-inf")
        score = float(len(seg))
        for ch in text:
            if "\u4e00" <= ch <= "\u9fff":
                score += 1.0
            elif ch.isalnum() or ch in " .,;:!?()[]{}":
                score += 0.5
            elif ch in "\t\r\n":
                pass
            else:
                score -= 1.0
        utf8_cache[seg] = score
        return score

    def gbk_score(seg: bytes) -> float:
        if seg in gbk_cache:
            return gbk_cache[seg]
        text = seg.decode("gbk", errors="replace")
        score = 0.0
        valid_pairs = 0
        i = 0
        while i < len(seg):
            b = seg[i]
            if b <= 0x7F:
                i += 1
                continue
            if 0x81 <= b <= 0xFE and i + 1 < len(seg):
                b2 = seg[i + 1]
                if (0x40 <= b2 <= 0x7E) or (0x80 <= b2 <= 0xFE):
                    valid_pairs += 1
                    i += 2
                    continue
            i += 1
        score += valid_pairs * 2.0
        for ch in text:
            if "\u4e00" <= ch <= "\u9fff":
                score += 1.0
            elif ch.isalnum() or ch in " .,;:!?()[]{}":
                score += 0.5
            elif ch in "\t\r\n":
                pass
            else:
                score -= 1.0
        gbk_cache[seg] = score
        return score

    dp = [float("-inf")] * (n + 1)
    prev = [(-1, None)] * (n + 1)
    dp[0] = 0.0

    for i in range(1, n + 1):
        j0 = max(0, i - max_seg_len)
        for j in range(j0, i):
            seg = line_bytes[j:i]
            utf8 = utf8_score(seg)
            gbk = gbk_score(seg)
            if utf8 > gbk and utf8 > float("-inf"):
                cand = dp[j] + utf8
                if cand > dp[i]:
                    dp[i] = cand
                    prev[i] = (j, "utf-8")
            elif gbk > float("-inf"):
                cand = dp[j] + gbk
                if cand > dp[i]:
                    dp[i] = cand
                    prev[i] = (j, "gbk")

    if dp[n] == float("-inf"):
        return line_bytes.decode("utf-8", errors="replace")

    result = []
    pos = n
    while pos > 0:
        j, enc = prev[pos]
        if j < 0:
            break
        seg = line_bytes[j:pos]
        result.append((enc, seg))
        pos = j
    result.reverse()
    fixed = ""
    for enc, seg in result:
        if enc == "utf-8":
            fixed += seg.decode("utf-8", errors="replace")
        else:
            fixed += seg.decode("gbk", errors="replace")
    return fixed
