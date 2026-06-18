import json
import os


# 默认 512KB：原 2KB 会导致常见搜索（几十行、数列）也被截断，Agent/终端几乎无法一次拿全结果。
# 可通过环境变量覆盖，例如：set TAB_PROCESSOR_MAX_OUTPUT_CHARS=2097152
def _max_output_chars() -> int:
    raw = os.environ.get("TAB_PROCESSOR_MAX_OUTPUT_CHARS", "").strip()
    if raw:
        try:
            n = int(raw, 10)
            if n >= 4096:
                return min(n, 50 * 1024 * 1024)
        except ValueError:
            pass
    return 512 * 1024


MAX_OUTPUT_CHARS = _max_output_chars()
CUT_COLUMNS_COUNT = 5


def truncate_response(response: dict) -> dict:
    """Truncate response to stay within output limit"""
    columns = response.pop("_columns", None)
    column_truncated = False

    # 如果是count_only模式，直接返回，不需要截断
    if response.get("count_only"):
        return response

    dumped = json.dumps(response, ensure_ascii=False)
    if len(dumped) <= MAX_OUTPUT_CHARS:
        return response

    new_response = response.copy()
    original_lines = new_response.get("lines", [])

    list_fields = ["rows", "matches"]
    for field in list_fields:
        if field in new_response and isinstance(new_response[field], list):
            original = new_response[field]
            if not original:
                continue

            first_row_only = original[:1]
            test_response = new_response.copy()
            test_response[field] = first_row_only
            if len(json.dumps(test_response, ensure_ascii=False)) > MAX_OUTPUT_CHARS:
                if columns is not None and isinstance(columns, list):
                    keep_cols = columns[:CUT_COLUMNS_COUNT]
                    column_truncated = True
                    truncated_rows = []
                    for row in original:
                        new_row = {}
                        for col in keep_cols:
                            new_row[col] = row.get(col, None)
                        truncated_rows.append(new_row)
                    original = truncated_rows
                    new_response[field] = original

            original_len = len(original)
            for reduce in range(1, original_len + 1):
                truncated = original[: original_len - reduce]
                new_response[field] = truncated
                if "lines" in new_response and isinstance(new_response["lines"], list):
                    lines_count = max(50, len(truncated))
                    lines_count = min(lines_count, len(original_lines))
                    new_response["lines"] = original_lines[:lines_count]
                if len(json.dumps(new_response, ensure_ascii=False)) <= MAX_OUTPUT_CHARS:
                    new_response["truncated_by_server"] = True
                    base_msg = f"输出超过{MAX_OUTPUT_CHARS}字符，已截断"
                    if column_truncated:
                        base_msg += f"，仅保留前{CUT_COLUMNS_COUNT}列"
                    base_msg += f"，返回前{len(truncated)}条，保留至少50行"
                    hint = "\n\n[提示] 为避免截断，您可以："
                    hint += "\n1. 使用return_columns指定需要的列（如：['ID', 'Name']）"
                    hint += (
                        "\n2. 使用start_index分页获取更多数据（当前返回"
                        + str(len(truncated))
                        + "条，下次从"
                        + str(len(truncated))
                        + "开始）"
                    )
                    if column_truncated:
                        hint += "\n3. 列数很多时，使用get_row_columns工具"
                    else:
                        hint += "\n3. 行数很多但列数较少时，使用read_rows工具"
                    if "total_matches" in new_response:
                        hint += "\n4. 使用更精确的搜索条件"
                    base_msg += hint
                    new_response["truncated_message"] = base_msg
                    new_response["hint"] = {
                        "returned_count": len(truncated),
                        "next_start_index": len(truncated),
                        "suggestion": "使用return_columns指定列，或使用start_index分页"
                        + ("，或使用get_row_columns处理多列" if column_truncated else "，或使用read_rows处理多行"),
                    }
                    return new_response

            new_response[field] = []
            if "lines" in new_response and isinstance(new_response["lines"], list):
                lines_count = max(50, len(original_lines))
                new_response["lines"] = original_lines[:lines_count]
            if len(json.dumps(new_response, ensure_ascii=False)) <= MAX_OUTPUT_CHARS:
                new_response["truncated_by_server"] = True
                base_msg = f"输出超过{MAX_OUTPUT_CHARS}字符，已截断"
                if column_truncated:
                    base_msg += f"，仅保留前{CUT_COLUMNS_COUNT}列"
                base_msg += "，截断为空，保留至少50行"
                hint = "\n\n[提示] 为避免截断，您可以："
                hint += "\n1. 使用return_columns指定需要的列（如：['ID', 'Name']）"
                hint += "\n2. 列数很多时，使用get_row_columns工具"
                base_msg += hint
                new_response["truncated_message"] = base_msg
                new_response["hint"] = {
                    "returned_count": 0,
                    "next_start_index": 0,
                    "suggestion": "使用return_columns指定列，或使用get_row_columns处理多列",
                }
                return new_response

    string_fields = ["markdown"]
    for field in string_fields:
        if field in new_response and isinstance(new_response[field], str):
            original = new_response[field]
            original_len = len(original)
            for cut in range(original_len, 0, -100):
                truncated_str = original[:cut]
                new_response[field] = truncated_str
                if len(json.dumps(new_response, ensure_ascii=False)) <= MAX_OUTPUT_CHARS:
                    new_response["truncated_by_server"] = True
                    base_msg = f"输出超过{MAX_OUTPUT_CHARS}字符，字符串已截断"
                    if column_truncated:
                        base_msg += f"（列也已截断，仅保留前{CUT_COLUMNS_COUNT}列）"
                    hint = "\n\n[提示] 为避免截断，您可以："
                    hint += "\n1. 使用return_columns指定需要的列（如：['ID', 'Name']）"
                    if column_truncated:
                        hint += "\n2. 列数很多时，使用get_row_columns工具"
                    else:
                        hint += "\n2. 使用start_index分页获取更多数据"
                    base_msg += hint
                    new_response["truncated_message"] = base_msg
                    return new_response
            new_response[field] = ""
            new_response["truncated_by_server"] = True
            base_msg = f"输出超过{MAX_OUTPUT_CHARS}字符，截断为空"
            if column_truncated:
                base_msg += f"（列也已截断，仅保留前{CUT_COLUMNS_COUNT}列）"
            hint = "\n\n[提示] 为避免截断，您可以："
            hint += "\n1. 使用return_columns指定需要的列（如：['ID', 'Name']）"
            if column_truncated:
                hint += "\n2. 列数很多时，使用get_row_columns工具"
            else:
                hint += "\n2. 使用start_index分页获取更多数据"
            base_msg += hint
            new_response["truncated_message"] = base_msg
            return new_response

    new_response["truncated_by_server"] = True
    base_msg = f"输出超过{MAX_OUTPUT_CHARS}字符，无法进一步截断"
    if column_truncated:
        base_msg += f"（列已截断，仅保留前{CUT_COLUMNS_COUNT}列）"
    hint = "\n\n[提示] 为避免截断，您可以："
    hint += "\n1. 使用return_columns指定需要的列（如：['ID', 'Name']）"
    if column_truncated:
        hint += "\n2. 列数很多时，使用get_row_columns工具"
    else:
        hint += "\n2. 使用start_index分页获取更多数据"
    base_msg += hint
    new_response["truncated_message"] = base_msg
    return new_response
