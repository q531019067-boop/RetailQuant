# 批量处理示例

本示例介绍如何使用 tab 文件处理工具进行批量操作，提高工作效率。

## 示例1：批量查询并处理

**场景**：查询多个条件，分别处理

```bash
# 步骤1：查询所有25人副本
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column MaxPlayerCount=25 --column Type=1 --return_columns ID,Name,DisplayName --count_only true

# 步骤2：获取前50条记录
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column MaxPlayerCount=25 --column Type=1 --return_columns ID,Name,DisplayName --limit 50 --start_index 0

# 步骤3：获取后50条记录
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column MaxPlayerCount=25 --column Type=1 --return_columns ID,Name,DisplayName --limit 50 --start_index 50
```

**使用建议**：
- 先用 `--count_only true` 了解总数量
- 根据总数量决定分页策略
- 使用 `--return_columns` 减少数据传输

---

## 示例2：批量更新（手动方式）

**场景**：更新多个记录的某个字段

```bash
# 步骤1：查询所有需要更新的记录
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column Type=1 --return_columns ID,Name,DisplayName,Type --limit 100

# 步骤2：逐个更新记录（需要知道行号）
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action update_row --file client/settings/MapList.tab --row_index 43 --values '{"Type":"2"}'
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action update_row --file client/settings/MapList.tab --row_index 53 --values '{"Type":"2"}'
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action update_row --file client/settings/MapList.tab --row_index 57 --values '{"Type":"2"}'
```

**注意**：
- 工具不支持批量更新操作
- 需要逐个更新记录
- 建议编写脚本自动化此过程

---

## 示例3：批量删除（手动方式）

**场景**：删除多个记录

```bash
# 步骤1：查询所有需要删除的记录
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column Name=测试 --return_columns ID,Name,DisplayName

# 步骤2：逐个删除记录（注意：删除后行号会变化）
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action delete_row --file client/settings/MapList.tab --row_index 215
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action delete_row --file client/settings/MapList.tab --row_index 214
```

**注意**：
- 删除操作会改变后续行的索引
- 建议从后往前删除
- 删除操作不可撤销

---

## 示例4：批量导出数据

**场景**：导出特定条件的数据

```bash
# 步骤1：统计需要导出的记录数量
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column Type=1 --count_only true

# 步骤2：分页导出所有数据
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column Type=1 --return_columns ID,Name,DisplayName,MaxPlayerCount --limit 100 --start_index 0 > export_page1.json
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column Type=1 --return_columns ID,Name,DisplayName,MaxPlayerCount --limit 100 --start_index 100 > export_page2.json
```

**使用建议**：
- 使用 `>` 将输出重定向到文件
- 分页导出避免数据量过大
- 使用 `--return_columns` 只导出需要的列

---

## 示例5：批量验证数据

**场景**：验证数据的完整性

```bash
# 步骤1：检查是否有重复的ID
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action get_table_info --file client/settings/MapList.tab

# 步骤2：查询特定ID是否存在
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column ID --keyword 46 --whole_word true --count_only true

# 步骤3：查询特定名称是否存在
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column Name --keyword "英雄战宝迦兰" --count_only true
```

**使用建议**：
- 使用 `--whole_word true` 进行精确匹配
- 使用 `--count_only true` 快速验证
- 对比多个查询结果验证数据一致性

---

## 示例6：批量统计分析

**场景**：统计各类数据的数量

```bash
# 统计 Type=1 的记录数
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column Type=1 --count_only true

# 统计 Type=0 的记录数
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column Type=0 --count_only true

# 统计 25人副本的数量
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column MaxPlayerCount=25 --column Type=1 --count_only true

# 统计 10人副本的数量
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column MaxPlayerCount=10 --column Type=1 --count_only true
```

**使用建议**：
- 多个统计命令可以并行执行
- 将结果记录到文件中便于分析
- 使用脚本自动化统计过程

---

## 批量处理最佳实践

### 推荐的批量处理流程

```bash
# 步骤1：备份文件
cp client/settings/MapList.tab client/settings/MapList.tab.backup

# 步骤2：了解数据分布
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column Type=1 --count_only true
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column Type=0 --count_only true

# 步骤3：分批处理数据
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column Type=1 --limit 50 --start_index 0
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column Type=1 --limit 50 --start_index 50

# 步骤4：验证处理结果
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column Type=1 --count_only true
```

### 批量处理技巧

1. **先统计后处理**：先用 `--count_only true` 了解数据量
2. **分批处理**：使用 `--limit` 和 `--start_index` 分批处理
3. **减少数据传输**：使用 `--return_columns` 只获取需要的列
4. **并行查询**：多个独立的查询可以并行执行
5. **结果重定向**：使用 `>` 将输出重定向到文件
6. **脚本自动化**：对于复杂的批量操作，建议编写脚本

### 批量操作注意事项

1. **删除操作要谨慎**：删除会改变行号，建议从后往前删除
2. **更新操作要验证**：更新后使用 search 验证结果
3. **大文件要分批**：避免一次性处理过多数据
4. **错误要记录**：记录批量操作中的错误，便于排查
5. **性能要监控**：监控批量操作的执行时间，优化策略

---

## 下一步

- 查看 [常见场景示例](./05_common_scenarios.md) 了解实际应用场景
- 查看 [基础查询示例](./01_basic_queries.md) 回顾基础功能
