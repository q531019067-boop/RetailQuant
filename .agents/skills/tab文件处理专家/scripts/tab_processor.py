# -*- coding: utf-8 -*-
import os
import tempfile
import shutil
from typing import List, Dict, Any, Optional, Tuple, Union
from collections import Counter
import re
import json
import sys
import io


class TabTable:
    """
    GBK encoded tab file processor
    """

    def __init__(self, filepath: str):
        self.filepath = filepath
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"文件不存在: {filepath}")
        self.column_names: List[str] = []
        self.row_offsets: List[int] = []
        self.total_rows: int = 0
        self.column_types: Dict[str, str] = {}
        self._scan_file()

    def _scan_file(self):
        """Scan file to get column names, row offsets and column types"""
        with open(self.filepath, "rb") as f:
            # Read first line as column names
            first_line = f.readline()
            if not first_line:
                self.column_names = []
                return
            line_str = first_line.decode("gbk", errors="replace").rstrip("\r\n")
            self.column_names = line_str.split("\t") if line_str else []

            # Record row offsets
            while True:
                pos = f.tell()
                line = f.readline()
                if not line:
                    break
                self.row_offsets.append(pos)
            self.total_rows = len(self.row_offsets)

        # Infer column types from first 100 rows
        if self.total_rows > 0:
            sample_size = min(100, self.total_rows)
            sample_rows = [self._read_row_by_offset(self.row_offsets[i]) for i in range(sample_size)]
            self._infer_column_types(sample_rows)
        else:
            for col in self.column_names:
                self.column_types[col] = "string"

    def _infer_column_types(self, rows: List[Dict[str, str]]):
        """Infer column types from sample rows"""
        self.column_types = {col: "string" for col in self.column_names}
        if not rows:
            return

        for col in self.column_names:
            is_int = True
            is_float = True
            for row in rows:
                val = row.get(col, "")
                if val == "":
                    continue
                try:
                    int(val)
                except ValueError:
                    is_int = False
                try:
                    float(val)
                except ValueError:
                    is_float = False
                if not is_int and not is_float:
                    break
            if is_int:
                self.column_types[col] = "int"
            elif is_float:
                self.column_types[col] = "float"
            else:
                self.column_types[col] = "string"

    def _read_row_by_offset(self, offset: int) -> Dict[str, str]:
        """Read a row by byte offset"""
        with open(self.filepath, "rb") as f:
            f.seek(offset)
            line = f.readline()
        line_str = line.decode("gbk", errors="replace").rstrip("\r\n")
        parts = line_str.split("\t") if line_str else []
        if len(parts) < len(self.column_names):
            parts += [""] * (len(self.column_names) - len(parts))
        return dict(zip(self.column_names, parts))

    def _read_rows(self, start: int, limit: int) -> List[Dict[str, str]]:
        if start >= self.total_rows:
            return []
        end = min(start + limit, self.total_rows)
        rows = []
        for idx in range(start, end):
            rows.append(self._read_row_by_offset(self.row_offsets[idx]))
        return rows

    def _check_condition(self, row: Dict[str, str], condition: Dict[str, Any]) -> bool:
        """Check if a row meets a search condition"""
        keyword = condition.get("keyword", "")
        columns = condition.get("columns", self.column_names)
        is_regex = condition.get("is_regex", False)
        whole_word = condition.get("whole_word", False)
        case_sensitive = condition.get("case_sensitive", False)

        if not columns:
            columns = self.column_names

        if is_regex:
            try:
                flags = 0 if case_sensitive else re.IGNORECASE
                pattern = re.compile(keyword, flags)
            except re.error as e:
                raise ValueError(f"无效的正则表达式: {e}")
        elif whole_word:
            flags = 0 if case_sensitive else re.IGNORECASE
            pattern = re.compile(r"\b" + re.escape(keyword) + r"\b", flags)
        else:
            if case_sensitive:
                pattern = None
            else:
                keyword = keyword.lower()
                pattern = None

        for col in columns:
            if col not in self.column_names:
                continue
            val = str(row.get(col, ""))

            if is_regex or whole_word:
                if pattern.search(val):
                    return True
            else:
                if case_sensitive:
                    if keyword in val:
                        return True
                else:
                    if keyword in val.lower():
                        return True

        return False

    def search(
        self,
        keyword: str = None,
        columns: Optional[List[str]] = None,
        limit: int = 100,
        start_index: int = 0,
        return_columns: Optional[List[str]] = None,
        is_regex: bool = False,
        whole_word: bool = False,
        case_sensitive: bool = False,
        conditions: Optional[List[Dict[str, Any]]] = None,
        logic: str = "and",
        count_only: bool = False,
    ) -> Tuple[List[Dict[str, str]], List[int], int]:
        """Advanced search with regex, whole word, case sensitive, and multi-condition support"""
        matches = []
        lines = []
        total = 0

        if not conditions:
            if keyword is not None:
                conditions = [
                    {
                        "keyword": keyword,
                        "columns": columns,
                        "is_regex": is_regex,
                        "whole_word": whole_word,
                        "case_sensitive": case_sensitive,
                    }
                ]
            else:
                raise ValueError("必须提供keyword或conditions参数")

        for idx, offset in enumerate(self.row_offsets):
            row = self._read_row_by_offset(offset)

            if logic == "and":
                matched = all(self._check_condition(row, cond) for cond in conditions)
            else:
                matched = any(self._check_condition(row, cond) for cond in conditions)

            if matched:
                total += 1
                if not count_only and total > start_index and len(matches) < limit:
                    if return_columns is not None:
                        filtered_row = {}
                        for col in return_columns:
                            if col in row:
                                filtered_row[col] = row[col]
                        matches.append(filtered_row)
                    else:
                        matches.append(row)
                    lines.append(idx)

        return matches, lines, total

    def _rewrite_file(self, line_processor):
        temp_fd, temp_path = tempfile.mkstemp(dir=os.path.dirname(self.filepath))
        try:
            with os.fdopen(temp_fd, "wb") as out_f:
                out_f.write(("\t".join(self.column_names) + "\n").encode("gbk", errors="replace"))
                for idx, offset in enumerate(self.row_offsets):
                    with open(self.filepath, "rb") as in_f:
                        in_f.seek(offset)
                        line = in_f.readline().decode("gbk", errors="replace").rstrip("\r\n")
                    new_line = line_processor(idx, line)
                    if new_line is not None:
                        out_f.write((new_line + "\n").encode("gbk", errors="replace"))
            shutil.move(temp_path, self.filepath)
        except Exception as e:
            os.unlink(temp_path)
            raise e
        self._scan_file()

    def add_row(self, values: List[Union[str, int, float]]):
        if len(values) != len(self.column_names):
            raise ValueError(f"值的数量({len(values)})与列数({len(self.column_names)})不匹配")
        str_values = [str(v) for v in values]
        line = "\t".join(str_values)
        with open(self.filepath, "ab") as f:
            f.write((line + "\n").encode("gbk", errors="replace"))
        self._scan_file()

    def insert_row(self, index: int, values: List[Union[str, int, float]]):
        if index < 0 or index > self.total_rows:
            raise IndexError(f"行索引{index}超出范围[0, {self.total_rows}]")
        if len(values) != len(self.column_names):
            raise ValueError(f"值的数量({len(values)})与列数({len(self.column_names)})不匹配")
        str_values = [str(v) for v in values]
        new_line = "\t".join(str_values)

        def processor(idx, line):
            if idx == index:
                return new_line
            return line

        self._rewrite_file(processor)

    def update_row(self, index: int, values: Union[List, Dict]):
        if index < 0 or index >= self.total_rows:
            raise IndexError(f"行索引{index}超出范围[0, {self.total_rows - 1}]")
        current = self._read_row_by_offset(self.row_offsets[index])
        if isinstance(values, list):
            if len(values) != len(self.column_names):
                raise ValueError(f"列表长度({len(values)})与列数({len(self.column_names)})不匹配")
            new_row = dict(zip(self.column_names, [str(v) for v in values]))
        else:
            new_row = current.copy()
            for col, val in values.items():
                if col not in self.column_names:
                    raise ValueError(f"列'{col}'不存在")
                new_row[col] = str(val)
        new_line = "\t".join([new_row[col] for col in self.column_names])

        def processor(idx, line):
            if idx == index:
                return new_line
            return line

        self._rewrite_file(processor)

    def delete_row(self, index: int):
        if index < 0 or index >= self.total_rows:
            raise IndexError(f"行索引{index}超出范围[0, {self.total_rows - 1}]")

        def processor(idx, line):
            if idx == index:
                return None
            return line

        self._rewrite_file(processor)

    def add_column(self, name: str, default_value: Union[str, int, float] = "", position: Optional[int] = None):
        if name in self.column_names:
            raise ValueError(f"列'{name}'已存在")
        if position is None:
            position = len(self.column_names)
        else:
            if position < 0 or position > len(self.column_names):
                raise IndexError(f"列位置{position}超出范围[0, {len(self.column_names)}]")
        default_str = str(default_value)
        new_columns = self.column_names[:]
        new_columns.insert(position, name)
        self.column_names = new_columns

        def processor(idx, line):
            parts = line.split("\t") if line else []
            if len(parts) < len(self.column_names) - 1:
                parts += [""] * (len(self.column_names) - 1 - len(parts))
            parts.insert(position, default_str)
            return "\t".join(parts)

        self._rewrite_file(processor)

    def delete_column(self, name: str):
        if name not in self.column_names:
            raise ValueError(f"列'{name}'不存在")
        col_index = self.column_names.index(name)
        new_columns = [c for c in self.column_names if c != name]
        self.column_names = new_columns

        def processor(idx, line):
            parts = line.split("\t") if line else []
            if len(parts) < len(self.column_names) + 1:
                parts += [""] * (len(self.column_names) + 1 - len(parts))
            del parts[col_index]
            return "\t".join(parts)

        self._rewrite_file(processor)

    def rename_column(self, old: str, new: str):
        if old not in self.column_names:
            raise ValueError(f"列'{old}'不存在")
        if new in self.column_names and new != old:
            raise ValueError(f"列'{new}'已存在")
        idx = self.column_names.index(old)
        self.column_names[idx] = new
        with open(self.filepath, "r+b") as f:
            first_line = f.readline()
            new_header = "\t".join(self.column_names) + "\n"
            f.seek(0)
            f.write(new_header.encode("gbk", errors="replace"))
            rest = f.read()
            f.write(rest)
        self._scan_file()

    def filter_rows(
        self, row_indices: List[int], column_names: List[str], start_index: int = 0, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Filter rows by indices and column names"""
        valid_columns = [col for col in column_names if col in self.column_names]
        rows = []
        count = 0
        for idx in row_indices:
            if idx < 0 or idx >= self.total_rows:
                continue
            if count >= start_index and len(rows) < limit:
                offset = self.row_offsets[idx]
                row = self._read_row_by_offset(offset)
                filtered = {}
                for col in valid_columns:
                    filtered[col] = row.get(col, "")
                filtered["_row_index"] = idx
                rows.append(filtered)
            count += 1
        return rows

    def get_row_columns(
        self,
        row_index: int,
        column_names: Optional[List[str]] = None,
        column_conditions: Optional[List[Dict[str, Any]]] = None,
        logic: str = "or",
        column_ranges: Optional[List[Dict[str, int]]] = None,
        column_indices: Optional[List[int]] = None,
        start_index: int = 0,
        limit: int = 50,
        skip_empty: bool = False,
        empty_values: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Get columns of a specific row with various filtering options"""
        if row_index < 0 or row_index >= self.total_rows:
            raise IndexError(f"行索引{row_index}超出范围[0, {self.total_rows - 1}]")

        row = self._read_row_by_offset(self.row_offsets[row_index])

        selected_columns = []

        if column_names:
            selected_columns = [col for col in column_names if col in self.column_names]
        elif column_conditions:
            for col in self.column_names:
                if self._check_column_condition(col, column_conditions, logic):
                    selected_columns.append(col)
        elif column_ranges:
            for range_def in column_ranges:
                start = range_def.get("start", 0)
                end = range_def.get("end", len(self.column_names))
                for i in range(start, min(end, len(self.column_names))):
                    if i not in [self.column_names.index(col) for col in selected_columns]:
                        selected_columns.append(self.column_names[i])
        elif column_indices:
            for i in column_indices:
                if 0 <= i < len(self.column_names):
                    selected_columns.append(self.column_names[i])
        else:
            selected_columns = self.column_names

        if skip_empty:
            if empty_values is None:
                empty_values = ["", "0", "NULL", "null", "None"]
            filtered_columns = []
            for col in selected_columns:
                val = row.get(col, "")
                if val not in empty_values:
                    filtered_columns.append(col)
            selected_columns = filtered_columns

        total_selected = len(selected_columns)
        end_index = min(start_index + limit, total_selected)
        paginated_columns = selected_columns[start_index:end_index]

        columns_data = []
        for col in paginated_columns:
            columns_data.append(
                {"column_name": col, "column_index": self.column_names.index(col), "value": row.get(col, "")}
            )

        return {
            "row_index": row_index,
            "columns": columns_data,
            "total_selected": total_selected,
            "returned": len(columns_data),
            "start_index": start_index,
            "end_index": end_index,
            "has_more": end_index < total_selected,
        }

    def _check_column_condition(self, column_name: str, conditions: List[Dict[str, Any]], logic: str) -> bool:
        """Check if column name meets conditions"""
        if logic == "and":
            for cond in conditions:
                if not self._match_column_name(column_name, cond):
                    return False
            return True
        else:
            for cond in conditions:
                if self._match_column_name(column_name, cond):
                    return True
            return False

    def _match_column_name(self, column_name: str, condition: Dict[str, Any]) -> bool:
        """Match column name against a condition"""
        pattern = condition.get("pattern", "")
        is_regex = condition.get("is_regex", False)
        whole_word = condition.get("whole_word", False)
        case_sensitive = condition.get("case_sensitive", False)
        use_wildcard = condition.get("use_wildcard", False)

        if use_wildcard:
            import fnmatch

            if case_sensitive:
                return fnmatch.fnmatch(column_name, pattern)
            else:
                return fnmatch.fnmatch(column_name.lower(), pattern.lower())
        elif is_regex:
            try:
                flags = 0 if case_sensitive else re.IGNORECASE
                regex = re.compile(pattern, flags)
                return bool(regex.search(column_name))
            except re.error:
                return False
        elif whole_word:
            if case_sensitive:
                return column_name == pattern
            else:
                return column_name.lower() == pattern.lower()
        else:
            if case_sensitive:
                return pattern in column_name
            else:
                return pattern.lower() in column_name.lower()


# 列数不少于该阈值且未指定 return_columns 时，search 默认只返回「常用列 + 参与搜索的列」
WIDE_TABLE_MIN_COLUMNS = 40
# 自动瘦身时按顺序追加的常用列（表中存在的才会加入）
PREFERRED_SLIM_COLUMNS = [
    "ID",
    "Name",
    "Title",
    "DisplayName",
    "Model",
    "Kind",
    "Level",
    "MapName",
]


def _env_bool(key: str, default: bool) -> bool:
    v = os.environ.get(key)
    if v is None or not str(v).strip():
        return default
    return str(v).strip().lower() not in ("0", "false", "no", "off")


def _env_int_clamped(key: str, default: int, lo: int, hi: int) -> int:
    raw = os.environ.get(key, "").strip()
    if not raw:
        return default
    try:
        n = int(raw, 10)
    except ValueError:
        return default
    return max(lo, min(hi, n))


def _env_csv_columns(key: str, default: List[str]) -> List[str]:
    raw = os.environ.get(key, "").strip()
    if not raw:
        return list(default)
    return [x.strip() for x in raw.split(",") if x.strip()]


def search_auto_slim_env() -> Tuple[bool, int, List[str], int]:
    """(是否启用, 宽表列数阈值, 优先列名, 无命中时的前若干列回退)。"""
    enabled = _env_bool("TAB_PROCESSOR_AUTO_SLIM", True)
    threshold = _env_int_clamped(
        "TAB_PROCESSOR_WIDE_MIN_COLUMNS",
        WIDE_TABLE_MIN_COLUMNS,
        1,
        50000,
    )
    preferred = _env_csv_columns("TAB_PROCESSOR_SLIM_COLUMNS", PREFERRED_SLIM_COLUMNS)
    fallback = _env_int_clamped("TAB_PROCESSOR_SLIM_FALLBACK", 12, 1, 500)
    return enabled, threshold, preferred, fallback


def _collect_columns_from_search_conditions(conditions: Optional[List[Dict[str, Any]]]) -> List[str]:
    if not conditions:
        return []
    out: List[str] = []
    for cond in conditions:
        cols = cond.get("columns")
        if not cols:
            continue
        for c in cols:
            if c and c not in out:
                out.append(c)
    return out


def auto_slim_return_columns(
    table: TabTable,
    conditions: Optional[List[Dict[str, Any]]],
    explicit_search_columns: Optional[List[str]],
    preferred_columns: List[str],
    fallback_max: int,
) -> List[str]:
    """为超宽表生成默认返回列：常用标识列优先，再合并参与搜索的列。"""
    names: List[str] = []
    cn = table.column_names

    def extend(cols: Optional[List[str]]) -> None:
        for c in cols or []:
            if c in cn and c not in names:
                names.append(c)

    extend(preferred_columns)
    extend(_collect_columns_from_search_conditions(conditions))
    extend(explicit_search_columns)
    return names if names else cn[:fallback_max]


def format_search_rows_tsv(rows: List[Dict[str, str]]) -> str:
    if not rows:
        return ""
    cols = list(rows[0].keys())
    lines = ["\t".join(cols)]
    for row in rows:
        lines.append(
            "\t".join(str(row.get(c, "")).replace("\t", " ").replace("\r", " ").replace("\n", " ") for c in cols)
        )
    return "\n".join(lines) + "\n"


def format_search_rows_markdown(rows: List[Dict[str, str]]) -> str:
    if not rows:
        return ""
    cols = list(rows[0].keys())

    def esc(s: str) -> str:
        return str(s).replace("|", "\\|").replace("\n", " ").replace("\r", "")

    header = "| " + " | ".join(esc(c) for c in cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    body = ["| " + " | ".join(esc(row.get(c, "")) for c in cols) + " |" for row in rows]
    return "\n".join([header, sep] + body) + "\n"


MAX_OUTPUT_CHARS = 1024
CUT_COLUMNS_COUNT = 5

from truncate_response import truncate_response


def process_request(request):
    """Process tab file operation request"""
    try:
        action = request.get("action")
        filepath = request.get("filepath")

        if not action or not filepath:
            return {"success": False, "error": "缺少必要参数: action和filepath"}

        table = TabTable(filepath)

        if action == "get_table_info":
            preview_rows = table._read_rows(0, 5)
            preview_columns = table.column_names[:5]
            column_truncated = len(table.column_names) > 5

            filtered_preview = []
            for row in preview_rows:
                filtered_row = {}
                for col in preview_columns:
                    filtered_row[col] = row.get(col, "")
                filtered_preview.append(filtered_row)

            result = {
                "filename": os.path.basename(filepath),
                "columns": table.column_names,
                "total_rows": table.total_rows,
                "total_columns": len(table.column_names),
                "column_types": table.column_types,
                "preview": {
                    "rows": filtered_preview,
                    "row_count": len(filtered_preview),
                    "column_count": len(preview_columns),
                    "row_truncated": table.total_rows > 5,
                    "column_truncated": column_truncated,
                    "note": f"预览显示前{min(5, table.total_rows)}行和前{len(preview_columns)}列"
                    + ("，行数据已截断" if table.total_rows > 5 else "")
                    + ("，列数据已截断" if column_truncated else ""),
                },
            }

        elif action == "search":
            keyword = request.get("keyword")
            columns = request.get("columns")
            limit = request.get("limit", 100)
            start_index = request.get("start_index", 0)
            user_return_columns = request.get("return_columns")
            if isinstance(user_return_columns, str):
                user_return_columns = [s.strip() for s in user_return_columns.split(",") if s.strip()]
                if not user_return_columns:
                    user_return_columns = None
            is_regex = request.get("is_regex", False)
            whole_word = request.get("whole_word", False)
            case_sensitive = request.get("case_sensitive", False)
            conditions = request.get("conditions")
            logic = request.get("logic", "and")
            count_only = request.get("count_only", False)
            full_rows = request.get("full_rows", False)
            if isinstance(full_rows, str):
                full_rows = full_rows.strip().lower() in ("true", "1", "yes")

            cond_for_slim = conditions
            if not cond_for_slim and keyword is not None:
                cond_for_slim = [
                    {
                        "keyword": keyword,
                        "columns": columns,
                        "is_regex": is_regex,
                        "whole_word": whole_word,
                        "case_sensitive": case_sensitive,
                    }
                ]

            slim_on, slim_threshold, slim_preferred, slim_fallback = search_auto_slim_env()
            effective_return_columns = user_return_columns
            auto_slimmed = False
            if (
                slim_on
                and not count_only
                and not full_rows
                and user_return_columns is None
                and len(table.column_names) >= slim_threshold
            ):
                effective_return_columns = auto_slim_return_columns(
                    table,
                    cond_for_slim,
                    columns,
                    slim_preferred,
                    slim_fallback,
                )
                auto_slimmed = True

            matches, lines, total = table.search(
                keyword,
                columns,
                limit,
                start_index,
                effective_return_columns,
                is_regex,
                whole_word,
                case_sensitive,
                conditions,
                logic,
                count_only,
            )

            if count_only:
                result = {"total_matches": total, "count_only": True}
            else:
                end_index = start_index + len(matches)
                result = {
                    "total_matches": total,
                    "rows": matches,
                    "lines": lines,
                    "truncated": total > start_index + limit,
                    "start_index": start_index,
                    "end_index": end_index,
                    "next_start_index": end_index if end_index < total else None,
                    "has_more": end_index < total,
                }
                if auto_slimmed and matches and effective_return_columns is not None:
                    result["auto_slimmed_columns"] = True
                    result["returned_column_names"] = list(effective_return_columns)

                # 添加智能提示
                hints = []

                # 提示1：搜索数字时，如果没有使用全字匹配，给出建议
                if keyword and not whole_word and not is_regex:
                    try:
                        int(keyword)
                        hints.append(
                            {
                                "type": "search_precision",
                                "message": f"搜索关键词 '{keyword}' 是数字，建议使用 --whole_word true 进行精确匹配，避免匹配到包含该数字的值（如 '{keyword}00'）",
                                "suggestion": "添加参数 --whole_word true",
                            }
                        )
                    except ValueError:
                        pass

                # 提示2：当搜索结果很多时，建议使用 count_only
                if total > 100 and not count_only:
                    hints.append(
                        {
                            "type": "large_result",
                            "message": f"搜索结果较多（{total}条），建议先使用 --count_only true 了解总数，再使用分页获取数据",
                            "suggestion": "添加参数 --count_only true 或使用 --limit 和 --start_index 分页",
                        }
                    )

                # 提示3：当输出被截断时，提供更清晰的分页建议
                if result["truncated"]:
                    hints.append(
                        {
                            "type": "truncated_output",
                            "message": f"输出已截断，当前显示 {len(matches)} 条，共 {total} 条",
                            "suggestion": f"使用 --start_index {end_index} 获取下一页，或使用 --return_columns 减少返回的列",
                        }
                    )

                # 提示4：窄表未自动瘦身时，建议显式 return_columns
                if not user_return_columns and not auto_slimmed and len(matches) > 0 and len(table.column_names) > 10:
                    hints.append(
                        {
                            "type": "column_optimization",
                            "message": f"表格有 {len(table.column_names)} 列，建议只返回需要的列以提高效率",
                            "suggestion": f"使用 --return_columns 指定列名，如：--return_columns {','.join(table.column_names[:3])}",
                        }
                    )

                if auto_slimmed and len(matches) > 0:
                    hints.append(
                        {
                            "type": "auto_slimmed_columns",
                            "message": (
                                f"表格共 {len(table.column_names)} 列（≥{slim_threshold} 触发瘦身），已自动仅返回 "
                                f"{len(effective_return_columns or [])} 列"
                                f"（{','.join((effective_return_columns or [])[:8])}"
                                f"{'…' if len(effective_return_columns or []) > 8 else ''}）"
                            ),
                            "suggestion": (
                                "需要整行用 --full_rows true，或 --return_columns；"
                                "阈值/列清单可用环境变量 TAB_PROCESSOR_WIDE_MIN_COLUMNS、TAB_PROCESSOR_SLIM_COLUMNS 等调整"
                            ),
                        }
                    )

                if hints:
                    result["hints"] = hints

        elif action == "add_row":
            values = request.get("values")
            if not values:
                return {"success": False, "error": "缺少必要参数: values"}
            table.add_row(values)
            result = {"message": f"行已添加，新行号: {table.total_rows - 1}"}

        elif action == "insert_row":
            row_index = request.get("row_index")
            values = request.get("values")
            if row_index is None or values is None:
                return {"success": False, "error": "缺少必要参数: row_index和values"}
            table.insert_row(row_index, values)
            result = {"message": f"行已插入到位置: {row_index}"}

        elif action == "update_row":
            row_index = request.get("row_index")
            values = request.get("values")
            if row_index is None or values is None:
                return {"success": False, "error": "缺少必要参数: row_index和values"}
            table.update_row(row_index, values)
            result = {"message": f"行{row_index}已更新"}

        elif action == "delete_row":
            row_index = request.get("row_index")
            if row_index is None:
                return {"success": False, "error": "缺少必要参数: row_index"}
            table.delete_row(row_index)
            result = {"message": f"行{row_index}已删除"}

        elif action == "add_column":
            column_name = request.get("column_name")
            default_value = request.get("default_value", "")
            position = request.get("position")
            if not column_name:
                return {"success": False, "error": "缺少必要参数: column_name"}
            table.add_column(column_name, default_value, position)
            result = {"message": f"列'{column_name}'已添加"}

        elif action == "delete_column":
            column_name = request.get("column_name")
            if not column_name:
                return {"success": False, "error": "缺少必要参数: column_name"}
            table.delete_column(column_name)
            result = {"message": f"列'{column_name}'已删除"}

        elif action == "rename_column":
            old_name = request.get("old_name")
            new_name = request.get("new_name")
            if not old_name or not new_name:
                return {"success": False, "error": "缺少必要参数: old_name和new_name"}
            table.rename_column(old_name, new_name)
            result = {"message": f"列'{old_name}'已重命名为'{new_name}'"}

        elif action == "read_rows":
            row_indices = request.get("row_indices", [])
            column_names = request.get("column_names", [])
            start_index = request.get("start_index", 0)
            limit = request.get("limit", 100)

            rows = table.filter_rows(row_indices, column_names, start_index, limit)
            end_index = min(start_index + len(rows), len(row_indices))
            has_more = end_index < len(row_indices)

            result = {
                "rows": rows,
                "total_requested": len(row_indices),
                "returned": len(rows),
                "start_index": start_index,
                "end_index": end_index,
                "next_start_index": end_index if has_more else None,
                "has_more": has_more,
            }

        elif action == "get_row_columns":
            row_index = request.get("row_index")
            if row_index is None:
                return {"success": False, "error": "缺少必要参数: row_index"}

            column_names = request.get("column_names")
            column_conditions = request.get("column_conditions")
            logic = request.get("logic", "or")
            column_ranges = request.get("column_ranges")
            column_indices = request.get("column_indices")
            start_index = request.get("start_index", 0)
            limit = request.get("limit", 50)
            skip_empty = request.get("skip_empty", False)
            empty_values = request.get("empty_values")

            result = table.get_row_columns(
                row_index,
                column_names,
                column_conditions,
                logic,
                column_ranges,
                column_indices,
                start_index,
                limit,
                skip_empty,
                empty_values,
            )

            result["next_start_index"] = result["end_index"] if result["has_more"] else None

        else:
            return {"success": False, "error": f"未知操作: {action}"}

        if table.column_names:
            result.setdefault("_columns", table.column_names)
        result["success"] = True
        return truncate_response(result)

    except FileNotFoundError as e:
        return {"success": False, "error": str(e), "hint": "请检查文件路径是否正确，确保文件存在"}
    except IndexError as e:
        return {
            "success": False,
            "error": str(e),
            "hint": "行号或列号超出范围，请先使用 get_table_info 查看文件的总行数和总列数",
        }
    except ValueError as e:
        error_msg = str(e)
        hint = ""

        # 针对常见错误提供具体提示
        if "值的数量" in error_msg or "列表长度" in error_msg:
            hint = f"请确保提供的数据值数量与表格列数匹配。使用 get_table_info 查看表格结构"
        elif "列" in error_msg and "不存在" in error_msg:
            hint = f"请检查列名是否正确，使用 get_table_info 查看所有可用的列名"
        elif "无效的正则表达式" in error_msg:
            hint = "请检查正则表达式语法是否正确"

        return {"success": False, "error": error_msg, "hint": hint}
    except Exception as e:
        return {"success": False, "error": str(e), "hint": "如果问题持续存在，请检查文件格式是否正确，或联系技术支持"}


if __name__ == "__main__":

    def decode_stdin_json_bytes(raw: bytes) -> str:
        """将管道/重定向输入按常见编码解码为文本（优先 UTF-8，兼容 GBK）。"""
        if not raw or not raw.strip():
            return ""
        text = None
        for enc in ("utf-8-sig", "utf-8", "gbk"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            text = raw.decode("utf-8", errors="replace")
        return text

    def write_stderr_text(msg: str, encoding: str = "utf-8") -> None:
        """向 stderr 写入文本，避免与 stdout 二进制 JSON 混用时的编码混乱。"""
        line = msg if msg.endswith("\n") else msg + "\n"
        data = line.encode(encoding, errors="replace")
        errb = getattr(sys.stderr, "buffer", None)
        if errb is not None:
            errb.write(data)
        else:
            sys.stderr.write(line)
        sys.stderr.flush()

    def parse_output_encoding(raw) -> str:
        """标准输出 JSON 的编码，仅支持 utf-8（默认）与 gbk。"""
        if raw is None or raw == "":
            return "utf-8"
        s = str(raw).strip().lower().replace("_", "-")
        if s in ("utf-8", "utf8"):
            return "utf-8"
        if s == "gbk":
            return "gbk"
        raise ValueError(f"不支持的 output_encoding: {raw!r}，仅支持 utf-8、gbk")

    def write_stdout_bytes(data: bytes, fallback_encoding: str = "utf-8") -> None:
        buf = getattr(sys.stdout, "buffer", None)
        if buf is not None:
            buf.write(data)
        else:
            sys.stdout.write(data.decode(fallback_encoding, errors="replace"))
        sys.stdout.flush()

    def write_stdout_json(obj: Any, encoding: str) -> None:
        text = json.dumps(obj, ensure_ascii=False, indent=2) + "\n"
        write_stdout_bytes(text.encode(encoding, errors="replace"), fallback_encoding=encoding)

    def write_stdout_text(text: str, encoding: str = "utf-8") -> None:
        write_stdout_bytes(text.encode(encoding, errors="replace"), fallback_encoding=encoding)

    def parse_output_format(raw) -> str:
        if raw is None or raw == "":
            return "json"
        s = str(raw).strip().lower()
        if s in ("json", "tsv", "markdown", "md"):
            return "markdown" if s == "md" else s
        raise ValueError(f"不支持的 output_format: {raw!r}，支持 json、tsv、markdown（或 md）")

    def print_usage():
        print("Tab文件处理工具")
        print("=" * 60)
        print("使用方法:")
        print()
        print("方法1: 从标准输入读取JSON (推荐)")
        print('  echo \'{"action": "get_table_info", "file": "xxx.tab"}\' | python tab_processor.py')
        print("  或在PowerShell中:")
        print('  \'{"action": "get_table_info", "file": "xxx.tab"}\' | python tab_processor.py')
        print()
        print("方法2: 从命令行参数读取JSON")
        print('  python tab_processor.py \'{"action": "get_table_info", "file": "xxx.tab"}\'')
        print()
        print("方法3: 使用简化的命令行参数")
        print("  python tab_processor.py --action get_table_info --file xxx.tab")
        print('  python tab_processor.py --action search --file xxx.tab --keyword "关键词"')
        print("  python tab_processor.py --action search --file xxx.tab --column 列名 --keyword 值 --whole_word true")
        print()
        print("多条件搜索（新功能）:")
        print(
            "  python tab_processor.py --action search --file xxx.tab --column MaxPlayerCount=25 --column Type=1 --logic and"
        )
        print(
            '  python tab_processor.py --action search --file xxx.tab --conditions \'[{"columns":["MaxPlayerCount"],"keyword":"25"},{"columns":["Type"],"keyword":"1"}]\' --logic and'
        )
        print()
        print("统计功能（新功能）:")
        print(
            "  python tab_processor.py --action search --file xxx.tab --column MaxPlayerCount=25 --column Type=1 --count_only true"
        )
        print()
        print("支持的操作:")
        print("  get_table_info  - 获取表格信息")
        print("  search          - 搜索数据")
        print("  read_rows       - 读取指定行")
        print("  get_row_columns - 获取行的列数据")
        print("  update_row      - 更新行数据")
        print("  add_row         - 添加行")
        print("  delete_row      - 删除行")
        print()
        print("常用参数:")
        print("  --whole_word true    - 全字匹配（搜索数字时必须使用）")
        print("  --count_only true    - 仅返回匹配数量")
        print("  --return_columns     - 指定返回的列（逗号分隔）")
        print("  --full_rows true     - 超宽表搜索时强制返回全部列（默认≥40列会自动瘦身）")
        print("  --output_format      - search 结果输出: json（默认）| tsv | markdown")
        print("  --limit              - 限制返回结果数量")
        print("  --start_index        - 起始索引（用于分页）")
        print("  --logic and/or       - 多条件逻辑关系")
        print("  --output_encoding    - 标准输出 JSON 编码: utf-8（默认）或 gbk（tsv/markdown 固定为 utf-8）")
        print("  环境变量:")
        print("    TAB_PROCESSOR_READ_STDIN=0     - 不读 stdin（子进程未关 stdin 时可避免阻塞）")
        print("    TAB_PROCESSOR_AUTO_SLIM=0      - 关闭 search 自动瘦身（默认开启）")
        print("    TAB_PROCESSOR_WIDE_MIN_COLUMNS - 宽表阈值，默认 40（列数≥此值才可能瘦身）")
        print("    TAB_PROCESSOR_SLIM_COLUMNS     - 瘦身优先列，逗号分隔，覆盖内置清单")
        print("    TAB_PROCESSOR_SLIM_FALLBACK    - 优先列均不存在时取表头前 N 列，默认 12")
        print("    TAB_PROCESSOR_MAX_OUTPUT_CHARS - JSON 截断上限（见 truncate_response）")
        print()
        print("实用示例:")
        print("  # 查询25人副本数量")
        print(
            "  python tab_processor.py --action search --file MapList.tab --column MaxPlayerCount=25 --column Type=1 --count_only true"
        )
        print()
        print("  # 获取25人副本的详细信息")
        print(
            "  python tab_processor.py --action search --file MapList.tab --column MaxPlayerCount=25 --column Type=1 --return_columns ID,Name,DisplayName"
        )
        print()
        print("  # 查看文件结构")
        print("  python tab_processor.py --action get_table_info --file MapList.tab")
        print()
        print("=" * 60)

    def parse_simple_args(args):
        """解析简化的命令行参数"""

        request = {}
        i = 0
        # 收集所有的 --column 参数
        column_conditions = []

        while i < len(args):
            if args[i].startswith("--"):
                key = args[i][2:]
                if i + 1 < len(args) and not args[i + 1].startswith("--"):
                    value = args[i + 1]
                    # 某些参数应该保持字符串类型
                    string_params = [
                        "keyword",
                        "column",
                        "columns",
                        "column_names",
                        "return_columns",
                        "old_name",
                        "new_name",
                        "column_conditions",
                        "file",
                        "filepath",
                        "conditions",
                        "logic",
                        "output_encoding",
                        "output_format",
                    ]
                    if key in string_params:
                        # 保持字符串
                        pass
                    elif value.lower() == "true":
                        value = True
                    elif value.lower() == "false":
                        value = False
                    elif value.isdigit():
                        value = int(value)

                    # 特殊处理 --column 参数
                    if key == "column":
                        column_conditions.append(value)
                    else:
                        request[key] = value
                    i += 2
                else:
                    request[key] = True
                    i += 1
            else:
                i += 1

        # 参数名映射：将简化的参数名映射到正式参数名
        if "file" in request and "filepath" not in request:
            request["filepath"] = request.pop("file")

        # 将逗号分隔的字符串转换为列表
        list_params = ["return_columns", "columns", "column_names"]
        for param in list_params:
            if param in request and isinstance(request[param], str):
                request[param] = [s.strip() for s in request[param].split(",")]

        # 解析 conditions 参数（JSON格式）
        if "conditions" in request and isinstance(request["conditions"], str):
            try:
                import json

                request["conditions"] = json.loads(request["conditions"])
            except json.JSONDecodeError:
                pass

        # 处理收集的 column_conditions
        if column_conditions:
            # 检查是否有 column=value 格式
            has_condition_format = any("=" in cond for cond in column_conditions)

            if has_condition_format:
                # 使用 conditions 参数
                conditions = []
                for cond in column_conditions:
                    if "=" in cond:
                        col, keyword = cond.split("=", 1)
                        conditions.append({"columns": [col.strip()], "keyword": keyword.strip()})
                request["conditions"] = conditions
            else:
                # 使用 columns 参数（原来的单列搜索格式）
                request["columns"] = [c.strip() for c in column_conditions]

        return request

    try:
        request = None

        # 方法1: 尝试从 stdin 读取 JSON
        # 仅当除脚本名外无任何参数时才读 stdin。
        # 注意：子进程若未传入 input= 且未关闭 stdin，默认管道无 EOF，buffer.read() 会永久阻塞。
        # 此时请设置环境变量 TAB_PROCESSOR_READ_STDIN=0，或对 subprocess 使用 stdin=DEVNULL / input=b''。
        _read_stdin = os.environ.get("TAB_PROCESSOR_READ_STDIN", "1").lower() not in ("0", "false", "no")
        if _read_stdin and not sys.stdin.isatty() and len(sys.argv) == 1:
            try:
                raw_in = sys.stdin.buffer.read()
                stdin_data = decode_stdin_json_bytes(raw_in)
                if stdin_data.strip():
                    request = json.loads(stdin_data)
            except json.JSONDecodeError:
                pass

        # 方法2: 尝试从命令行参数读取JSON
        if request is None and len(sys.argv) > 1:
            try:
                request = json.loads(sys.argv[1])
            except json.JSONDecodeError:
                # 方法3: 尝试解析简化的命令行参数
                request = parse_simple_args(sys.argv[1:])

        if request is None or "action" not in request:
            # 用法输出到 stderr，避免污染期望从 stdout 读 JSON 的管道
            buf = io.StringIO()
            old_out, sys.stdout = sys.stdout, buf
            try:
                print_usage()
            finally:
                sys.stdout = old_out
            write_stderr_text(buf.getvalue(), "utf-8")
            sys.exit(1)

        saved_action = request.get("action")
        raw_output_format = request.pop("output_format", None)
        raw_output_enc = request.pop("output_encoding", None)
        try:
            output_format = parse_output_format(raw_output_format)
        except ValueError as fmt_err:
            write_stderr_text(f"错误: {fmt_err}", "utf-8")
            sys.exit(1)
        try:
            output_enc = parse_output_encoding(raw_output_enc)
        except ValueError as enc_err:
            write_stderr_text(f"错误: {enc_err}", "utf-8")
            sys.exit(1)

        result = process_request(request)

        use_text_out = (
            output_format in ("tsv", "markdown")
            and saved_action == "search"
            and isinstance(result, dict)
            and result.get("count_only") is not True
            and result.get("success") is not False
            and "error" not in result
            and result.get("rows")
        )
        if use_text_out:
            rows = result["rows"]
            if output_format == "tsv":
                write_stdout_text(format_search_rows_tsv(rows), "utf-8")
            else:
                write_stdout_text(format_search_rows_markdown(rows), "utf-8")
        else:
            # search 且空结果 / count_only 时用 JSON 属预期，不写 stderr；其它 action 误用 tsv/md 再提示
            if output_format in ("tsv", "markdown"):
                obvious_json = (
                    isinstance(result, dict)
                    and saved_action == "search"
                    and (result.get("count_only") is True or not result.get("rows"))
                )
                if not obvious_json:
                    write_stderr_text(
                        "提示: output_format=tsv/markdown 仅适用于 search 且有非空 rows；本次已输出 JSON。\n",
                        "utf-8",
                    )
            write_stdout_json(result, output_enc)

    except json.JSONDecodeError as e:
        write_stderr_text(f"错误: JSON解析失败 - {e}")
        write_stderr_text("")
        buf = io.StringIO()
        old_out, sys.stdout = sys.stdout, buf
        try:
            print_usage()
        finally:
            sys.stdout = old_out
        write_stderr_text(buf.getvalue(), "utf-8")
        sys.exit(1)
    except Exception as e:
        write_stderr_text(f"错误: {e}", "utf-8")
        sys.exit(1)
