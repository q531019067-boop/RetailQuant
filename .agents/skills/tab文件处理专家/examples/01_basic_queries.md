# 基础查询示例

本示例介绍 tab 文件处理工具的基础查询功能，帮助你快速上手。

## 示例1：查看文件基本信息

**场景**：首次接触一个 tab 文件，想了解它的结构

```bash
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action get_table_info --file client/settings/MapList.tab
```

**输出说明**：
- `columns`: 所有列名列表
- `total_rows`: 总行数
- `total_columns`: 总列数
- `column_types`: 每列的数据类型
- `preview`: 前5行数据的预览

**使用建议**：
- 查看文件结构是使用工具的第一步
- 了解列名和数据类型后，才能准确地进行后续查询

---

## 示例2：简单关键词搜索

**场景**：搜索包含特定文本的记录

```bash
# 搜索所有包含"英雄"的记录
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --keyword "英雄"
```

**输出说明**：
- `total_matches`: 匹配的总记录数
- `rows`: 匹配的记录（默认返回前100条）
- `lines`: 匹配记录的行号（从0开始）
- `truncated`: 是否还有更多匹配的记录

**使用建议**：
- 如果匹配记录很多，会自动截断输出
- 使用 `--limit` 控制返回数量
- 使用 `--start_index` 分页获取更多数据

---

## 示例3：指定列搜索

**场景**：在特定列中搜索关键词

```bash
# 在 Name 列中搜索"英雄"
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column Name --keyword "英雄"
```

**优势**：
- 只在指定列中搜索，提高效率
- 避免在其他列中误匹配

**使用建议**：
- 当你知道关键词应该在哪个列时，使用此方法
- 可以同时指定多个列：`--column Name --column DisplayName`

---

## 示例4：精确匹配数字（全字匹配）

**场景**：搜索特定数值，如副本人数、ID 等

```bash
# 错误示例：会匹配到 2500、251 等
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column MaxPlayerCount --keyword 25

# 正确示例：只匹配 25
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column MaxPlayerCount --keyword 25 --whole_word true
```

**重要提示**：
- 搜索数字时，**必须使用** `--whole_word true`
- 否则会匹配到包含该数字的所有值

**适用场景**：
- 搜索 ID：`--column ID --keyword 10 --whole_word true`
- 搜索人数：`--column MaxPlayerCount --keyword 25 --whole_word true`
- 搜索类型：`--column Type --keyword 1 --whole_word true`

---

## 示例5：只返回需要的列

**场景**：减少数据传输，提高效率

```bash
# 只返回 ID、Name、DisplayName 三列
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --keyword "英雄" --return_columns ID,Name,DisplayName
```

**优势**：
- 减少输出数据量
- 提高处理速度
- 结果更清晰易读

**使用建议**：
- 当表格列数很多时（超过10列），建议指定返回列
- 只选择你真正需要的列

---

## 示例6：分页获取数据

**场景**：处理大量匹配记录

```bash
# 第1页：获取前50条
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --keyword "英雄" --limit 50 --start_index 0

# 第2页：获取第51-100条
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --keyword "英雄" --limit 50 --start_index 50

# 第3页：获取第101-150条
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --keyword "英雄" --limit 50 --start_index 100
```

**输出说明**：
- `start_index`: 当前页的起始索引
- `end_index`: 当前页的结束索引
- `next_start_index`: 下一页的起始索引
- `has_more`: 是否还有更多数据

**使用建议**：
- 先用 `--count_only true` 了解总数量
- 再根据总数量决定如何分页

---

## 示例7：统计匹配数量

**场景**：只需要知道有多少条记录，不需要具体数据

```bash
# 统计包含"英雄"的记录数量
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --keyword "英雄" --count_only true
```

**输出示例**：
```json
{
  "total_matches": 156,
  "count_only": true,
  "success": true
}
```

**使用建议**：
- 在获取详细数据前，先用此命令了解数据量
- 避免获取大量不需要的数据

---

## 基础查询最佳实践

### 推荐的三步查询流程

```bash
# 步骤1：了解文件结构
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action get_table_info --file client/settings/MapList.tab

# 步骤2：统计匹配数量
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --keyword "关键词" --count_only true

# 步骤3：获取需要的数据
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --keyword "关键词" --return_columns ID,Name --limit 50
```

### 常用参数组合

| 场景 | 命令 |
|------|------|
| 快速浏览文件 | `--action get_table_info` |
| 统计数量 | `--action search --count_only true` |
| 精确数字匹配 | `--action search --column 列名 --keyword 数字 --whole_word true` |
| 文本模糊搜索 | `--action search --column 列名 --keyword 文本` |
| 获取指定列 | `--action search --return_columns 列1,列2,列3` |
| 分页查询 | `--action search --limit 50 --start_index 0` |

---

## 下一步

- 查看 [高级搜索示例](./02_advanced_search.md) 学习多条件搜索
- 查看 [常见场景示例](./05_common_scenarios.md) 了解实际应用场景
