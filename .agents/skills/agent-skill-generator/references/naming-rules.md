# Skill命名规范

## 说明
本文件定义了agent-skill-generator生成Skill时的命名规则和约定。

## Skill名称生成规则

### 基本格式
```
[数据类型]-[类型后缀]
```

### 数据类型映射
| 关键词 | 英文映射 | 示例 |
|--------|---------|------|
| 玩家 | player | player-tool |
| 数据 | data | data-processor |
| NPC | npc | npc-editor |
| 技能 | skill | skill-manager |
| 任务 | quest | quest-creator |
| 物品 | item | item-editor |
| 属性 | attribute | attribute-checker |
| 副本 | dungeon | dungeon-knowledge-base |
| CD | cooldown | cooldown-expert |
| 配置 | config | config-tester |
| 脚本 | script | script-validator |
| 文件 | file | file-reader |
| 编码 | encoding | encoding-converter |
| 乱码 | garbled | garbled-fixer |
| 代码 | code | code-doc-generator |
| 文档 | doc | doc-generator |

### 类型后缀映射
| Skill类型 | 后缀 | 示例 |
|----------|------|------|
| converter | converter | encoding-converter |
| tool | tool | player-tool |
| knowledge_base | knowledge-base | dungeon-knowledge-base |
| tester | tester | config-tester |
| checker | checker | config-checker |
| guide | guide | skill-guide |
| planner | planner | workflow-planner |
| hybrid | expert | dungeon-cooldown-expert |

## 命名规范要求

### 1. 字符限制
- 只允许使用小写字母、数字和连字符(-)
- 不允许使用空格、下划线或其他特殊字符
- 连字符只能用于分隔单词，不能在开头或结尾

### 2. 长度限制
- 建议长度：10-50个字符
- 最小长度：3个字符
- 最大长度：100个字符

### 3. 唯一性
- Skill名称在SKILLS目录下必须唯一
- 如果名称冲突，会添加时间戳后缀

### 4. 可读性
- 使用有意义的单词组合
- 避免使用缩写或缩写词
- 保持名称描述性和一致性

## 特殊情况处理

### 无数据类型匹配
当描述中没有匹配的数据类型时：
- 使用类型前缀 + 时间戳
- 示例：`tool-1773637207`

### 时间戳格式
- 使用Unix时间戳（秒）
- 确保名称唯一性
- 示例：`guide-1773637207`

## 示例

### 正确示例
- `player-data-processor`
- `dungeon-cooldown-expert`
- `config-tester`
- `workflow-planner`
- `encoding-converter`
- `code-doc-generator`

### 错误示例
- `PlayerDataProcessor`（大写字母）
- `player_data_processor`（使用下划线）
- `player data processor`（使用空格）
- `player-data-processor-`（结尾有连字符）
