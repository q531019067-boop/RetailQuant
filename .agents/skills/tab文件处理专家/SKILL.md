---
name: ".tab文件处理专家"
description: ".tab文件处理专家，专门用于处理.tab格式文件，提供读取、修改、查询等完整功能。支持大文件处理，复杂搜索，分页查询等高级特性。 tab格式的文件读取非常容易失败，请使用本工具来操作，避免手写直接操作"
---

# tab文件处理专家

## 技能描述
tab文件处理专家，专门用于处理.tab格式文件，提供读取、修改、查询等完整功能。
tab文件的处理非常容易失败，请尽量使用我提供的python代码来处理，不要直接用命令行读写文件。

## Agent 必读（避免常见失败）

### 1. 编码：不要用 IDE / ripgrep 直接搜中文
- 多数 `.tab` 为 **GBK**。用 UTF-8 关键词在仓库里 **全文搜索中文往往 0 条**，属于正常现象。
- **查中文内容、中文列名匹配**：一律用 `tab_processor.py` 的 `search`（或先 `get_table_info` 再按列搜），不要依赖 `grep`/`rg` 对 `.tab` 的搜索结果下结论。

### 2. 超宽表：优先带 `--return_columns` 或使用自动瘦身
- 像 `NpcTemplate.tab`、`skills.tab` 等常有 **几十～几百列**。若把整行打成 JSON，体积极大，Agent 与终端都不好处理。
- **工具行为**：当表 **列数 ≥ 阈值**（默认 40，可由 `TAB_PROCESSOR_WIDE_MIN_COLUMNS` 修改）且未指定 `--return_columns`、未加 `--full_rows true`、且未用 `TAB_PROCESSOR_AUTO_SLIM=0` 关闭时，`search` 会 **自动只返回**「参与搜索的列 + 常用列」（默认常用列见内置清单，可用 `TAB_PROCESSOR_SLIM_COLUMNS` 覆盖）。此时结果里会有 `auto_slimmed_columns`、`returned_column_names` 及对应 `hints`。
- **需要整行所有列**时：显式加 `--full_rows true`。
- **仍建议**：在已知列名时直接用 `--return_columns ID,Name,...`，语义最清晰。

### 3. 便于粘贴表格的输出格式
- `--output_format tsv`：制表符分隔，适合再加工。
- `--output_format markdown`（或 `md`）：Markdown 表格，适合直接贴进答复。**仅当** `action=search`、有非空 `rows` 时生效；否则仍输出 JSON。`tsv`/`markdown` 的文本为 **UTF-8**。

### 4. 路径与文件名大小写
- 仓库内常见 **`NpcTemplate.tab`**（大小写混写）。Windows 上路径往往不敏感，**Linux/CI 敏感**，请与仓库中实际文件名一致。

### 5. Windows / PowerShell
- 子进程捕获 stdout 时，尽量让脚本输出 **UTF-8**（`tsv`/`markdown` 已是 UTF-8；JSON 可用 `--output_encoding utf-8`）。
- 避免在 PowerShell 里随意管道转码导致乱码；需要落盘时可用 `Set-Content -Encoding utf8` 或让 Python 写文件。

## tab格式概述

### 什么是tab格式
tab格式是一种类CSV的表格格式，使用制表符（\t）作为列分隔符。与CSV格式相比，tab格式具有以下特点：

- 使用制表符（\t）分隔列，而不是逗号
- 字符串不需要引号包裹
- 支持中文等多字节字符
- 通常使用GBK编码，特别是在中文环境中

### tab格式的优势
- 避免了CSV格式中逗号分隔符与内容冲突的问题
- 处理包含逗号的字符串更方便
- 在中文环境下编码兼容性更好
- 适合游戏配置文件等场景

## 处理难点

### 1. 编码问题
- GBK编码与UTF-8编码的转换
- 多字节字符的处理
- 非法字节的处理

### 2. 大文件处理
- 文件可能非常大，无法一次性加载到内存
- 需要高效的随机访问机制
- 修改操作需要考虑性能

### 3. 列数过多
- 某些配置文件可能有几百列
- 显示和查询时需要智能截断
- 需要按需选择列的功能

### 4. 行数过多
- 表格可能包含成千上万行
- 需要分页查询机制
- 搜索结果需要分页返回

### 5. 搜索复杂性
- 需要支持多种搜索模式
- 正则表达式、全字匹配、通配符
- 多条件组合（与、或关系）

## 工具使用方法

### 工具位置
所有处理工具位于当前工具的子目录 `scripts` 目录下：
- `scripts/tab_processor.py` - 核心处理模块
- `scripts/truncate_response.py` - 响应截断模块

**重要提示**：在 Trae IDE 中使用时，请使用完整路径：
```bash
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action get_table_info --file client/settings/MapList.tab
```

### 命令行使用方式（推荐）

**重要改进**：工具现在支持三种命令行使用方式，大大提高了易用性：

#### 方式1：简化的命令行参数（最简单）
```bash
# 获取文件信息
python scripts/tab_processor.py --action get_table_info --file client/settings/MapList.tab

# 搜索数据
python scripts/tab_processor.py --action search --file client/settings/MapList.tab --keyword "关键词"

# 在指定列中搜索
python scripts/tab_processor.py --action search --file client/settings/MapList.tab --column MaxPlayerCount --keyword 25 --whole_word true

# 指定返回的列
python scripts/tab_processor.py --action search --file client/settings/MapList.tab --column MaxPlayerCount --keyword 25 --return_columns ID,Name,DisplayName

# 超宽表示例（NpcTemplate）：按名称搜 NPC，只取需要的列（推荐写法）
python scripts/tab_processor.py --action search --file client/settings/NpcTemplate.tab --column Name --keyword "李复" --whole_word true --return_columns ID,Name,Title

# 同上：不指定 return_columns 时，列数≥40 会自动瘦身；要整行则加 --full_rows true
python scripts/tab_processor.py --action search --file client/settings/NpcTemplate.tab --column Name --keyword "李复" --whole_word true --output_format markdown

# 分页获取结果
python scripts/tab_processor.py --action search --file client/settings/MapList.tab --keyword "关键词" --start_index 0 --limit 50
```

#### 方式2：从标准输入读取JSON
```bash
# 在bash中
echo '{"action": "get_table_info", "file": "client/settings/MapList.tab"}' | python scripts/tab_processor.py

# 在PowerShell中
'{"action": "get_table_info", "file": "client/settings/MapList.tab"}' | python scripts/tab_processor.py
```

#### 方式3：从命令行参数读取JSON
```bash
python scripts/tab_processor.py '{"action": "get_table_info", "file": "client/settings/MapList.tab"}'
```

**参数说明**：
- `--action`: 操作类型（get_table_info, search, read_rows, get_row_columns, update_row, add_row, delete_row等）
- `--file` 或 `--filepath`: 文件路径
- `--keyword`: 搜索关键词
- `--column` 或 `--columns`: 指定搜索的列，支持多条件格式（如：`--column MaxPlayerCount=25 --column Type=1`）
- `--return_columns`: 指定返回的列（逗号分隔）
- `--full_rows`: 超宽表搜索时返回全部列（true/false，默认 false；列数达到阈值时会自动瘦身，见下方环境变量；本参数可关闭该行为）
- `--output_format`: `json`（默认）| `tsv` | `markdown`（或 `md`）；仅对 `search` 且存在非空 `rows` 时以纯文本输出，否则仍为 JSON（`search` 且 0 条匹配、`count_only` 等预期为 JSON 时**不会**向 stderr 刷提示）
- `--whole_word`: 全字匹配（true/false）
- `--case_sensitive`: 大小写敏感（true/false）
- `--is_regex`: 使用正则表达式（true/false）
- `--start_index`: 起始索引（用于分页）
- `--limit`: 返回结果数量限制
- `--logic`: 多条件逻辑关系（and/or，默认为and）
- `--count_only`: 仅返回匹配数量（true/false，默认为false）
- `--output_encoding`: 标准输出 **JSON** 的编码，仅支持 `utf-8`（默认，可写 `utf8`）或 `gbk`。`tsv`/`markdown` 固定为 UTF-8。JSON 请求里也可传字段 `output_encoding`（同样仅这两种）；`output_format` 也可放入 JSON 请求体（与 CLI 一致，会在处理前从请求中弹出）

**标准输入 JSON（管道）与编码**：从 `stdin` 读入时按顺序尝试解码 `utf-8-sig`（带 BOM 的 UTF-8）、`utf-8`、`gbk`。成功结果 JSON 仍由 `output_encoding` 控制写出编码。

**子进程 / 自动化调用**：仅脚本名、无额外参数且 `stdin` 非 TTY 时，工具会 `read()` 全部 stdin。若未向子进程传入任何 stdin 数据且未关闭管道（例如 `subprocess.run` 默认把 stdin 接到空管道），会导致**一直阻塞**。请使用 `stdin=subprocess.DEVNULL`、`input=b''`，或设置环境变量 `TAB_PROCESSOR_READ_STDIN=0`（或 `false`/`no`）跳过读 stdin。

**环境变量（`tab_processor.py`）**：

| 变量 | 作用 | 默认 / 说明 |
|------|------|-------------|
| `TAB_PROCESSOR_READ_STDIN` | 是否尝试读 stdin | `1` 开启；`0` / `false` / `no` 关闭 |
| `TAB_PROCESSOR_AUTO_SLIM` | 是否启用 search 自动瘦身 | 开启；`0` / `false` / `no` / `off` 关闭 |
| `TAB_PROCESSOR_WIDE_MIN_COLUMNS` | 宽表列数阈值（≥ 才可能瘦身） | `40`，范围 clamp 在 1～50000 |
| `TAB_PROCESSOR_SLIM_COLUMNS` | 瘦身时优先返回的列 | 逗号分隔列名；未设置则用内置清单（ID、Name、Title…） |
| `TAB_PROCESSOR_SLIM_FALLBACK` | 优先列在表中均不存在时，取表头前 N 列 | `12`，范围 1～500 |
| `TAB_PROCESSOR_MAX_OUTPUT_CHARS` | 单次 JSON 输出截断上限 | 见 `truncate_response.py`，≥4096 |

PowerShell 示例：`$env:TAB_PROCESSOR_WIDE_MIN_COLUMNS="60"`；临时关闭瘦身：`$env:TAB_PROCESSOR_AUTO_SLIM="0"`。

**用法与解析错误**：帮助信息与参数错误输出在 **stderr**，且按 **UTF-8** 字节写出，避免与 stdout 上的 JSON 二进制混流。

### 多条件搜索（新功能）

工具现在支持多条件组合搜索，可以通过两种方式实现：

#### 方式1：使用简化的 --column 参数
```bash
# 查找 MaxPlayerCount=25 且 Type=1 的记录
python scripts/tab_processor.py --action search --file client/settings/MapList.tab --column MaxPlayerCount=25 --column Type=1

# 查找 MaxPlayerCount=25 或 Type=0 的记录
python scripts/tab_processor.py --action search --file client/settings/MapList.tab --column MaxPlayerCount=25 --column Type=0 --logic or
```

#### 方式2：使用 JSON 格式的 conditions 参数
```bash
# 使用 JSON 格式指定多个条件
python scripts/tab_processor.py --action search --file client/settings/MapList.tab --conditions '[{"columns":["MaxPlayerCount"],"keyword":"25"},{"columns":["Type"],"keyword":"1"}]' --logic and
```

### 统计功能（新功能）

如果只需要知道匹配记录的数量，而不需要具体数据，可以使用 `--count_only` 参数：

```bash
# 统计 25人副本的数量
python scripts/tab_processor.py --action search --file client/settings/MapList.tab --column MaxPlayerCount=25 --column Type=1 --count_only true
```

输出结果：
```json
{
  "total_matches": 29,
  "count_only": true,
  "success": true
}
```

### 详细示例文档

为了帮助你快速入门并高效使用本工具，我们准备了详细的示例文档，位于 `examples` 目录下：

### 示例文档列表

1. **[01_basic_queries.md](./examples/01_basic_queries.md)** - 基础查询示例
   - 查看文件基本信息
   - 简单关键词搜索
   - 指定列搜索
   - 精确匹配数字（全字匹配）
   - 只返回需要的列
   - 分页获取数据
   - 统计匹配数量
   - 基础查询最佳实践

2. **[02_advanced_search.md](./examples/02_advanced_search.md)** - 高级搜索示例
   - 多条件 AND 搜索
   - 多条件 OR 搜索
   - 文本 + 数值 组合搜索
   - 精确数值 + 精确类型
   - 使用 JSON 格式的 conditions
   - 正则表达式搜索
   - 大小写敏感搜索
   - 复杂组合查询
   - 多列搜索同一关键词
   - 统计复杂条件的匹配数
   - 高级搜索最佳实践

3. **[03_data_modification.md](./examples/03_data_modification.md)** - 数据修改示例
   - 添加新行
   - 插入行到指定位置
   - 更新指定行
   - 删除指定行
   - 添加新列
   - 删除列
   - 重命名列
   - 数据修改最佳实践

4. **[04_batch_processing.md](./examples/04_batch_processing.md)** - 批量处理示例
   - 批量查询并处理
   - 批量更新（手动方式）
   - 批量删除（手动方式）
   - 批量导出数据
   - 批量验证数据
   - 批量统计分析
   - 批量处理最佳实践

5. **[05_common_scenarios.md](./examples/05_common_scenarios.md)** - 常见场景示例
   - 查询副本信息
   - 查找特定副本
   - 统计副本类型分布
   - 查找包含特定关键词的副本
   - 查找特定人数范围的副本
   - 批量导出副本数据
   - 验证数据完整性
   - 查找配置错误
   - 按名称模糊搜索
   - 批量修改副本类型
   - 常见场景速查表

### 如何使用示例文档

**推荐学习路径**：
1. 先阅读 [01_basic_queries.md](./examples/01_basic_queries.md) 掌握基础查询功能
2. 再阅读 [02_advanced_search.md](./examples/02_advanced_search.md) 学习高级搜索技巧
3. 根据需要阅读 [03_data_modification.md](./examples/03_data_modification.md) 或 [04_batch_processing.md](./examples/04_batch_processing.md)
4. 最后阅读 [05_common_scenarios.md](./examples/05_common_scenarios.md) 了解实际应用场景

**快速查找**：
- 如果你是第一次使用，从 [01_basic_queries.md](./examples/01_basic_queries.md) 开始
- 如果需要解决特定问题，查看 [05_common_scenarios.md](./examples/05_common_scenarios.md) 的速查表
- 如果需要批量操作，查看 [04_batch_processing.md](./examples/04_batch_processing.md)
- 如果需要修改数据，查看 [03_data_modification.md](./examples/03_data_modification.md)

**示例文档特点**：
- 每个示例都包含实际场景和解决方案
- 提供完整的命令和输出示例
- 包含使用建议和注意事项
- 提供最佳实践和常见问题解答

## 实用示例集合

#### 示例1：查询特定类型的副本数量
**场景**：查询 MapList.tab 中有多少个25人副本

```bash
# 步骤1：先查看文件结构，了解有哪些列
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action get_table_info --file client/settings/MapList.tab

# 步骤2：使用多条件搜索，精确匹配25人副本
# 注意：使用 --whole_word true 避免匹配到 2500 这样的值
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column MaxPlayerCount=25 --column Type=1 --count_only true

# 步骤3：获取副本的详细信息
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column MaxPlayerCount=25 --column Type=1 --return_columns ID,Name,DisplayName
```

#### 示例2：全字匹配的使用场景
**何时必须使用全字匹配**：

1. **数字精确匹配**：搜索 "25" 时，如果不使用全字匹配，会匹配到 "2500"、"251"、"125" 等
   ```bash
   # 错误：会匹配到 MaxPlayerCount=2500 的记录
   python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column MaxPlayerCount --keyword 25

   # 正确：只匹配 MaxPlayerCount=25 的记录
   python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column MaxPlayerCount --keyword 25 --whole_word true
   ```

2. **ID精确匹配**：搜索 "10" 时，避免匹配到 "100"、"1010"、"210" 等
   ```bash
   python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column ID --keyword 10 --whole_word true
   ```

3. **类型代码精确匹配**：搜索 "1" 时，避免匹配到 "10"、"11"、"21" 等
   ```bash
   python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column Type --keyword 1 --whole_word true
   ```

**何时不需要使用全字匹配**：
- 搜索文本内容，如 "英雄"（可以匹配 "英雄战宝迦兰"、"英雄大明宫" 等）
- 搜索名称的一部分，如 "荻花"（可以匹配 "荻花宫后山"、"荻花圣殿" 等）

#### 示例3：高效的三步查询流程
**场景**：快速了解某个配置文件的内容

```bash
# 步骤1：快速统计（使用 count_only）
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column Type=1 --count_only true
# 输出：{"total_matches": 156, "count_only": true, "success": true}

# 步骤2：获取前几条记录，了解数据结构
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column Type=1 --return_columns ID,Name,DisplayName,MaxPlayerCount --limit 5

# 步骤3：如果需要更多数据，使用分页
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column Type=1 --return_columns ID,Name,DisplayName --start_index 5 --limit 10
```

#### 示例4：组合条件的高级搜索
**场景**：查找满足多个条件的记录

```bash
# 查找 25人副本 且 Type=1 的记录
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column MaxPlayerCount=25 --column Type=1

# 查找 25人副本 或 Type=0 的记录
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column MaxPlayerCount=25 --column Type=0 --logic or

# 查找名称包含"英雄"且人数为25的副本
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column Name=英雄 --column MaxPlayerCount=25
```

#### 示例5：处理大文件的技巧
**场景**：文件有上万行，需要高效查询

```bash
# 技巧1：始终使用 count_only 先了解数据量
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --keyword "关键词" --count_only true

# 技巧2：只返回需要的列，减少数据传输
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --keyword "关键词" --return_columns ID,Name

# 技巧3：使用分页逐步获取数据
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --keyword "关键词" --limit 50 --start_index 0
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --keyword "关键词" --limit 50 --start_index 50
```

### 编程接口使用方式

#### 1. 获取文件信息
获取tab文件的基本信息，包括列名、行数、列类型等。

**适用场景**：首次查看文件，了解文件结构

#### 2. 搜索数据
在文件中搜索包含关键词的行，支持多种搜索选项。

**搜索选项**：
- 正则表达式搜索
- 全字匹配
- 大小写敏感
- 指定列搜索
- 多条件组合（与/或关系）
- 分页返回结果

**适用场景**：查找特定配置项、筛选数据

#### 3. 读取指定行和列
按行号和列名读取数据，支持分页。

**特点**：
- 精确指定需要的行和列
- 支持分页获取
- 返回原始行号信息

**适用场景**：已知行号，需要获取特定数据

#### 4. 获取指定行的列数据
获取指定行的列数据，支持多种列选择方式。

**列选择方式**：
- 指定列名列表
- 按条件过滤列名（正则、通配符、全字匹配）
- 按列范围选择
- 按列索引选择
- 过滤空值列

**适用场景**：列数特别多，需要按需获取列数据

#### 5. 数据修改
支持添加、插入、更新、删除行和列。

**适用场景**：修改配置文件、更新数据

## 使用建议

### 1. 大文件处理
对于大文件，建议：
- 使用搜索功能而不是读取全部数据
- 使用分页功能逐步获取数据
- 指定需要的列，减少数据量

### 2. 列数特别多的情况
当列数达到几百列时，建议：
- 使用 `get_row_columns` 工具
- 按条件选择需要的列
- 使用分页功能逐步获取列数据

### 3. 搜索优化
为了提高搜索效率：
- 使用更精确的搜索条件
- 指定搜索列，减少搜索范围
- 使用正则表达式进行复杂匹配

### 4. 编码处理
工具已内置GBK编码处理，但需要注意：
- 确保文件确实是GBK编码
- 处理非法字符时会自动替换
- 输出结果使用UTF-8编码

## 常见问题和最佳实践

### Q1: 为什么搜索数字时会匹配到不相关的记录？
**问题**：搜索 `MaxPlayerCount=25` 时，会匹配到 `2500` 的记录。

**原因**：默认的搜索是包含匹配，"25" 是 "2500" 的子串。

**解决方案**：使用 `--whole_word true` 参数进行全字匹配。
```bash
# 错误
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column MaxPlayerCount --keyword 25

# 正确
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column MaxPlayerCount --keyword 25 --whole_word true
```

**最佳实践**：搜索数字、ID、类型代码等精确值时，始终使用 `--whole_word true`。

### Q2: 如何快速了解一个配置文件的结构？
**最佳实践**：三步法
```bash
# 步骤1：获取文件基本信息
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action get_table_info --file client/settings/MapList.tab

# 步骤2：统计特定类型的记录数量
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column Type=1 --count_only true

# 步骤3：获取前几条记录查看数据格式
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column Type=1 --limit 5 --return_columns ID,Name,DisplayName
```

### Q3: 输出被截断了怎么办？
**问题**：搜索结果太多，输出被截断，看不到完整数据。

**说明**：`truncate_response.py` 会对单次 JSON 输出做长度上限（默认约 512KB 字符）。仍超限时会出现 `truncated_by_server`。可通过环境变量加大上限，例如 PowerShell：`$env:TAB_PROCESSOR_MAX_OUTPUT_CHARS="2097152"`（最大允许约 50MB，需正整数且 ≥4096）。

**解决方案**：
1. 使用 `--count_only` 先了解总数量
2. 使用 `--limit` 和 `--start_index` 分页获取
3. 使用 `--return_columns` 只返回需要的列
4. 仍不够时设置环境变量 `TAB_PROCESSOR_MAX_OUTPUT_CHARS` 提高上限

```bash
# 步骤1：先统计总数
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column Type=1 --count_only true

# 步骤2：分页获取数据（每页50条）
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column Type=1 --limit 50 --start_index 0
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column Type=1 --limit 50 --start_index 50

# 步骤3：只返回需要的列
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column Type=1 --return_columns ID,Name
```

### Q4: 如何组合多个搜索条件？
**最佳实践**：使用多条件搜索
```bash
# AND 条件：同时满足多个条件
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column MaxPlayerCount=25 --column Type=1

# OR 条件：满足任一条件
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column MaxPlayerCount=25 --column Type=0 --logic or

# 复杂组合：名称包含"英雄" 且 人数为25
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column Name=英雄 --column MaxPlayerCount=25
```

### Q5: 在 Trae IDE 中使用时路径问题
**问题**：在 Trae IDE 中运行时，找不到 scripts 目录。

**解决方案**：使用完整路径
```bash
# 错误
python scripts/tab_processor.py --action get_table_info --file client/settings/MapList.tab

# 正确
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action get_table_info --file client/settings/MapList.tab
```

### Q6: 如何高效处理大量数据？
**最佳实践**：
1. 始终先用 `--count_only` 了解数据量
2. 使用 `--return_columns` 减少数据传输
3. 使用 `--limit` 和 `--start_index` 分页处理
4. 使用 `--column` 指定搜索列，提高搜索效率

```bash
# 高效查询示例
python .trae/skills/tab文件处理专家/scripts/tab_processor.py --action search --file client/settings/MapList.tab --column Type=1 --column MaxPlayerCount=25 --return_columns ID,Name,DisplayName --count_only true
```

## 技术特性

- **GBK编码支持**：自动处理GBK编码的读写
- **大文件友好**：使用行偏移量表实现随机访问
- **流式处理**：写操作通过流式重写，内存占用低
- **智能截断**：自动截断超长响应，提供分页提示
- **错误处理**：完善的异常处理和错误提示
- **分页支持**：所有查询操作都支持分页

## 典型使用流程

### 查看配置文件
1. 使用 `get_table_info` 了解文件结构
2. 使用 `search` 查找需要的配置项
3. 使用 `read_rows` 或 `get_row_columns` 获取详细数据

### 修改配置文件
1. 使用 `get_table_info` 了解文件结构
2. 使用 `search` 找到要修改的行
3. 使用 `update_row` 修改数据
4. 使用 `read_rows` 验证修改结果

### 批量处理
1. 使用 `search` 获取所有需要处理的行号
2. 使用分页功能逐批处理
3. 使用 `update_row` 或其他修改工具更新数据