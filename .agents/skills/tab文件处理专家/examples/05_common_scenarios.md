# 常见场景示例

本示例介绍 tab 文件处理工具在实际工作中的应用场景，帮助你快速解决常见问题。

## 场景1：查询副本信息

**需求**：查询 MapList.tab 中所有 25 人副本的信息

**解决方案**：
```bash
# 步骤1：查看文件结构
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action get_table_info --file client/settings/MapList.tab

# 步骤2：统计25人副本数量
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column MaxPlayerCount=25 --column Type=1 --count_only true

# 步骤3：获取副本详细信息
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column MaxPlayerCount=25 --column Type=1 --return_columns ID,Name,DisplayName,MaxPlayerCount
```

**输出示例**：
```json
{
  "total_matches": 29,
  "rows": [
    {
      "ID": "46",
      "Name": "英雄战宝迦兰",
      "DisplayName": "英雄战宝迦兰",
      "MaxPlayerCount": "25"
    },
    {
      "ID": "58",
      "Name": "25人英雄荻花宫后山",
      "DisplayName": "25人英雄荻花宫后山",
      "MaxPlayerCount": "25"
    }
  ]
}
```

---

## 场景2：查找特定副本

**需求**：查找 ID 为 46 的副本信息

**解决方案**：
```bash
# 使用全字匹配精确查找
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column ID --keyword 46 --whole_word true --return_columns ID,Name,DisplayName,MaxPlayerCount,Type
```

**注意**：
- 搜索 ID 时必须使用 `--whole_word true`
- 否则会匹配到包含 46 的其他 ID（如 146、246）

---

## 场景3：统计副本类型分布

**需求**：统计不同类型副本的数量

**解决方案**：
```bash
# 统计 Type=0 的数量
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column Type=0 --count_only true

# 统计 Type=1 的数量
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column Type=1 --count_only true

# 统计 Type=2 的数量
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column Type=2 --count_only true
```

**结果示例**：
```
Type=0: 4 条
Type=1: 156 条
Type=2: 56 条
```

---

## 场景4：查找包含特定关键词的副本

**需求**：查找所有名称包含"英雄"的副本

**解决方案**：
```bash
# 查找名称包含"英雄"的副本
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column Name=英雄 --return_columns ID,Name,DisplayName
```

**注意**：
- 文本搜索默认是包含匹配
- 不需要使用 `--whole_word true`
- 会匹配到 "英雄战宝迦兰"、"英雄大明宫" 等

---

## 场景5：查找特定人数范围的副本

**需求**：查找人数在 10-25 之间的副本

**解决方案**：
```bash
# 查找 10 人副本
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column MaxPlayerCount=10 --whole_word true --count_only true

# 查找 25 人副本
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column MaxPlayerCount=25 --whole_word true --count_only true

# 查找 5 人副本
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column MaxPlayerCount=5 --whole_word true --count_only true
```

**注意**：
- 工具不支持范围查询（如 10-25）
- 需要分别查询每个值
- 可以使用脚本自动化此过程

---

## 场景6：批量导出副本数据

**需求**：导出所有 25 人副本的数据到文件

**解决方案**：
```bash
# 步骤1：统计总数
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column MaxPlayerCount=25 --column Type=1 --count_only true

# 步骤2：分页导出数据
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column MaxPlayerCount=25 --column Type=1 --return_columns ID,Name,DisplayName,MaxPlayerCount --limit 50 --start_index 0 > 25man_dungeons_page1.json
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column MaxPlayerCount=25 --column Type=1 --return_columns ID,Name,DisplayName,MaxPlayerCount --limit 50 --start_index 50 > 25man_dungeons_page2.json
```

**使用建议**：
- 使用 `>` 将输出重定向到文件
- 根据总数决定分页数量
- 使用 `--return_columns` 只导出需要的列

---

## 场景7：验证数据完整性

**需求**：验证是否有重复的副本 ID

**解决方案**：
```bash
# 步骤1：获取文件信息
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action get_table_info --file client/settings/MapList.tab

# 步骤2：查询特定 ID 是否存在
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column ID --keyword 46 --whole_word true --count_only true
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column ID --keyword 58 --whole_word true --count_only true
```

**注意**：
- 使用 `--whole_word true` 进行精确匹配
- 使用 `--count_only true` 快速验证
- 可以编写脚本批量验证多个 ID

---

## 场景8：查找配置错误

**需求**：查找 MaxPlayerCount 为 0 的记录（可能是配置错误）

**解决方案**：
```bash
# 查找 MaxPlayerCount 为 0 的记录
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column MaxPlayerCount=0 --whole_word true --return_columns ID,Name,DisplayName,MaxPlayerCount
```

**使用场景**：
- 检查配置错误
- 验证数据完整性
- 找出异常配置

---

## 场景9：按名称模糊搜索

**需求**：查找名称包含"荻花"的所有副本

**解决方案**：
```bash
# 查找名称包含"荻花"的副本
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column Name=荻花 --return_columns ID,Name,DisplayName
```

**匹配结果**：
- "25人英雄荻花宫后山"
- "25人英雄荻花圣殿"
- "25人英雄荻花圣殿·正殿"

---

## 场景10：批量修改副本类型

**需求**：将所有 Type=1 的副本改为 Type=2

**解决方案**：
```bash
# 步骤1：查询所有 Type=1 的记录
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column Type=1 --return_columns ID,Name,DisplayName,Type --limit 100

# 步骤2：逐个更新记录（需要知道行号）
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action update_row --file client/settings/MapList.tab --row_index 43 --values '{"Type":"2"}'
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action update_row --file client/settings/MapList.tab --row_index 53 --values '{"Type":"2"}'
```

**注意**：
- 工具不支持批量更新
- 需要逐个更新记录
- 建议编写脚本自动化此过程

---

## 常见场景速查表

| 场景 | 命令 |
|------|------|
| 查询25人副本 | `--action search --column MaxPlayerCount=25 --column Type=1` |
| 查找特定ID | `--action search --column ID --keyword 46 --whole_word true` |
| 统计类型分布 | `--action search --column Type=1 --count_only true` |
| 查找包含关键词 | `--action search --column Name=英雄` |
| 查找配置错误 | `--action search --column MaxPlayerCount=0 --whole_word true` |
| 导出数据 | `--action search --return_columns ID,Name > output.json` |
| 验证数据 | `--action search --column ID --keyword 46 --count_only true` |

---

## 实用技巧

### 1. 快速了解文件

```bash
# 一条命令了解文件结构
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action get_table_info --file client/settings/MapList.tab
```

### 2. 高效查询流程

```bash
# 三步查询法
# 1. 统计数量
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column Type=1 --count_only true

# 2. 获取样本
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column Type=1 --limit 10

# 3. 获取详细数据
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column Type=1 --return_columns ID,Name,DisplayName
```

### 3. 避免常见错误

```bash
# 错误：搜索数字时没有使用全字匹配
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column MaxPlayerCount --keyword 25

# 正确：使用全字匹配
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column MaxPlayerCount --keyword 25 --whole_word true
```

---

## 下一步

- 查看 [基础查询示例](./01_basic_queries.md) 学习基础功能
- 查看 [高级搜索示例](./02_advanced_search.md) 学习高级功能
- 查看 [数据修改示例](./03_data_modification.md) 学习修改操作
- 查看 [批量处理示例](./04_batch_processing.md) 学习批量操作
