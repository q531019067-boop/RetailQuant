# 数据修改示例

本示例介绍如何使用 tab 文件处理工具修改数据，包括添加、更新、删除等操作。

## ?? 重要提示

**修改数据前请务必备份文件！**

```bash
# 备份文件
cp client/settings/MapList.tab client/settings/MapList.tab.backup
```

---

## 示例1：添加新行

**场景**：在文件末尾添加一条新记录

```bash
# 使用字典格式（推荐）
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action add_row --file client/settings/MapList.tab --values '{"ID":"999","Name":"测试副本","DisplayName":"测试副本"}'
```

**注意**：
- 使用字典格式时，只需提供需要修改的列
- 未提供的列将使用默认值（空字符串）
- 列名必须与文件中的列名完全匹配

**输出示例**：
```json
{
  "message": "行已添加，新行号: 216",
  "success": true
}
```

---

## 示例2：插入行到指定位置

**场景**：在指定位置插入新行

```bash
# 在第10行（索引9）插入新行
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action insert_row --file client/settings/MapList.tab --row_index 9 --values '{"ID":"999","Name":"测试副本"}'
```

**注意**：
- 行索引从0开始
- 插入后，后续行的索引会自动调整

---

## 示例3：更新指定行

**场景**：修改某一行的一个或多个字段

```bash
# 方式1：使用字典格式（推荐）
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action update_row --file client/settings/MapList.tab --row_index 43 --values '{"Name":"新名称","DisplayName":"新显示名称"}'
```

**注意**：
- 使用字典格式时，只需提供要修改的列
- 其他列保持不变
- 列名必须与文件中的列名完全匹配

---

## 示例4：删除指定行

**场景**：删除某一行

```bash
# 删除第44行（索引43）
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action delete_row --file client/settings/MapList.tab --row_index 43
```

**注意**：
- 删除后，后续行的索引会自动调整
- 删除操作不可撤销，请谨慎操作

---

## 示例5：添加新列

**场景**：在表格中添加新列

```bash
# 在表格末尾添加新列
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action add_column --file client/settings/MapList.tab --column_name "NewColumn" --default_value "0"

# 在指定位置添加新列（在第3列）
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action add_column --file client/settings/MapList.tab --column_name "NewColumn" --default_value "0" --position 3
```

**注意**：
- position 从0开始
- 如果不指定 position，默认添加到末尾
- 所有现有行的新列将使用默认值

---

## 示例6：删除列

**场景**：删除表格中的某列

```bash
# 删除名为 "NewColumn" 的列
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action delete_column --file client/settings/MapList.tab --column_name "NewColumn"
```

**注意**：
- 删除操作不可撤销
- 列名必须与文件中的列名完全匹配

---

## 示例7：重命名列

**场景**：修改列名

```bash
# 将 "OldName" 重命名为 "NewName"
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action rename_column --file client/settings/MapList.tab --old_name "OldName" --new_name "NewName"
```

**注意**：
- 新列名不能与现有列名重复
- 重命名操作不可撤销

---

## 数据修改最佳实践

### 推荐的修改流程

```bash
# 步骤1：备份文件
cp client/settings/MapList.tab client/settings/MapList.tab.backup

# 步骤2：查看文件结构
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action get_table_info --file client/settings/MapList.tab

# 步骤3：找到要修改的行
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column ID --keyword 46 --return_columns ID,Name,DisplayName

# 步骤4：执行修改
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action update_row --file client/settings/MapList.tab --row_index 43 --values '{"Name":"新名称"}'

# 步骤5：验证修改结果
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column ID --keyword 46 --return_columns ID,Name,DisplayName
```

### 常用修改操作

| 场景 | 命令 |
|------|------|
| 添加新行 | `--action add_row --values '{"列名":"值"}'` |
| 插入行 | `--action insert_row --row_index 0 --values '{"列名":"值"}'` |
| 更新行 | `--action update_row --row_index 0 --values '{"列名":"新值"}'` |
| 删除行 | `--action delete_row --row_index 0` |
| 添加列 | `--action add_column --column_name "新列名" --default_value "默认值"` |
| 删除列 | `--action delete_column --column_name "列名"` |
| 重命名列 | `--action rename_column --old_name "旧列名" --new_name "新列名"` |

### 修改注意事项

1. **始终备份**：修改前务必备份原文件
2. **验证列名**：确保列名与文件中的列名完全匹配
3. **验证行号**：确保行号在有效范围内（使用 get_table_info 查看）
4. **测试修改**：先在备份文件上测试，确认无误后再修改原文件
5. **验证结果**：修改后使用 search 命令验证修改结果

---

## 下一步

- 查看 [批量处理示例](./04_batch_processing.md) 学习批量操作
- 查看 [常见场景示例](./05_common_scenarios.md) 了解实际应用场景
