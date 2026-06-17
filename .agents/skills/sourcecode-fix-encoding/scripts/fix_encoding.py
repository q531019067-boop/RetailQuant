# -*- coding: utf-8 -*-
"""
SVN Source Code Encoding Fixer

Scans the SVN working copy for C/C++ (.c, .cpp, .cxx, .h, .hpp) and Lua
(.lua, .ls, .lh) files in modify (or add) status,
compares on-disk encoding with the reference (SVN HEAD or a backup), and
re-encodes when they differ. Comments are aligned to the reference using
context-based matching; non-comment code is not rewritten.

Core idea: encoding repair and comment repair are independent steps. Comment
restoration does not rely on guessing mojibake from character patterns; it uses
mapped pairs and a bulk text-diff threshold (see filter_comment_maps_for_fix).

Usage examples:

  # SVN mode -- scan modified source files under a directory
  python fix_encoding.py K:/Sword10/Source/Common/SO3World/Src

  # SVN mode -- single file
  python fix_encoding.py K:/Sword10/Source/Common/SO3World/Src/KLuaPlayer.cpp

  # Backup mode -- one clean file as reference
  python fix_encoding.py damaged.cpp --backup clean_backup.cpp

  # Backup mode -- backup directory, match by filename
  python fix_encoding.py ./corrupted_dir --backup ./backup_dir

  # Preview without writing
  python fix_encoding.py ./src --backup ./backup --dry-run

More detail: CLAUDE.md in this repo.
"""

import subprocess
import sys
import os
import re
import argparse

# ---------------------------------------------------------------------------
# Encoding helpers
# ---------------------------------------------------------------------------

BOM_UTF8 = b"\xef\xbb\xbf"
BOM_UTF16_LE = b"\xff\xfe"
BOM_UTF16_BE = b"\xfe\xff"


def detect_encoding(data: bytes) -> str:
    """Return one of: 'utf-8-bom', 'utf-16-le', 'utf-16-be', 'utf-8', 'gbk'."""
    if data[:3] == BOM_UTF8:
        return "utf-8-bom"
    if data[:2] == BOM_UTF16_LE:
        return "utf-16-le"
    if data[:2] == BOM_UTF16_BE:
        return "utf-16-be"
    try:
        data.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        pass
    return "gbk"


def decode_bytes(data: bytes, encoding: str) -> str:
    """
    Decode raw file bytes. All paths use errors='replace' so invalid sequences
    never raise (BOM+truncated body, bad UTF-16, mixed garbage, etc.).
    """
    if encoding == "utf-8-bom":
        return data[3:].decode("utf-8", errors="replace")
    if encoding == "utf-16-le":
        return data.decode("utf-16-le", errors="replace")
    if encoding == "utf-16-be":
        return data.decode("utf-16-be", errors="replace")
    if encoding == "utf-8":
        return data.decode("utf-8", errors="replace")
    if encoding == "gbk":
        return data.decode("gbk", errors="replace")
    return data.decode(encoding, errors="replace")


def encode_to_bytes(text: str, encoding: str) -> bytes:
    if encoding == "utf-8-bom":
        return BOM_UTF8 + text.encode("utf-8")
    if encoding == "utf-16-le":
        return text.encode("utf-16-le")
    if encoding == "utf-16-be":
        return text.encode("utf-16-be")
    if encoding == "utf-8":
        return text.encode("utf-8")
    if encoding == "gbk":
        return text.encode("gbk")
    return text.encode(encoding, errors="replace")


def _encode_text_robust(text: str, encoding: str) -> bytes:
    """encode_to_bytes with replace fallback (used when re-saving files)."""
    try:
        return encode_to_bytes(text, encoding)
    except (UnicodeEncodeError, LookupError):
        return text.encode(encoding, errors="replace")


# ---------------------------------------------------------------------------
# Comment lexers (extension -> dialect in EXTENSION_COMMENT_DIALECT)
# ---------------------------------------------------------------------------

COMMENT_KIND_LINE = "line"
COMMENT_KIND_BLOCK = "block"

# Every processable extension appears here with its comment lexer dialect.
# SUPPORTED_EXTS below is derived from these keys so scanners and dialect stay in sync.
# Adding a type (e.g. ini): add ".ini": "ini", implement the lexer, branch in
# _comments_with_lines -- do not omit the extension row.
EXTENSION_COMMENT_DIALECT: dict[str, str] = {
    ".c": "cpp",
    ".cpp": "cpp",
    ".cxx": "cpp",
    ".h": "cpp",
    ".hpp": "cpp",
    ".lua": "lua",
    ".ls": "lua",
    ".lh": "lua",
}

SUPPORTED_EXTS = tuple(sorted(EXTENSION_COMMENT_DIALECT.keys()))

# Fallback when the path suffix is not in EXTENSION_COMMENT_DIALECT (e.g. ad-hoc path).
DEFAULT_COMMENT_DIALECT = "cpp"

# Comment repair: only apply reference text when more than this many mapped
# comment pairs differ (bulk damage vs intentional small edits).
COMMENT_MISMATCH_TRIGGER_COUNT = 10


def file_comment_dialect(filepath: str) -> str:
    """Comment lexer for this path's extension; unknown suffix falls back to DEFAULT_COMMENT_DIALECT."""
    ext = os.path.splitext(filepath)[1].lower()
    return EXTENSION_COMMENT_DIALECT.get(ext, DEFAULT_COMMENT_DIALECT)


def _compute_line_starts(text: str):
    starts = [0]
    for i, ch in enumerate(text):
        if ch == "\n":
            starts.append(i + 1)
    return starts


def _line_number_of(line_starts: list, pos: int) -> int:
    lo = 0
    hi = len(line_starts) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if line_starts[mid] <= pos:
            lo = mid + 1
        else:
            hi = mid - 1
    return hi + 1


def _lua_skip_long_bracket(text: str, open_bracket: int, n: int):
    """
    If text[open_bracket] opens a Lua long bracket ([=*[ ... ]=*]),
    return the index just past the closing delimiter; else None.
    """
    if open_bracket >= n or text[open_bracket] != "[":
        return None
    j = open_bracket + 1
    eq = 0
    while j < n and text[j] == "=":
        eq += 1
        j += 1
    if j >= n or text[j] != "[":
        return None
    body_start = j + 1
    close_delim = "]" + ("=" * eq) + "]"
    cix = text.find(close_delim, body_start)
    if cix < 0:
        return n
    return cix + len(close_delim)


def _lua_skip_quoted_string(text: str, i: int, n: int, quote: str) -> int:
    """Advance past a Lua single- or double-quoted string; i points at the opening quote."""
    if i >= n or text[i] != quote:
        return i
    i += 1
    while i < n:
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == quote:
            return i + 1
        i += 1
    return n


def _comments_with_lines_lua(text: str):
    """
    Lua: -- line comments; long comments --[=*[ ... ]=*] (skip strings first).
    """
    results = []
    line_starts = _compute_line_starts(text)
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == '"':
            i = _lua_skip_quoted_string(text, i, n, '"')
            continue
        if ch == "'":
            i = _lua_skip_quoted_string(text, i, n, "'")
            continue
        if ch == "[":
            end_long = _lua_skip_long_bracket(text, i, n)
            if end_long is not None:
                i = end_long
                continue
        if ch == "-" and i + 1 < n and text[i + 1] == "-":
            start = i
            if i + 2 < n and text[i + 2] == "[":
                ob = i + 2
                end_long = _lua_skip_long_bracket(text, ob, n)
                if end_long is not None:
                    end = end_long
                    line_num = _line_number_of(line_starts, start)
                    results.append(
                        (start, end, line_num, COMMENT_KIND_BLOCK, text[start:end])
                    )
                    i = end
                    continue
            i += 2
            while i < n and text[i] != "\n":
                i += 1
            end = i
            line_num = _line_number_of(line_starts, start)
            results.append(
                (start, end, line_num, COMMENT_KIND_LINE, text[start:end])
            )
            continue
        i += 1
    return results


def _comments_with_lines_cpp(text: str):
    """C/C++: // line comments and /* */ blocks; skip strings and char literals."""
    results = []
    line_starts = _compute_line_starts(text)

    i = 0
    n = len(text)
    in_string = False
    in_char = False
    escape = False

    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""

        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue

        if in_char:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == "'":
                in_char = False
            i += 1
            continue

        if ch == '"':
            in_string = True
            i += 1
            continue
        if ch == "'":
            in_char = True
            i += 1
            continue

        if ch == "/" and nxt == "/":
            start = i
            i += 2
            while i < n and text[i] != "\n":
                i += 1
            end = i
            line_num = _line_number_of(line_starts, start)
            results.append((start, end, line_num, COMMENT_KIND_LINE, text[start:end]))
            continue

        if ch == "/" and nxt == "*":
            start = i
            i += 2
            while i < n - 1 and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            if i < n - 1:
                i += 2
                end = i
            else:
                end = n
                i = n
            line_num = _line_number_of(line_starts, start)
            results.append((start, end, line_num, COMMENT_KIND_BLOCK, text[start:end]))
            continue

        i += 1

    return results


def _comments_with_lines(text: str, dialect: str = "cpp"):
    """
    Return list of (start, end, line_number, kind, comment_text).
    dialect 'cpp': // and /* */; 'lua': -- and long brackets.
    """
    if dialect == "lua":
        return _comments_with_lines_lua(text)
    return _comments_with_lines_cpp(text)


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def run_git(args: list, cwd: str = None) -> bytes:
    result = subprocess.run(
        ["git"] + args,
        capture_output=True,
        cwd=cwd,
    )
    return result.stdout


def git_modified_files(root: str) -> list:
    """Return list of (status_letter, absolute_path) for modified files.
    Uses `git status --porcelain` which outputs: XY path (status in first 2 chars)."""
    raw = run_git(["status", "--porcelain", root])
    files = []
    for line in raw.decode("utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        # git status --porcelain format: "XY path" (3+ chars)
        if len(line) < 4:
            continue
        letter = line[1]  # index status: M/A/D/R, working-tree: ?/M/space
        if letter.strip() and letter not in ("M", "A", "R"):
            continue
        path = line[3:].strip()
        if not path:
            continue
        if not os.path.isabs(path):
            path = os.path.normpath(os.path.join(root, path))
        if path.endswith(SUPPORTED_EXTS):
            files.append((letter, path))
    return files


def git_cat_head(filepath: str, root: str = None) -> bytes:
    """Return file contents at Git HEAD (last committed revision).
    Converts absolute path to repo-relative path for git show."""
    if root is None:
        root = os.getcwd()
    try:
        rel_path = os.path.relpath(filepath, root)
        return run_git(["show", f"HEAD:{rel_path}"], cwd=root)
    except Exception:
        return b""


# ---------------------------------------------------------------------------
# Comment mapping: SimHash + non-crossing bipartite match
# ---------------------------------------------------------------------------

def _fnv1a_64(data: bytes) -> int:
    """FNV-1a 64-bit hash."""
    h = 0xCBF29CE484222325
    for byte in data:
        h ^= byte
        h = (h * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return h


def _simhash(text: str, bits: int = 64) -> int:
    """Compute 64-bit simhash of text: tokenize, FNV-1a hash each token, bit-vote."""
    tokens = re.split(r'[^a-zA-Z0-9\u4e00-\u9fff]+', text)
    tokens = [t for t in tokens if t]
    if not tokens:
        return 0
    acc = [0] * bits
    for token in tokens:
        h = _fnv1a_64(token.encode("utf-8", errors="replace"))
        for b in range(bits):
            if h & (1 << b):
                acc[b] += 1
            else:
                acc[b] -= 1
    result = 0
    for b in range(bits):
        if acc[b] > 0:
            result |= (1 << b)
    return result


def _simhash_distance(h1: int, h2: int) -> int:
    """Hamming distance between two simhash values."""
    return bin(h1 ^ h2).count("1")


def _extract_context_lines(lines: list, comment_line_start: int,
                           comment_line_end: int, N: int = 5,
                           dialect: str = "cpp") -> str:
    """
    Extract N non-empty, non-comment code lines before and after a comment block.
    Returns concatenated context string with whitespace and inline comments stripped.
    """
    def _is_pure_comment_line(line_text: str) -> bool:
        stripped = line_text.strip()
        if dialect == "lua":
            return stripped.startswith("--")
        return (stripped.startswith("//") or stripped.startswith("/*") or
                stripped.startswith("*") or stripped == "*/")

    def _strip_inline_comment(line_text: str) -> str:
        if dialect == "lua":
            idx = line_text.find("--")
            if idx >= 0:
                return line_text[:idx].strip()
            return line_text.strip()
        idx = line_text.find("//")
        if idx >= 0:
            return line_text[:idx].strip()
        return line_text.strip()

    pre_lines = []
    idx = comment_line_start - 1
    while idx >= 0 and len(pre_lines) < N:
        line_text = lines[idx]
        if line_text.strip() and not _is_pure_comment_line(line_text):
            pre_lines.append(_strip_inline_comment(line_text))
        idx -= 1

    after_lines = []
    idx = comment_line_end + 1
    while idx < len(lines) and len(after_lines) < N:
        line_text = lines[idx]
        if line_text.strip() and not _is_pure_comment_line(line_text):
            after_lines.append(_strip_inline_comment(line_text))
        idx += 1

    pre_lines.reverse()
    return "".join(pre_lines + after_lines)


def _non_crossing_match(sim_matrix: list, threshold: float) -> list:
    """
    Maximum-weight non-crossing bipartite matching via DP.

    dp[i][j] = max(dp[i-1][j], dp[i][j-1], dp[i-1][j-1] + sim[i][j])
    Backtrack to recover pairs; only keep matches with similarity >= threshold.
    Returns [(a_idx, b_idx), ...].
    """
    if not sim_matrix:
        return []
    n_ref = len(sim_matrix)
    n_curr = len(sim_matrix[0])
    if n_curr == 0:
        return []

    dp = [[0.0] * (n_curr + 1) for _ in range(n_ref + 1)]
    for i in range(1, n_ref + 1):
        for j in range(1, n_curr + 1):
            dp[i][j] = max(
                dp[i - 1][j],
                dp[i][j - 1],
                dp[i - 1][j - 1] + sim_matrix[i - 1][j - 1],
            )

    matches = []
    i, j = n_ref, n_curr
    while i > 0 and j > 0:
        if abs(dp[i][j] - (dp[i - 1][j - 1] + sim_matrix[i - 1][j - 1])) < 1e-9:
            if sim_matrix[i - 1][j - 1] >= threshold:
                matches.append((i - 1, j - 1))
            i -= 1
            j -= 1
        elif abs(dp[i][j] - dp[i - 1][j]) < 1e-9:
            i -= 1
        else:
            j -= 1

    matches.reverse()
    return matches


SIMHASH_MATCH_THRESHOLD = 0.6


def _first_line_body_and_newline(line_with_possible_nl: str) -> tuple:
    """
    Split a physical line into (body_without_line_ending, line_ending_suffix).
    """
    if not line_with_possible_nl:
        return "", ""
    if line_with_possible_nl.endswith("\r\n"):
        return line_with_possible_nl[:-2], "\r\n"
    if line_with_possible_nl.endswith("\n"):
        return line_with_possible_nl[:-1], "\n"
    if line_with_possible_nl.endswith("\r"):
        return line_with_possible_nl[:-1], "\r"
    return line_with_possible_nl, ""


def _should_replace_first_line_from_reference(first_line: str) -> bool:
    """BOM junk heuristic for C/C++ headers: line should start with # or /."""
    body, _nl = _first_line_body_and_newline(first_line)
    s = body.lstrip("\ufeff \t")
    if not s:
        return False
    return not (s.startswith("#") or s.startswith("/"))


def apply_first_line_from_reference(curr_text: str, ref_text: str,
                                    dialect: str = "cpp") -> tuple:
    """
    C/C++ only: replace the first line from reference when it does not look
    like #... or /... (BOM conversion junk). Lua uses many valid starters
    (local, return, --, ...); skip for dialect 'lua'.
    Returns (new_text, changed).
    """
    if dialect == "lua":
        return curr_text, False
    if not curr_text or not ref_text:
        return curr_text, False
    curr_parts = curr_text.splitlines(True)
    ref_parts = ref_text.splitlines(True)
    if not curr_parts or not ref_parts:
        return curr_text, False
    first_line = curr_parts[0]
    if not _should_replace_first_line_from_reference(first_line):
        return curr_text, False
    ref_body, _ref_nl = _first_line_body_and_newline(ref_parts[0])
    _body, nl = _first_line_body_and_newline(first_line)
    new_first = ref_body + nl
    return new_first + "".join(curr_parts[1:]), True


def count_mapped_comment_mismatches(curr_text: str, comment_maps: list) -> int:
    """How many matched (curr span, ref) pairs have different text."""
    return sum(1 for start, end, ref_c in comment_maps if curr_text[start:end] != ref_c)


def select_mismatch_comment_replacements(curr_text: str, comment_maps: list) -> list:
    """All matched pairs where current comment text != reference."""
    return [
        (start, end, ref_c)
        for start, end, ref_c in comment_maps
        if curr_text[start:end] != ref_c
    ]


def _code_line_before_comment(text: str, comment_pos: int,
                              dialect: str = "cpp") -> str:
    """Code on the same line before the comment token (strip // or -- tail)."""
    line_start = text.rfind("\n", 0, comment_pos) + 1
    prefix = text[line_start:comment_pos]
    if dialect == "lua":
        idx = prefix.find("--")
        if idx >= 0:
            prefix = prefix[:idx]
    else:
        idx = prefix.find("//")
        if idx >= 0:
            prefix = prefix[:idx]
    return prefix.strip()


def build_comment_map(ref_text: str, curr_text: str, verbose: bool = False,
                      dialect: str = "cpp") -> list:
    """
    Map each comment span in curr_text to the corresponding reference comment.

    Phase 1: match by identical code line prefix before the comment.
    Phase 2: SimHash context match for unmatched comments.
    Global pairing via DP non-crossing matching.
    """
    ref_comments = _comments_with_lines(ref_text, dialect)
    curr_comments = _comments_with_lines(curr_text, dialect)

    if not ref_comments or not curr_comments:
        return []

    ref_lines = ref_text.splitlines()
    curr_lines = curr_text.splitlines()

    line_starts_ref = _compute_line_starts(ref_text)
    line_starts_curr = _compute_line_starts(curr_text)

    def _pos_to_line_0(line_starts, pos):
        return _line_number_of(line_starts, pos) - 1

    # Phase 1: Code prefix matching
    ref_prefixes = [_code_line_before_comment(ref_text, rs, dialect)
                    for rs, _re, _rl, _rk, _rt in ref_comments]
    curr_prefixes = [_code_line_before_comment(curr_text, cs, dialect)
                     for cs, _ce, _cl, _ck, _ct in curr_comments]

    n_ref = len(ref_comments)
    n_curr = len(curr_comments)
    ref_matched = [False] * n_ref
    curr_matched = [False] * n_curr
    mappings = []
    debug_prefix = []

    for i in range(n_ref):
        rs_i, re_i, rl_i, rk_i, rt_i = ref_comments[i]
        rp = ref_prefixes[i]
        if not rp:
            continue  # Empty prefix (e.g., comment at file start) - ambiguous
        best_j = -1
        for j in range(n_curr):
            if curr_matched[j]:
                continue
            if ref_comments[i][3] != curr_comments[j][3]:
                continue
            if curr_prefixes[j] == rp:
                if best_j < 0:
                    best_j = j
                else:
                    # Multiple candidates with same prefix - keep first
                    pass
        if best_j >= 0:
            cs, ce = curr_comments[best_j][0], curr_comments[best_j][1]
            mappings.append((cs, ce, rt_i))
            ref_matched[i] = True
            curr_matched[best_j] = True
            debug_prefix.append((curr_comments[best_j][2], rl_i))

    # Phase 2: SimHash matching for remaining unmatched comments
    ref_hashes = []
    for rs, re_, _rline, _rkind, _rtext in ref_comments:
        rline_start = _pos_to_line_0(line_starts_ref, rs)
        rline_end = _pos_to_line_0(line_starts_ref, re_)
        ctx = _extract_context_lines(ref_lines, rline_start, rline_end, N=5,
                                      dialect=dialect)
        ref_hashes.append(_simhash(ctx))

    curr_hashes = []
    for cs, ce, _cline, _ckind, _ctext in curr_comments:
        cline_start = _pos_to_line_0(line_starts_curr, cs)
        cline_end = _pos_to_line_0(line_starts_curr, ce)
        ctx = _extract_context_lines(curr_lines, cline_start, cline_end, N=5,
                                      dialect=dialect)
        curr_hashes.append(_simhash(ctx))

    # Build similarity matrix only for unmatched comments
    unmatched_ref_idx = [i for i in range(n_ref) if not ref_matched[i]]
    unmatched_curr_idx = [j for j in range(n_curr) if not curr_matched[j]]

    simhash_matches = []
    if unmatched_ref_idx and unmatched_curr_idx:
        sim_matrix = []
        for i in unmatched_ref_idx:
            row = []
            for j in unmatched_curr_idx:
                dist = _simhash_distance(ref_hashes[i], curr_hashes[j])
                similarity = 1.0 - dist / 64.0
                if ref_comments[i][3] != curr_comments[j][3]:
                    similarity *= 0.5
                row.append(similarity)
            sim_matrix.append(row)

        raw_matches = _non_crossing_match(
            sim_matrix, threshold=SIMHASH_MATCH_THRESHOLD)
        for ri, ci in raw_matches:
            a_idx = unmatched_ref_idx[ri]
            b_idx = unmatched_curr_idx[ci]
            cs, ce = curr_comments[b_idx][0], curr_comments[b_idx][1]
            rtext = ref_comments[a_idx][4]
            mappings.append((cs, ce, rtext))
            simhash_matches.append((a_idx, b_idx))

    # Sort mappings by position for consistent output
    mappings.sort(key=lambda x: x[0])

    if verbose:
        if debug_prefix:
            print(f"  [DEBUG] Prefix matched {len(debug_prefix)} comment pairs")
            for cline, rline in debug_prefix:
                print(f"    - curr L{cline:>4} -> ref L{rline:<4} (prefix)")
        if simhash_matches:
            print(
                "  [DEBUG] SimHash matched "
                f"{len(simhash_matches)} comment pairs "
                f"(threshold={SIMHASH_MATCH_THRESHOLD})"
            )
            for a_idx, b_idx in simhash_matches:
                rs, re_, rline, rkind, _rt = ref_comments[a_idx]
                cs, ce, cline, ckind, _ct = curr_comments[b_idx]
                dist = _simhash_distance(ref_hashes[a_idx], curr_hashes[b_idx])
                sim = 1.0 - dist / 64.0
                print(
                    f"    - curr L{cline:>4} ({ckind}) -> ref L{rline:<4} ({rkind}) "
                    f"sim={sim:.2f} hamming={dist}"
                )

    return mappings


def fix_comments(new_text: str, comment_maps: list) -> str:
    """Replace comment spans in new_text with reference text; reverse order by offset."""
    if not comment_maps:
        return new_text
    result = new_text
    for start, end, old_comment in sorted(comment_maps, key=lambda x: x[0], reverse=True):
        result = result[:start] + old_comment + result[end:]
    return result


def filter_comment_maps_for_fix(curr_text: str, comment_maps: list) -> list:
    """
    After prefix/SimHash matching, count pairs where comment text differs.
    Only if that count is *greater than* COMMENT_MISMATCH_TRIGGER_COUNT do we
    apply replacements (all differing matched pairs). This avoids guessing
    mojibake and limits comment restores to bulk-corruption cases.
    """
    mismatches = select_mismatch_comment_replacements(curr_text, comment_maps)
    if len(mismatches) <= COMMENT_MISMATCH_TRIGGER_COUNT:
        return []
    return mismatches


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def find_target_files(path: str) -> list:
    """If path is a directory, recursively collect supported extensions."""
    if os.path.isfile(path):
        if path.endswith(SUPPORTED_EXTS):
            return [path]
        return []
    files = []
    for dirpath, _dirnames, filenames in os.walk(path):
        for fn in filenames:
            if fn.endswith(SUPPORTED_EXTS):
                files.append(os.path.join(dirpath, fn))
    return files


def get_reference_raw(filepath: str, backup_path: str = None) -> bytes:
    """Load reference bytes: single backup file, or file under backup dir by basename."""
    if backup_path:
        if os.path.isfile(backup_path):
            # One backup file shared as reference for all targets
            with open(backup_path, "rb") as f:
                return f.read()
        # Backup directory: match by filename only (no stable root mapping)
        candidates = [
            os.path.join(backup_path, os.path.basename(filepath)),
        ]
        for c in candidates:
            if os.path.isfile(c):
                with open(c, "rb") as f:
                    return f.read()
        print(f"  [WARN] Backup not found for {os.path.basename(filepath)}, tried: {candidates}")
        return b""
    else:
        return git_cat_head(filepath, root)


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def process_file(filepath: str, root: str, backup_path: str = None,
                 dry_run: bool = False, verbose: bool = False):
    """
    Re-encode to match reference when needed; restore comments using mapped diff
    counts and first-line garbage fix (see apply_first_line_from_reference).
    """
    dialect = file_comment_dialect(filepath)
    rel = os.path.relpath(filepath, root)
    print(f"\n--- Processing: {rel} ---")

    with open(filepath, "rb") as f:
        current_raw = f.read()

    ref_raw = get_reference_raw(filepath, backup_path)
    if not ref_raw:
        print(f"  [SKIP] Cannot retrieve reference for {rel}")
        return

    curr_enc = detect_encoding(current_raw)
    ref_enc = detect_encoding(ref_raw)

    ref_label = "Backup" if backup_path else "Git"
    print(f"  {ref_label} encoding: {ref_enc}")
    print(f"  File encoding: {curr_enc}")

    curr_text = decode_bytes(current_raw, curr_enc)

    # Normalize ref newlines to CRLF if the working file uses CRLF
    ref_text_raw = decode_bytes(ref_raw, ref_enc)
    if "\r\n" in curr_text and "\r\n" not in ref_text_raw:
        ref_text = ref_text_raw.replace("\n", "\r\n")
    else:
        ref_text = ref_text_raw

    # --- Step 1: Fix encoding ---
    if curr_enc != ref_enc:
        print(f"  [INFO] Encoding mismatch: {curr_enc} -> {ref_enc}")
        if dry_run:
            print(f"  [DRY-RUN] Would re-encode {curr_enc} -> {ref_enc}.")
            return
        # Re-encode: strip U+FFFD to avoid GBK encoder crash, then round-trip
        # through ref encoding so comment comparison runs on consistent encoding.
        re_encoded = curr_text.replace("\ufffd", "")
        curr_bytes = _encode_text_robust(re_encoded, ref_enc)
        curr_text = decode_bytes(curr_bytes, ref_enc)
        curr_enc = ref_enc
        print(f"  [FIXED] Re-encoded to {ref_enc} (removed U+FFFD if any).")
    else:
        print("  [INFO] Encoding matches reference.")

    curr_text, first_line_fixed = apply_first_line_from_reference(
        curr_text, ref_text, dialect)
    if first_line_fixed:
        print("  [FIXED] Replaced malformed first line from reference (# or / expected).")

    # --- Step 2: Fix comments ---
    comment_maps = build_comment_map(
        ref_text, curr_text, verbose=verbose, dialect=dialect)
    mismatch_n = count_mapped_comment_mismatches(curr_text, comment_maps)
    filtered_maps = filter_comment_maps_for_fix(curr_text, comment_maps)

    if mismatch_n <= COMMENT_MISMATCH_TRIGGER_COUNT:
        if mismatch_n > 0:
            print(
                f"  [INFO] Matched comments with text diffs: {mismatch_n} "
                f"(<= {COMMENT_MISMATCH_TRIGGER_COUNT}, skip comment restore)."
            )
        else:
            print("  [OK] All mapped comments match reference.")

    if filtered_maps:
        print(f"  [INFO] Bulk comment diffs ({mismatch_n} > "
              f"{COMMENT_MISMATCH_TRIGGER_COUNT}); fixing {len(filtered_maps)} comments.")
        curr_text = fix_comments(curr_text, filtered_maps)
        print(f"  [FIXED] Replaced {len(filtered_maps)} comments.")
    elif mismatch_n > COMMENT_MISMATCH_TRIGGER_COUNT:
        print(f"  [WARN] Mismatch count {mismatch_n} but no replacement spans (unexpected).")

    if dry_run:
        print("  [DRY-RUN] Would write changes.")
        return

    target_enc = ref_enc if curr_enc != ref_enc else curr_enc
    fixed_bytes = _encode_text_robust(curr_text, target_enc)
    with open(filepath, "wb") as f:
        f.write(fixed_bytes)
    if curr_enc != ref_enc:
        print(f"  [FIXED] Re-encoded from {curr_enc} to {ref_enc}.")


def main():
    parser = argparse.ArgumentParser(
        description="Fix encoding and comments of C/C++ and Lua source files."
    )
    parser.add_argument("path", nargs="?",
                        help="File or directory to process. "
                             "No-backup mode: only modified files (git status). "
                             "Backup mode: recursive scan.")
    parser.add_argument("--backup", "-b", metavar="PATH",
                        help="Backup file/directory to use as reference instead of Git HEAD. "
                             "Each target file is matched by relative path or filename.")
    parser.add_argument("--dry-run", "-n", action="store_true",
                        help="Only report, don't write.")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Verbose output.")
    parser.add_argument("--self-check", action="store_true",
                        help="Run in-memory mapping smoke tests and exit.")
    args = parser.parse_args()

    if args.self_check:
        test_file = os.path.join(os.path.dirname(__file__), "test", "test_fix_encoding.py")
        if not os.path.isfile(test_file):
            print(f"Error: test file not found: {test_file}", file=sys.stderr)
            sys.exit(1)
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        sys.exit(subprocess.run([sys.executable, test_file], env=env).returncode)

    if not args.path:
        parser.error("path is required unless --self-check is used")

    target = os.path.abspath(args.path)
    if not os.path.exists(target):
        print(f"Error: {target} does not exist.", file=sys.stderr)
        sys.exit(1)

    backup_path = None
    if args.backup:
        backup_path = os.path.abspath(args.backup)
        if not os.path.exists(backup_path):
            print(f"Error: backup {backup_path} does not exist.", file=sys.stderr)
            sys.exit(1)

    if os.path.isfile(target):
        files = [target]
        root = os.path.dirname(target)
    elif backup_path:
        files = find_target_files(target)
        root = target
    else:
        files = [p for _status, p in git_modified_files(target)]
        root = target

    if not files:
        print("No matching source files found.")
        return

    mode = "backup" if backup_path else "Git"
    print(f"Found {len(files)} source file(s), mode={mode}")

    if args.dry_run:
        print("(DRY-RUN mode -- no files will be modified)\n")

    for filepath in files:
        try:
            process_file(filepath, root, backup_path=backup_path,
                         dry_run=args.dry_run, verbose=args.verbose)
        except Exception as e:
            print(f"  [ERROR] {filepath}: {e}", file=sys.stderr)

    print("\nDone.")


if __name__ == "__main__":
    main()
