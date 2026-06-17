---
name: agent-skill-generator
description: |
  用来帮助用户建立agent-skill（agent技能）的工具。
  根据用户的自然语言描述，自动生成符合规范的Skill目录结构和文件。
allowed-tools: powershell, cmd, Edit, Read, Write, RunCommand
---

# Skill生成器使用指南

## 功能介绍
该Skill用于根据用户的自然语言描述，自动生成符合规范的Skill目录结构和文件。用户只需用自然语言描述所需Skill的功能，系统会自动识别Skill类型，创建完整的Skill目录结构、编写SKILL.md文件和相关脚本。

# 所有项目级技能必须严格存放在以下位置：
```
${workspaceFolder}/tools/AITools/SKILLS/
```

## SKILL.md 头部格式规范（重要！）

**SKILL.md文件必须以YAML格式头部开头，这是Skill识别的关键！**

### YAML头部格式

```yaml
---
name: skill-name
description: |
  多行描述内容
  第二行内容
allowed-tools: powershell, cmd, Edit, Read, Write, RunCommand
---
```

### 字段说明

| 字段 | 类型 | 是否必需 | 说明 |
|------|------|----------|------|
| `name` | string | **是** | Skill的唯一名称，使用小写字母、数字和连字符(-)，如 `encoding-converter` |
| `description` | string | **是** | Skill功能的详细描述，支持多行文本（使用 `\|` 符号） |
| `allowed-tools` | string | **是** | 允许使用的工具列表，多个工具用逗号分隔 |

### 描述字段的多行写法

**使用 `\|` 符号表示多行文本：**

```yaml
---
name: dungeon-cooldown-expert
description: |
  副本CD配置专家，同时具备多种角色：
  1. 知识库：回答配置方式和文件路径
  2. 检查器：检查配置文件的正确性
  3. 查询器：查询特定副本的CD时间
  4. 指导器：指导用户完成配置任务
allowed-tools: powershell, cmd, Edit, Read, Write, RunCommand
---
```

### 常见错误

❌ **错误示例1：缺少YAML头部**
```markdown
# Skill名称
## 功能介绍
...
```

❌ **错误示例2：YAML格式不正确**
```yaml
---
name: skill name  # 错误：包含空格
---
```

✅ **正确示例**
```yaml
---
name: encoding-converter
description: |
  批量转换文件编码，支持GBK到UTF-8转换、
  乱码修复、批处理等功能
allowed-tools: powershell, cmd, Edit, Read, Write, RunCommand
---
```

## Skill目录结构规范

生成的Skill必须遵循以下目录结构：

```
skill-name/
├── SKILL.md                    # [必需] Skill定义文件，包含YAML头部和使用指南
├── main.py                     # [可选] 主Python脚本，支持命令行参数
├── xxx_tool.py                 # [可选] 其他Python工具脚本，支持命令行参数
├── examples/                   # [必需] 使用示例和指南目录
│   ├── usage-guide.md          # [必需] Python命令行使用指南
│   ├── scenario-examples.md   # [必需] 使用场景举例
│   ├── usage-scenarios.md      # [必需] 使用场景说明
│   └── efficient-usage.md     # [必需] 最高效的使用方式
├── references/                 # [可选] 参考资料目录
│   └── config-guide.md         # 配置指南等参考文档
└── scripts/                    # [可选] 辅助脚本目录
    └── helper.py               # 辅助脚本（通过命令行传参调用）
```

### 目录说明
- **SKILL.md**：Skill的定义文件，必须包含YAML头部和详细的使用指南
- **main.py / xxx_tool.py**：主要的Python工具脚本，必须支持命令行参数，放在skill根目录
- **examples/**：使用示例和指南，必须包含以下文件：
  - `usage-guide.md`：Python命令行使用指南，详细说明如何通过命令行调用各个脚本
  - `scenario-examples.md`：具体的使用场景举例，展示实际应用案例
  - `usage-scenarios.md`：使用场景说明，解释不同场景下的最佳实践
  - `efficient-usage.md`：最高效的使用方式，提供性能优化建议
- **references/**：参考资料，包含配置指南、FAQ等
- **scripts/**：辅助脚本，用于内部调用，不直接通过命令行使用

## 支持的Skill类型

### 1. 转换器类型 (converter)
用于编码转换、乱码修复、批处理、批量总结、代码文档生成。
**关键词**：转换、编码、乱码、批处理、批量处理、批量总结、文档生成、生成器

### 2. 工具类型 (tool)
用于处理数据的工具，如编辑、修改、导出数据等。
**关键词**：处理、管理、编辑、创建、修改、读取、批量、导出

### 3. 知识库类型 (knowledge_base)
用于回答配置相关问题，提供知识和规则说明。
**关键词**：知识库、文档、回答、查询、解释、说明

### 4. 测试器类型 (tester)
用于测试配置文件和脚本的正确性。
**关键词**：测试、验证、检测、试运行

### 5. 检查器类型 (checker)
用于检查配置文件的正确性和完整性。
**关键词**：检查、校验、审查、核对、排查

### 6. 指导器类型 (guide)
用于指导Agent调用其他Skill或MCP工具。
**关键词**：指导、指引、调用、使用、协助

### 7. 流程专家类型 (planner)
用于指导生成ReAct Agent的工作流程计划。
**关键词**：计划、规划、流程、步骤、方案、ReAct

### 8. 复合型 (hybrid)
同时具备多种角色，如知识库+检查器+查询器+指导器。
**关键词**：专家、复合、多功能、综合

## 生成流程
1. **接收用户需求**：用户用自然语言描述所需Skill的功能
2. **分析需求**：解析用户描述，提取关键信息和Skill类型
3. **生成目录结构**：创建符合规范的Skill目录结构
4. **编写SKILL.md**：根据Skill类型生成相应内容的SKILL.md文件
5. **生成脚本**：根据需要生成相关的Python脚本和参考文件
6. **检查编码**：验证生成文件的编码格式，确保使用UTF-8编码
7. **测试功能正常性**：运行生成的脚本，验证功能是否正常
8. **确认输出目录**：确认Skill已正确生成到指定目录：`${workspaceFolder}/tools/AITools/SKILLS/`

## Python脚本使用规范

### 脚本放置位置
- **主要工具脚本**：必须放在Skill根目录，如 `main.py`、`xxx_tool.py`
- **辅助脚本**：放在 `scripts/` 子目录，仅用于内部调用

### 命令行参数要求
所有放在根目录的Python脚本必须支持命令行参数：

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
脚本功能描述
"""

import argparse

def main():
    parser = argparse.ArgumentParser(description='脚本功能描述')
    parser.add_argument('--input', type=str, required=True, help='输入文件路径')
    parser.add_argument('--output', type=str, help='输出文件路径')
    parser.add_argument('--option', type=str, default='default', help='选项说明')
    args = parser.parse_args()
    
    # 实现功能逻辑
    print(f"处理文件: {args.input}")
    if args.output:
        print(f"输出到: {args.output}")

if __name__ == '__main__':
    main()
```

### 使用方式
```powershell
# 基本用法
python main.py --input data.txt

# 完整用法
python main.py --input data.txt --output result.txt --option value
```

## examples目录内容规范

### 必需文件
examples目录必须包含以下4个文件：

#### 1. usage-guide.md - Python命令行使用指南
详细说明每个Python脚本的命令行参数、使用方法和示例。

**内容结构：**
```markdown
# Python命令行使用指南

## main.py
### 功能说明
### 命令行参数
- `--input`: 输入文件路径（必需）
- `--output`: 输出文件路径（可选）
### 使用示例
```powershell
python main.py --input data.txt
```

## xxx_tool.py
...
```

#### 2. scenario-examples.md - 使用场景举例
展示具体的使用场景和实际应用案例。

**内容结构：**
```markdown
# 使用场景举例

## 场景1：批量处理文件
### 需求
### 解决方案
### 执行命令
### 预期结果

## 场景2：数据转换
...
```

#### 3. usage-scenarios.md - 使用场景说明
解释不同场景下的最佳实践和注意事项。

**内容结构：**
```markdown
# 使用场景说明

## 场景分类
1. 批量处理场景
2. 单文件处理场景
3. 数据转换场景

## 最佳实践
- 场景1的最佳做法
- 场景2的注意事项
```

#### 4. efficient-usage.md - 最高效的使用方式
提供性能优化建议和高效使用技巧。

**内容结构：**
```markdown
# 最高效的使用方式

## 性能优化建议
1. 批量处理技巧
2. 内存优化方法
3. 并行处理建议

## 高效使用技巧
- 技巧1：如何快速完成任务
- 技巧2：如何避免常见陷阱
```

## ReAct工作流程

当使用agent-skill-generator生成新的Skill时，Agent应遵循以下ReAct工作流程：

### 第一步：需求确认
- **确认用户需求**：首先理解用户的自然语言描述，确保没有疑问
- **澄清歧义**：如果描述存在歧义或不明确，主动询问用户澄清
- **工具名候选**：根据需求提供2-3个候选工具名称，例如：
  - 对于乱码修复工具：`garbled-fixer`, `encoding-validator`, `mixed-encoding-repairer`
  - 对于数据处理工具：`data-processor`, `file-converter`, `batch-handler`
- **参数列表**：列出生成Skill所需的参数，征求用户同意：
  - `--name`：Skill名称（必选）
  - `--description`：Skill功能描述（必选）
  - `--output-dir`：输出目录（可选，默认为`${workspaceFolder}/tools/AITools/SKILLS/`）
- **补充意见**：询问用户是否有其他补充意见或特殊要求

### 第二步：生成前确认
- **确认所有参数**：确保用户同意所有参数和工具名称
- **确认输出位置**：明确Skill将生成到`${workspaceFolder}/tools/AITools/SKILLS/`目录
- **最终确认**：询问用户是否准备好开始生成

### 第三步：执行生成
- **运行生成命令**：执行生成脚本，创建Skill目录结构和文件
- **进度跟踪**：实时反馈生成进度

### 第四步：生成后验证
- **编码检查**：验证生成的所有文件（SKILL.md、脚本等）使用UTF-8编码
- **功能测试**：运行生成的脚本，确保基本功能正常
- **结构验证**：检查目录结构是否符合规范
- **YAML头部验证**：确认SKILL.md包含正确的YAML头部

### 第五步：交付与说明
- **输出目录确认**：向用户展示生成的Skill完整路径
- **使用说明**：提供使用新Skill的示例命令
- **后续建议**：建议用户如何进一步定制生成的Skill

## 使用示例

### 示例1：生成转换器类型Skill
**用户输入**：
```
批量转换文件编码，将GBK编码的文件转换为UTF-8编码
```

**生成结果**：
- 类型：`converter`
- 名称：`encoding-converter`
- 包含：
  - SKILL.md（转换器使用指南）
  - main.py（编码转换主脚本，支持命令行参数）
  - fix_garbled.py（乱码修复脚本，支持命令行参数）
  - examples/usage-guide.md（命令行使用指南）
  - examples/scenario-examples.md（使用场景举例）
  - examples/usage-scenarios.md（使用场景说明）
  - examples/efficient-usage.md（最高效使用方式）
  - scripts/helper.py（辅助脚本）

**目录结构**：
```
encoding-converter/
├── SKILL.md
├── main.py
├── fix_garbled.py
├── examples/
│   ├── usage-guide.md
│   ├── scenario-examples.md
│   ├── usage-scenarios.md
│   └── efficient-usage.md
├── references/
└── scripts/
    └── helper.py
```

### 示例2：生成工具类型Skill
**用户输入**：
```
我需要一个处理NPC数据的Skill，能够读取和修改NPC模板文件，支持批量操作。
```

**生成结果**：
- 类型：`tool`
- 名称：`npc-data-processor`
- 包含：
  - SKILL.md（工具使用指南）
  - main.py（NPC数据处理主脚本，支持命令行参数）
  - examples/usage-guide.md（命令行使用指南）
  - examples/scenario-examples.md（使用场景举例）
  - examples/usage-scenarios.md（使用场景说明）
  - examples/efficient-usage.md（最高效使用方式）
  - references/npc-templates.md（NPC模板参考）

**目录结构**：
```
npc-data-processor/
├── SKILL.md
├── main.py
├── examples/
│   ├── usage-guide.md
│   ├── scenario-examples.md
│   ├── usage-scenarios.md
│   └── efficient-usage.md
└── references/
    └── npc-templates.md
```

### 示例3：生成知识库类型Skill
**用户输入**：
```
副本CD配置知识库，用于回答配置方式和文件路径以及潜规则、算法
```

**生成结果**：
- 类型：`knowledge_base`
- 名称：`dungeon-knowledge-base`
- 包含：
  - SKILL.md（知识库使用指南）
  - examples/usage-guide.md（命令行使用指南）
  - examples/scenario-examples.md（使用场景举例）
  - examples/usage-scenarios.md（使用场景说明）
  - examples/efficient-usage.md（最高效使用方式）
  - references/config-guide.md（配置指南）
  - references/faq.md（常见问题）

**目录结构**：
```
dungeon-knowledge-base/
├── SKILL.md
├── examples/
│   ├── usage-guide.md
│   ├── scenario-examples.md
│   ├── usage-scenarios.md
│   └── efficient-usage.md
└── references/
    ├── config-guide.md
    └── faq.md
```

### 示例4：生成测试器类型Skill
**用户输入**：
```
测试配置文件和脚本写法是否正确的测试器
```

**生成结果**：
- 类型：`tester`
- 名称：`config-tester`
- 包含：
  - SKILL.md（测试器使用指南）
  - main.py（测试主脚本，支持命令行参数）
  - examples/usage-guide.md（命令行使用指南）
  - examples/scenario-examples.md（使用场景举例）
  - examples/usage-scenarios.md（使用场景说明）
  - examples/efficient-usage.md（最高效使用方式）

**目录结构**：
```
config-tester/
├── SKILL.md
├── main.py
├── examples/
│   ├── usage-guide.md
│   ├── scenario-examples.md
│   ├── usage-scenarios.md
│   └── efficient-usage.md
```

### 示例5：生成检查器类型Skill
**用户输入**：
```
检查配置文件是否正确，比较相互之间的关系，找出有问题的部分
```

**生成结果**：
- 类型：`checker`
- 名称：`config-checker`
- 包含：
  - SKILL.md（检查器使用指南）
  - main.py（检查主脚本，支持命令行参数）
  - examples/usage-guide.md（命令行使用指南）
  - examples/scenario-examples.md（使用场景举例）
  - examples/usage-scenarios.md（使用场景说明）
  - examples/efficient-usage.md（最高效使用方式）

**目录结构**：
```
config-checker/
├── SKILL.md
├── main.py
├── examples/
│   ├── usage-guide.md
│   ├── scenario-examples.md
│   ├── usage-scenarios.md
│   └── efficient-usage.md
```

### 示例6：生成指导器类型Skill
**用户输入**：
```
指导agent去调用别的skill或者mcp的指导器
```

**生成结果**：
- 类型：`guide`
- 名称：`skill-guide`
- 包含：
  - SKILL.md（指导器使用指南，包含工具调用指南）
  - examples/usage-guide.md（命令行使用指南）
  - examples/scenario-examples.md（使用场景举例）
  - examples/usage-scenarios.md（使用场景说明）
  - examples/efficient-usage.md（最高效使用方式）

**目录结构**：
```
skill-guide/
├── SKILL.md
└── examples/
    ├── usage-guide.md
    ├── scenario-examples.md
    ├── usage-scenarios.md
    └── efficient-usage.md
```

### 示例7：生成流程专家类型Skill
**用户输入**：
```
根据固定下来的经验，指导生成一个ReAct的Agent的工作流程的计划
```

**生成结果**：
- 类型：`planner`
- 名称：`workflow-planner`
- 包含：
  - SKILL.md（流程专家使用指南，包含ReAct流程模板）
  - examples/usage-guide.md（命令行使用指南）
  - examples/scenario-examples.md（使用场景举例）
  - examples/usage-scenarios.md（使用场景说明）
  - examples/efficient-usage.md（最高效使用方式）

**目录结构**：
```
workflow-planner/
├── SKILL.md
└── examples/
    ├── usage-guide.md
    ├── scenario-examples.md
    ├── usage-scenarios.md
    └── efficient-usage.md
```

### 示例8：生成复合型Skill
**用户输入**：
```
副本CD配置专家，可以是知识库、检查器、查询器和指导器
```

**生成结果**：
- 类型：`hybrid`
- 名称：`dungeon-cooldown-expert`
- 包含：
  - SKILL.md（复合型专家使用指南）
  - main.py（查询主脚本，支持命令行参数）
  - check_config.py（检查脚本，支持命令行参数）
  - examples/usage-guide.md（命令行使用指南）
  - examples/scenario-examples.md（使用场景举例）
  - examples/usage-scenarios.md（使用场景说明）
  - examples/efficient-usage.md（最高效使用方式）
  - references/dungeon-config-guide.md（副本配置指南）

**目录结构**：
```
dungeon-cooldown-expert/
├── SKILL.md
├── main.py
├── check_config.py
├── examples/
│   ├── usage-guide.md
│   ├── scenario-examples.md
│   ├── usage-scenarios.md
│   └── efficient-usage.md
└── references/
    └── dungeon-config-guide.md
```

## 技术实现

### 核心功能
- 解析自然语言描述，提取Skill名称和功能
- 生成符合规范的目录结构
- 自动编写SKILL.md文件，包含YAML头部和详细说明
- 根据需要生成Python脚本

### 实现细节
- 使用Python脚本实现目录创建和文件生成
- 支持自定义Skill名称和功能描述
- 生成的文件采用UTF-8编码
- 严格遵循Skill开发规范

## YAML格式定义

生成的Skill使用标准的YAML头部格式，每个Skill的SKILL.md文件必须包含以下YAML头部：

### 基本格式
```yaml
---
name: skill-name
description: Skill功能的详细描述
allowed-tools: powershell, cmd, Edit, Read, Write, RunCommand
---
```

### 完整示例
```yaml
---
name: dungeon-cooldown-expert
description: |
  副本CD配置专家，用于：
  1. 回答副本CD配置方式和文件路径
  2. 检查配置文件的正确性和完整性
  3. 查询特定副本的CD时间
  4. 指导用户完成配置任务
allowed-tools: powershell, cmd, Edit, Read, Write, RunCommand
---
```

### 字段说明
| 字段 | 类型 | 是否必需 | 说明 |
|------|------|----------|------|
| `name` | string | 是 | Skill的唯一名称，使用小写字母、数字和连字符(-) |
| `description` | string | 是 | Skill功能的详细描述，支持多行文本（使用`\|`） |
| `allowed-tools` | string | 是 | 允许使用的工具列表，多个工具用逗号分隔 |

### 各类型Skill的YAML示例

#### 转换器类型 (converter)
```yaml
---
name: encoding-converter
description: 批量转换文件编码，支持GBK到UTF-8转换、乱码修复、批处理等功能
allowed-tools: powershell, cmd, Edit, Read, Write, RunCommand
---
```

#### 工具类型 (tool)
```yaml
---
name: npc-data-processor
description: 处理NPC数据的工具，能够读取和修改NPC模板文件，支持批量操作
allowed-tools: powershell, cmd, Edit, Read, Write, RunCommand
---
```

#### 知识库类型 (knowledge_base)
```yaml
---
name: dungeon-knowledge-base
description: 副本CD配置知识库，用于回答配置方式和文件路径以及潜规则、算法
allowed-tools: powershell, cmd, Edit, Read, Write, RunCommand
---
```

#### 测试器类型 (tester)
```yaml
---
name: config-tester
description: 测试配置文件和脚本写法是否正确的测试器
allowed-tools: powershell, cmd, Edit, Read, Write, RunCommand
---
```

#### 检查器类型 (checker)
```yaml
---
name: config-checker
description: 检查配置文件是否正确，比较相互之间的关系，找出有问题的部分
allowed-tools: powershell, cmd, Edit, Read, Write, RunCommand
---
```

#### 指导器类型 (guide)
```yaml
---
name: skill-guide
description: 指导agent去调用别的skill或者mcp的指导器
allowed-tools: powershell, cmd, Edit, Read, Write, RunCommand
---
```

#### 流程专家类型 (planner)
```yaml
---
name: workflow-planner
description: 根据固定下来的经验，指导生成一个ReAct的Agent的工作流程的计划
allowed-tools: powershell, cmd, Edit, Read, Write, RunCommand
---
```

#### 复合型 (hybrid)
```yaml
---
name: dungeon-cooldown-expert
description: |
  副本CD配置专家，同时具备多种角色：
  1. 知识库：回答配置方式和文件路径
  2. 检查器：检查配置文件的正确性
  3. 查询器：查询特定副本的CD时间
  4. 指导器：指导用户完成配置任务
allowed-tools: powershell, cmd, Edit, Read, Write, RunCommand
---
```

## 注意事项
1. **命名规范**：Skill目录名应使用小写字母、数字和连字符(-)
2. **编码规范**：SKILL.md和脚本文件使用UTF-8编码
3. **目录结构**：严格按照规范创建目录结构
4. **YAML头部**：确保包含name、description和allowed-tools字段

## 示例命令

### 生成新Skill
```powershell
# 生成一个名为npc-editor的Skill
python scripts/generate_skill.py -n "npc-editor" -d "用于编辑NPC数据的工具"

# 生成一个名为item-manager的Skill
python scripts/generate_skill.py -n "item-manager" -d "用于管理物品数据的工具"
```

## 输入输出示例

#### 输入：
```
我需要一个处理任务数据的Skill，能够添加新任务和修改任务属性。
```

#### 输出：
```
正在生成skill: quest-data-processor
创建目录结构...
编写SKILL.md文件...
生成脚本文件...
Skill生成完成！
```

## 常见问题

### Q: 生成的Skill目录结构不符合规范怎么办？
A: 请检查输入的描述是否清晰，系统会根据描述自动生成符合规范的目录结构。

### Q: 生成的SKILL.md文件内容不完整怎么办？
A: 请提供更详细的功能描述，系统会根据描述生成更完整的SKILL.md文件。

### Q: 如何修改生成的Skill？
A: 可以直接编辑生成的文件，或者重新运行生成命令并提供更详细的描述。
