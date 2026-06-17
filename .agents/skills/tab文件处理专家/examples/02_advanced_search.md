# 高级搜索示例

本示例介绍 tab 文件处理工具的高级搜索功能，包括多条件搜索、正则表达式等。

## 示例1：多条件 AND 搜索

**场景**：查找同时满足多个条件的记录

```bash
# 查找 25人副本 且 Type=1 的记录
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column MaxPlayerCount=25 --column Type=1
```

**说明**：
- 默认使用 AND 逻辑（同时满足所有条件）
- 可以指定任意数量的条件

**适用场景**：
- 查找特定类型的副本
- 查找满足多个属性配置项

---

## 示例2：多条件 OR 搜索

**场景**：查找满足任一条件的记录

```bash
# 查找 25人副本 或 Type=0 的记录
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column MaxPlayerCount=25 --column Type=0 --logic or
```

**说明**：
- 使用 `--logic or` 指定 OR 逻辑
- 满足任一条件即匹配

**适用场景**：
- 查找多种类型的副本
- 查找多个可能的配置值

---

## 示例3：文本 + 数值 组合搜索

**场景**：名称包含特定文本且满足数值条件

```bash
# 查找名称包含"英雄"且人数为25的副本
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column Name=英雄 --column MaxPlayerCount=25
```

**说明**：
- 文本搜索默认是包含匹配
- 数值搜索建议使用 `--whole_word true`

**适用场景**：
- 查找特定名称的副本
- 查找满足多个属性的配置

---

## 示例4：精确数值 + 精确类型

**场景**：精确匹配多个数值字段

```bash
# 查找 25人副本、Type=1、副本ID大于100的记录
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column MaxPlayerCount=25 --column Type=1 --return_columns ID,Name,MaxPlayerCount,Type
```

**注意**：
- 工具不支持直接比较运算符（>、<、>=、<=）
- 可以通过正则表达式实现复杂匹配

---

## 示例5：使用 JSON 格式的 conditions

**场景**：需要更灵活的条件组合

```bash
# 使用 JSON 格式指定多个条件
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --conditions '[{"columns":["MaxPlayerCount"],"keyword":"25"},{"columns":["Type"],"keyword":"1"}]' --logic and
```

**JSON 格式说明**：
```json
[
  {
    "columns": ["列名1", "列名2"],
    "keyword": "搜索关键词",
    "is_regex": false,
    "whole_word": false,
    "case_sensitive": false
  },
  {
    "columns": ["列名3"],
    "keyword": "关键词2"
  }
]
```

**优势**：
- 可以指定多个列进行搜索
- 更灵活的条件配置

---

## 示例6：正则表达式搜索

**场景**：使用正则表达式进行复杂匹配

```bash
# 查找 ID 以 1 开头的记录
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column ID --keyword "^1" --is_regex true

# 查找名称包含数字的记录
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column Name --keyword "\\d+" --is_regex true

# 查找名称以"英雄"开头或结尾的记录
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column Name --keyword "^英雄|英雄$" --is_regex true
```

**常用正则表达式**：
| 模式 | 说明 | 示例 |
|------|------|------|
| `^文本` | 以文本开头 | `^英雄` 匹配 "英雄战宝迦兰" |
| `文本$` | 以文本结尾 | `宫$` 匹配 "荻花宫" |
| `\d+` | 一个或多个数字 | `\d+` 匹配 "25人"、"10人" |
| `[abc]` | 匹配 a、b 或 c | `[一二三]` 匹配包含一二三的 |
| `.*` | 任意字符（贪婪） | `英雄.*` 匹配 "英雄战宝迦兰" |
| `.+` | 一个或多个任意字符 | `.+` 匹配非空内容 |

**使用建议**：
- 正则表达式功能强大但复杂，建议先掌握基础模式
- 测试正则表达式时，先用 `--limit 5` 验证结果

---

## 示例7：大小写敏感搜索

**场景**：区分大小写的精确匹配

```bash
# 大小写不敏感（默认）
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column Name --keyword "英雄" --case_sensitive false

# 大小写敏感
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column Name --keyword "Hero" --case_sensitive true
```

**使用场景**：
- 英文配置文件需要区分大小写
- 某些代码或标识符需要精确匹配

---

## 示例8：复杂组合查询

**场景**：多个条件 + 正则表达式 + 大小写敏感

```bash
# 查找名称以"英雄"开头，人数为25，Type为1的记录
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column Name=^英雄 --is_regex true --column MaxPlayerCount=25 --column Type=1 --return_columns ID,Name,DisplayName
```

**说明**：
- 可以混合使用不同的搜索选项
- 每个条件可以独立配置

---

## 示例9：多列搜索同一关键词

**场景**：在多个列中搜索相同的关键词

```bash
# 在 Name 和 DisplayName 列中搜索"英雄"
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --conditions '[{"columns":["Name","DisplayName"],"keyword":"英雄"}]'
```

**优势**：
- 一次搜索多个列
- 任一列匹配即返回结果

---

## 示例10：统计复杂条件的匹配数

**场景**：了解满足复杂条件的记录数量

```bash
# 统计 25人副本且Type=1的记录数
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column MaxPlayerCount=25 --column Type=1 --count_only true
```

**输出示例**：
```json
{
  "total_matches": 29,
  "count_only": true,
  "success": true
}
```

**使用建议**：
- 在获取详细数据前，先用此命令了解数据量
- 避免获取大量不需要的数据

---

## 高级搜索最佳实践

### 推荐的搜索流程

```bash
# 步骤1：了解文件结构
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action get_table_info --file client/settings/MapList.tab

# 步骤2：构建搜索条件
# 根据需要选择：
# - 简单关键词搜索
# - 多条件 AND/OR 搜索
# - 正则表达式搜索
# - 组合搜索

# 步骤3：统计匹配数量
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column MaxPlayerCount=25 --column Type=1 --count_only true

# 步骤4：获取详细数据
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column MaxPlayerCount=25 --column Type=1 --return_columns ID,Name,DisplayName --limit 50
```

### 常用搜索模式

| 场景 | 命令 |
|------|------|
| 精确数值匹配 | `--column 列名 --keyword 数字 --whole_word true` |
| 多条件 AND | `--column 条件1 --column 条件2` |
| 多条件 OR | `--column 条件1 --column 条件2 --logic or` |
| 正则表达式 | `--column 列名 --keyword "正则" --is_regex true` |
| 多列搜索 | `--conditions '[{"columns":["列1","列2"],"keyword":"关键词"}]'` |
| 大小写敏感 | `--column 列名 --keyword "Text" --case_sensitive true` |

### 搜索优化技巧

1. **指定搜索列**：始终使用 `--column` 指定搜索列，提高效率
2. **使用全字匹配**：搜索数字时，使用 `--whole_word true`
3. **先统计后查询**：先用 `--count_only true` 了解数据量
4. **限制返回列**：使用 `--return_columns` 减少数据传输
5. **分页处理**：使用 `--limit` 和 `--start_index` 分页获取数据

---

## 下一步

- 查看 [数据修改示例](./03_data_modification.md) 学习如何修改数据
- 查看 [批量处理示例](./04_batch_processing.md) 学习批量操作
- 查看 [常见场景示例](./05_common_scenarios.md) 了解实际应用场景
