# -*- coding: utf-8 -*-
"""多轮错存逆向：对单行 Unicode 尝试有限深度（默认≤3）的 encode→decode 链，用于合并/局部乱码。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# 单步：Unicode -> bytes(用 enc 编码) -> Unicode(用 dec 解码)
Step = Tuple[str, str, str]  # (name, encode_codec, decode_codec)


def default_steps() -> List[Step]:
    """常见「错读后再存」的逆向一步（可多步串联，深度由调用方限制）。"""
    return [
        ("latin1->gbk", "latin-1", "gbk"),
        ("latin1->gb18030", "latin-1", "gb18030"),
        ("latin1->utf-8", "latin-1", "utf-8"),
        ("cp1252->utf-8", "cp1252", "utf-8"),
        # UTF-8 文本被误按 GBK 解码再保存等场景（strict，失败则该步不可用）
        ("utf-8->gbk", "utf-8", "gbk"),
        ("utf-8->gb18030", "utf-8", "gb18030"),
    ]


def _apply_step(s: str, enc: str, dec: str) -> Optional[str]:
    try:
        raw = s.encode(enc)
    except (UnicodeEncodeError, LookupError):
        return None
    try:
        return raw.decode(dec)
    except (UnicodeDecodeError, LookupError):
        return None


def score_recovery_candidate(s: str, *, reference: Optional[str] = None) -> float:
    """
    偏高：CJK 与全角标点；含 U+FFFD 直接判失败。
    若提供 reference（通常为乱码原行），对相对参考串异常膨胀的长度罚分，抑制多步 utf-8↔gbk 产生的「随机汉字海」。
    """
    if "\ufffd" in s:
        return -1e9
    score = 0.0
    for ch in s:
        o = ord(ch)
        if 0x4E00 <= o <= 0x9FFF:
            score += 3.0
        elif 0x3400 <= o <= 0x4DBF or 0x20000 <= o <= 0x2CEAF:
            score += 2.0
        elif 0x3000 <= o <= 0x303F or (0xFF00 <= o <= 0xFFEF):
            score += 1.0
        elif 0xE000 <= o <= 0xF8FF or 0xF0000 <= o <= 0xFFFFD:
            score -= 5.0

    if reference is not None and len(reference) > 0:
        # 合并错存常见：GBK 字节被拆成多个 Latin-1 字符，「字符数」与错链生成的汉字串相近；
        # 用 UTF-8 字节长度比更能区分「真恢复」（通常比乱码显示更短）与随机汉字膨胀。
        try:
            ref_b = len(reference.encode("utf-8"))
            cur_b = len(s.encode("utf-8"))
        except UnicodeEncodeError:
            ref_b, cur_b = len(reference), len(s)
        ratio_b = cur_b / float(max(ref_b, 1))
        if ratio_b > 1.12:
            score -= (ratio_b - 1.12) * 39.0
        elif ratio_b < 0.55:
            score -= (0.55 - ratio_b) * 12.0
        score -= abs(cur_b - ref_b) * 0.12

    return score


@dataclass
class ChainCandidate:
    text: str
    score: float
    chain: List[str]


def select_reverse_apply_candidate(
    candidates: List[ChainCandidate],
    *,
    start_line: str,
    orig_score: float,
    min_score_delta: float,
) -> Optional[ChainCandidate]:
    """
    在 reverse_try 的若干候选中选一条用于自动落盘。

    经验：按「总分」取第一名常会选中多步 utf-8↔gbk 堆叠出的高 CJK 分噪声（如 latin1->gbk 后再 utf-8->gbk）。
    此处在「达到 min_score_delta」的前提下**优先更短的逆向链**，同深度再取更高分；并排除含 U+FFFD 的结果。
    """
    thr = orig_score + min_score_delta
    viable: List[ChainCandidate] = []
    for c in candidates:
        if not c.chain:
            continue
        if c.score < thr:
            continue
        if "\ufffd" in c.text:
            continue
        viable.append(c)
    if not viable:
        return None

    def _utf8_len(s: str) -> int:
        try:
            return len(s.encode("utf-8"))
        except UnicodeEncodeError:
            return len(s)

    ref_b = _utf8_len(start_line)

    def sort_key(c: ChainCandidate) -> Tuple[int, float, int, int]:
        cur_b = _utf8_len(c.text)
        return (len(c.chain), -c.score, abs(cur_b - ref_b), cur_b)

    viable.sort(key=sort_key)
    return viable[0]


def reverse_try_from_text(
    start: str,
    *,
    max_depth: int = 3,
    steps: Optional[List[Step]] = None,
    top_k: int = 5,
) -> List[ChainCandidate]:
    """
    BFS 展开至多 max_depth 步，每步套用 default_steps 中可成功的变换；去重字符串。
    返回按 score 降序的 top_k 条（含深度 0 原串）。
    """
    if max_depth < 0:
        max_depth = 0
    if top_k < 1:
        top_k = 1
    st = steps if steps is not None else default_steps()

    seen: Dict[str, Tuple[float, List[str]]] = {}
    # (text, depth, chain_names)
    frontier: List[Tuple[str, int, List[str]]] = [(start, 0, [])]

    while frontier:
        cur, depth, chain = frontier.pop(0)
        sc = score_recovery_candidate(cur, reference=start)
        prev = seen.get(cur)
        if prev is None or sc > prev[0]:
            seen[cur] = (sc, chain)

        if depth >= max_depth:
            continue
        for name, enc, dec in st:
            nxt = _apply_step(cur, enc, dec)
            if nxt is None or nxt == cur:
                continue
            frontier.append((nxt, depth + 1, chain + [name]))

    candidates = [ChainCandidate(text=t, score=sc, chain=ch) for t, (sc, ch) in seen.items()]
    candidates.sort(key=lambda c: (-c.score, len(c.chain), len(c.text), c.text))
    return candidates[:top_k]


def parse_line_ranges(spec: str, *, max_line: int) -> List[int]:
    """
    解析 "1,5,10-12" 为 1-based 行号列表，去重升序；越界行号丢弃。
    """
    out: List[int] = []
    if not spec or not spec.strip():
        return out
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            try:
                lo = int(a.strip())
                hi = int(b.strip())
            except ValueError:
                continue
            if lo > hi:
                lo, hi = hi, lo
            for n in range(lo, hi + 1):
                if 1 <= n <= max_line:
                    out.append(n)
        else:
            try:
                n = int(part)
            except ValueError:
                continue
            if 1 <= n <= max_line:
                out.append(n)
    return sorted(set(out))
