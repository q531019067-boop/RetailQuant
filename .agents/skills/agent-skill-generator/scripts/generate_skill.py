#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Skill生成器脚本
根据用户的自然语言描述，自动生成符合规范的Skill目录结构和文件
"""

import os
import re
import argparse
import sys
from pathlib import Path

# 处理命令行参数编码
def get_encoded_arg(arg):
    if isinstance(arg, bytes):
        try:
            # 尝试GBK编码（Windows默认）
            return arg.decode('gbk', errors='replace')
        except:
            #  fallback到utf-8
            return arg.decode('utf-8', errors='replace')
    return arg


def parse_description(description):
    """
    解析用户的自然语言描述，提取Skill名称、类型和功能
    :param description: 用户的自然语言描述
    :return: (skill_name, skill_description, skill_type)
    """
    import re
    import time
    
    # 定义Skill类型及其关键词（注意：hybrid类型需要放在前面，因为"专家"关键词优先级较高）
    skill_types = {
        'hybrid': {
            'keywords': ['专家', '复合', '多功能', '综合'],
            'prefix': 'expert',
            'name_suffix': 'expert'
        },
        'converter': {
            'keywords': ['转换', '编码', '乱码', '批处理', '批量处理', '批量总结', '文档生成', '生成器'],
            'prefix': 'converter',
            'name_suffix': 'converter'
        },
        'knowledge_base': {
            'keywords': ['知识库', '文档', '回答', '查询', '解释', '说明'],
            'prefix': 'kb',
            'name_suffix': 'knowledge-base'
        },
        'tester': {
            'keywords': ['测试', '验证', '检测', '试运行'],
            'prefix': 'test',
            'name_suffix': 'tester'
        },
        'checker': {
            'keywords': ['检查', '校验', '审查', '核对', '排查'],
            'prefix': 'check',
            'name_suffix': 'checker'
        },
        'guide': {
            'keywords': ['指导', '指引', '调用', '使用', '协助'],
            'prefix': 'guide',
            'name_suffix': 'guide'
        },
        'planner': {
            'keywords': ['计划', '规划', '流程', '步骤', '方案', 'ReAct'],
            'prefix': 'plan',
            'name_suffix': 'planner'
        },
        'tool': {
            'keywords': ['处理', '管理', '编辑', '创建', '修改', '读取', '批量', '导出'],
            'prefix': 'tool',
            'name_suffix': 'tool'
        }
    }
    
    # 常见的数据类型关键词
    data_keywords = {
        '玩家': 'player',
        '数据': 'data',
        'NPC': 'npc',
        '技能': 'skill',
        '任务': 'quest',
        '物品': 'item',
        '属性': 'attribute',
        '副本': 'dungeon',
        'CD': 'cooldown',
        '配置': 'config',
        '脚本': 'script',
        '文件': 'file',
        '编码': 'encoding',
        '乱码': 'garbled',
        '代码': 'code',
        '文档': 'doc'
    }
    
    # 检测Skill类型
    detected_type = None
    for skill_type, config in skill_types.items():
        for keyword in config['keywords']:
            if keyword in description:
                detected_type = skill_type
                break
        if detected_type:
            break
    
    # 如果没有检测到类型，默认为tool
    if not detected_type:
        detected_type = 'tool'
    
    # 提取数据类型关键词
    data_match = None
    for keyword, english in data_keywords.items():
        if keyword in description:
            data_match = english
            break
    
    # 生成skill名称
    type_config = skill_types[detected_type]
    if data_match:
        skill_name = f"{data_match}-{type_config['name_suffix']}"
    else:
        # 如果没有提取到数据类型，使用时间戳
        timestamp = int(time.time())
        skill_name = f"{type_config['prefix']}-{timestamp}"
    
    # 确保名称符合规范
    skill_name = re.sub(r'[^a-z0-9-]', '', skill_name)
    
    # 确保名称不为空
    if not skill_name:
        skill_name = 'auto-generated-skill'
    
    return skill_name, description, detected_type


def create_skill_structure(skill_name, skill_description, skill_type='tool'):
    """
    创建Skill目录结构和文件
    :param skill_name: Skill名称
    :param skill_description: Skill描述
    :param skill_type: Skill类型
    :return: 生成的目录路径
    """
    # 获取工作目录
    workspace_folder = Path(os.getcwd()).parent.parent.parent
    skill_dir = workspace_folder / 'SKILLS' / skill_name
    
    # 创建目录结构
    (skill_dir / 'scripts').mkdir(parents=True, exist_ok=True)
    (skill_dir / 'examples').mkdir(parents=True, exist_ok=True)
    (skill_dir / 'references').mkdir(parents=True, exist_ok=True)
    
    # 生成examples目录的必需文件
    generate_examples_files(skill_dir, skill_name, skill_description, skill_type)
    
    # 根据Skill类型生成不同的内容
    if skill_type == 'converter':
        generate_converter_skill(skill_dir, skill_name, skill_description)
    elif skill_type == 'knowledge_base':
        generate_knowledge_base_skill(skill_dir, skill_name, skill_description)
    elif skill_type == 'tester':
        generate_tester_skill(skill_dir, skill_name, skill_description)
    elif skill_type == 'checker':
        generate_checker_skill(skill_dir, skill_name, skill_description)
    elif skill_type == 'guide':
        generate_guide_skill(skill_dir, skill_name, skill_description)
    elif skill_type == 'planner':
        generate_planner_skill(skill_dir, skill_name, skill_description)
    elif skill_type == 'hybrid':
        generate_hybrid_skill(skill_dir, skill_name, skill_description)
    else:
        # 默认生成工具类型Skill
        generate_tool_skill(skill_dir, skill_name, skill_description)
    
    return skill_dir


def generate_examples_files(skill_dir, skill_name, skill_description, skill_type):
    """
    生成examples目录的必需文件
    :param skill_dir: Skill目录
    :param skill_name: Skill名称
    :param skill_description: Skill描述
    :param skill_type: Skill类型
    """
    examples_dir = skill_dir / 'examples'
    
    # 1. 生成 usage-guide.md - Python命令行使用指南
    usage_guide_content = generate_usage_guide_content(skill_name, skill_description, skill_type)
    with open(examples_dir / 'usage-guide.md', 'w', encoding='utf-8') as f:
        f.write(usage_guide_content)
    
    # 2. 生成 scenario-examples.md - 使用场景举例
    scenario_examples_content = generate_scenario_examples_content(skill_name, skill_description, skill_type)
    with open(examples_dir / 'scenario-examples.md', 'w', encoding='utf-8') as f:
        f.write(scenario_examples_content)
    
    # 3. 生成 usage-scenarios.md - 使用场景说明
    usage_scenarios_content = generate_usage_scenarios_content(skill_name, skill_description, skill_type)
    with open(examples_dir / 'usage-scenarios.md', 'w', encoding='utf-8') as f:
        f.write(usage_scenarios_content)
    
    # 4. 生成 efficient-usage.md - 最高效的使用方式
    efficient_usage_content = generate_efficient_usage_content(skill_name, skill_description, skill_type)
    with open(examples_dir / 'efficient-usage.md', 'w', encoding='utf-8') as f:
        f.write(efficient_usage_content)


def generate_usage_guide_content(skill_name, skill_description, skill_type):
    """
    生成usage-guide.md的内容
    """
    content = f"""# Python命令行使用指南

本指南详细说明{skill_name}的Python脚本如何通过命令行参数使用。

## 概述
{skill_name}：{skill_description}
类型：{skill_type}

## 脚本列表

"""
    
    # 根据不同类型生成不同的脚本说明
    if skill_type == 'converter':
        content += """### main.py - 编码转换工具
**功能说明**：批量转换文件编码格式

**命令行参数**：
- `--input`: 输入文件路径（必需）
- `--dir`: 输入目录路径（与--input二选一）
- `--from`: 源编码格式，默认为gbk
- `--to`: 目标编码格式，默认为utf-8
- `--output-dir`: 输出目录，默认为输入目录下的converted子目录

**使用示例**：
```powershell
# 转换单个文件
python main.py --input data.txt --from gbk --to utf-8

# 批量转换目录
python main.py --dir ./data --from gbk --to utf-8 --output-dir ./converted
```

### fix_garbled.py - 乱码修复工具
**功能说明**：智能修复文件中的乱码内容

**命令行参数**：
- `--input`: 输入文件路径（必需）
- `--encoding`: 文件编码，默认为utf-8
- `--output`: 输出文件路径，默认为覆盖原文件

**使用示例**：
```powershell
# 修复乱码文件
python fix_garbled.py --input garbled.txt --encoding utf-8

# 修复并输出到新文件
python fix_garbled.py --input garbled.txt --encoding utf-8 --output fixed.txt
```

### batch_process.py - 批处理工具
**功能说明**：按照固定工作流批量处理文件

**命令行参数**：
- `--config`: 工作流配置文件路径（必需）
- `--input`: 输入目录路径（必需）
- `--output`: 输出目录路径（可选）

**使用示例**：
```powershell
# 执行批处理任务
python batch_process.py --config workflow.json --input ./data --output ./result
```
"""
    elif skill_type == 'tool':
        content += """### main.py - 数据处理工具
**功能说明**：处理相关数据，支持读取、修改、批量操作

**命令行参数**：
- `--input`: 输入文件路径（必需）
- `--output`: 输出文件路径（可选）
- `--action`: 操作类型，如read/write/update（必需）
- `--filter`: 过滤条件（可选）

**使用示例**：
```powershell
# 读取数据
python main.py --input data.txt --action read

# 修改数据
python main.py --input data.txt --action update --output new_data.txt

# 批量处理
python main.py --input ./data --action batch --filter "type=1"
```
"""
    elif skill_type == 'tester':
        content += """### main.py - 测试工具
**功能说明**：测试配置文件和脚本的正确性

**命令行参数**：
- `--target`: 测试目标，如config/script/all（可选，默认为all）
- `--verbose`: 显示详细输出（可选）

**使用示例**：
```powershell
# 测试所有内容
python main.py

# 测试配置文件
python main.py --target config

# 显示详细输出
python main.py --target config --verbose
```
"""
    elif skill_type == 'checker':
        content += """### main.py - 检查工具
**功能说明**：检查配置文件的正确性和完整性

**命令行参数**：
- `--file`: 要检查的文件路径（可选）
- `--dir`: 要检查的目录路径（可选）
- `--strict`: 严格模式，检查所有规则（可选）

**使用示例**：
```powershell
# 检查单个文件
python main.py --file config.yaml

# 检查整个目录
python main.py --dir ./config

# 严格模式检查
python main.py --dir ./config --strict
```
"""
    elif skill_type == 'knowledge_base':
        content += """注意：知识库类型Skill主要通过SKILL.md中的知识内容提供帮助，不需要命令行工具。

如需查询特定信息，请参考SKILL.md中的核心知识和使用指南部分。
"""
    elif skill_type == 'guide':
        content += """注意：指导器类型Skill主要通过SKILL.md中的指导内容提供帮助，不需要命令行工具。

如需指导信息，请参考SKILL.md中的使用指南部分。
"""
    elif skill_type == 'planner':
        content += """注意：流程专家类型Skill主要通过SKILL.md中的流程模板提供帮助，不需要命令行工具。

如需流程规划，请参考SKILL.md中的流程模板部分。
"""
    elif skill_type == 'hybrid':
        content += """### main.py - 查询工具
**功能说明**：查询相关配置和数据

**命令行参数**：
- `--query`: 查询内容（必需）
- `--type`: 查询类型（可选）

**使用示例**：
```powershell
# 查询配置
python main.py --query "副本CD配置"

# 指定类型查询
python main.py --query "副本CD配置" --type config
```

### check_config.py - 检查工具
**功能说明**：检查配置文件的正确性

**命令行参数**：
- `--file`: 要检查的文件路径（必需）
- `--strict`: 严格模式（可选）

**使用示例**：
```powershell
# 检查配置文件
python check_config.py --file config.yaml

# 严格模式检查
python check_config.py --file config.yaml --strict
```
"""
    else:
        content += """### main.py - 主工具
**功能说明**：{skill_description}

**命令行参数**：
- `--input`: 输入文件路径（必需）
- `--output`: 输出文件路径（可选）

**使用示例**：
```powershell
# 基本使用
python main.py --input data.txt

# 指定输出
python main.py --input data.txt --output result.txt
```
"""
    
    content += """
## 常见问题

### Q1: 如何查看帮助信息？
**A**: 使用 `--help` 参数查看完整的帮助信息：
```powershell
python main.py --help
```

### Q2: 参数中的路径需要引号吗？
**A**: 如果路径包含空格，需要使用引号：
```powershell
python main.py --input "my data.txt"
```

### Q3: 如何批量处理多个文件？
**A**: 使用 `--dir` 参数指定目录，工具会自动处理目录下的所有文件：
```powershell
python main.py --dir ./data
```
"""
    
    return content


def generate_scenario_examples_content(skill_name, skill_description, skill_type):
    """
    生成scenario-examples.md的内容
    """
    content = f"""# 使用场景举例

本文档展示{skill_name}的具体使用场景和实际应用案例。

## 场景概述
{skill_name}：{skill_description}
类型：{skill_type}

"""
    
    # 根据不同类型生成不同的场景举例
    if skill_type == 'converter':
        content += """## 场景1：批量转换GBK文件为UTF-8

### 需求
项目中有大量历史数据文件使用GBK编码，需要全部转换为UTF-8编码以支持国际化。

### 解决方案
使用main.py工具批量转换编码。

### 执行命令
```powershell
python main.py --dir ./data --from gbk --to utf-8 --output-dir ./data_utf8
```

### 预期结果
- 扫描./data目录下所有文件
- 检测每个文件的编码
- 将GBK编码文件转换为UTF-8
- 输出到./data_utf8目录
- 显示转换统计信息

---

## 场景2：修复混合编码文件

### 需求
某个文件中存在混合编码，部分内容显示为乱码，需要修复。

### 解决方案
使用fix_garbled.py工具智能修复乱码。

### 执行命令
```powershell
python fix_garbled.py --input mixed_encoding.txt --encoding utf-8
```

### 预期结果
- 分段读取文件内容
- 利用AI识别乱码位置
- 自动修复乱码内容
- 保存修复后的文件

---

## 场景3：按照工作流批量处理

### 需求
需要按照固定的流程批量处理文件：读取->转换->验证->输出。

### 解决方案
使用batch_process.py工具执行工作流。

### 执行命令
```powershell
python batch_process.py --config workflow.json --input ./raw_data --output ./processed_data
```

### 预期结果
- 加载工作流配置
- 按照配置的步骤处理文件
- 每步处理完成后进行验证
- 输出最终结果
"""
    elif skill_type == 'tool':
        content += """## 场景1：读取并分析数据

### 需求
需要读取数据文件并分析其中的内容。

### 解决方案
使用main.py工具读取数据。

### 执行命令
```powershell
python main.py --input data.txt --action read
```

### 预期结果
- 读取数据文件
- 解析数据结构
- 显示分析结果

---

## 场景2：批量修改数据

### 需求
需要批量修改数据文件中的某些字段。

### 解决方案
使用main.py工具批量修改。

### 执行命令
```powershell
python main.py --input ./data --action batch --filter "type=1" --output ./updated_data
```

### 预期结果
- 扫描数据目录
- 根据过滤条件筛选文件
- 批量修改指定字段
- 输出修改后的数据
"""
    elif skill_type == 'checker':
        content += """## 场景1：检查单个配置文件

### 需求
需要检查某个配置文件是否正确。

### 解决方案
使用main.py工具检查配置。

### 执行命令
```powershell
python main.py --file config.yaml
```

### 预期结果
- 解析配置文件
- 检查语法正确性
- 验证数据完整性
- 显示检查结果

---

## 场景2：批量检查配置目录

### 需求
需要检查整个配置目录下的所有文件。

### 解决方案
使用main.py工具批量检查。

### 执行命令
```powershell
python main.py --dir ./config
```

### 预期结果
- 扫描配置目录
- 检查每个配置文件
- 汇总检查结果
- 标记问题文件
"""
    elif skill_type == 'tester':
        content += """## 场景1：测试配置文件

### 需求
需要测试配置文件是否可以正常加载和使用。

### 解决方案
使用main.py工具测试配置。

### 执行命令
```powershell
python main.py --target config
```

### 预期结果
- 加载配置文件
- 验证配置语法
- 测试配置逻辑
- 输出测试结果

---

## 场景2：完整测试

### 需求
需要进行完整的测试，包括配置、脚本等。

### 解决方案
使用main.py工具进行完整测试。

### 执行命令
```powershell
python main.py
```

### 预期结果
- 测试所有组件
- 显示详细测试信息
- 生成测试报告
"""
    elif skill_type == 'knowledge_base':
        content += """## 场景1：查询配置信息

### 需求
需要了解某个配置的详细信息和规则。

### 解决方案
参考SKILL.md中的核心知识和配置指南。

### 使用方式
1. 查看SKILL.md的"核心知识"部分
2. 查看references/config-guide.md
3. 根据关键词搜索相关信息

---

## 场景2：理解配置规则

### 需求
需要理解配置文件中的规则和约束。

### 解决方案
参考SKILL.md中的配置规则说明。

### 使用方式
1. 查看SKILL.md的"配置规则"部分
2. 查看references/faq.md
3. 结合实际配置示例理解
"""
    elif skill_type == 'guide':
        content += """## 场景1：学习如何使用其他Skill

### 需求
需要了解如何调用和使用其他Skill。

### 解决方案
参考SKILL.md中的工具调用指南。

### 使用方式
1. 查看SKILL.md的"工具调用指南"部分
2. 了解不同Skill的功能和用法
3. 按照指南调用相应的Skill

---

## 场景2：理解工作流程

### 需求
需要了解如何组织多个Skill完成复杂任务。

### 解决方案
参考SKILL.md中的工作流程说明。

### 使用方式
1. 查看SKILL.md的"工作流程"部分
2. 理解Skill之间的协作关系
3. 按照流程组织任务
"""
    elif skill_type == 'planner':
        content += """## 场景1：生成ReAct工作流程

### 需求
需要为一个新任务生成ReAct工作流程计划。

### 解决方案
参考SKILL.md中的ReAct流程模板。

### 使用方式
1. 查看SKILL.md的"ReAct流程模板"部分
2. 根据任务需求选择合适的流程
3. 按照模板生成工作流程

---

## 场景2：优化现有流程

### 需求
需要优化现有的工作流程以提高效率。

### 解决方案
参考SKILL.md中的流程优化建议。

### 使用方式
1. 查看SKILL.md的"流程优化"部分
2. 分析现有流程的瓶颈
3. 应用优化建议
"""
    elif skill_type == 'hybrid':
        content += """## 场景1：查询配置信息

### 需求
需要查询特定配置的详细信息。

### 解决方案
使用main.py工具查询配置。

### 执行命令
```powershell
python main.py --query "副本CD配置"
```

### 预期结果
- 搜索配置信息
- 显示相关配置详情
- 提供配置说明

---

## 场景2：检查配置正确性

### 需求
需要检查配置文件是否正确。

### 解决方案
使用check_config.py工具检查配置。

### 执行命令
```powershell
python check_config.py --file config.yaml
```

### 预期结果
- 解析配置文件
- 检查配置正确性
- 显示检查结果
"""
    else:
        content += """## 场景1：基本使用

### 需求
需要使用{skill_name}完成基本任务。

### 解决方案
使用main.py工具。

### 执行命令
```powershell
python main.py --input data.txt
```

### 预期结果
- 处理输入数据
- 输出处理结果
"""
    
    return content


def generate_usage_scenarios_content(skill_name, skill_description, skill_type):
    """
    生成usage-scenarios.md的内容
    """
    content = f"""# 使用场景说明

本文档说明{skill_name}在不同场景下的最佳实践和注意事项。

## 场景概述
{skill_name}：{skill_description}
类型：{skill_type}

"""
    
    # 根据不同类型生成不同的使用场景说明
    if skill_type == 'converter':
        content += """## 场景分类

### 1. 批量转换场景
适用于需要批量转换多个文件编码的情况。

**最佳实践**：
- 使用 `--dir` 参数指定目录，而不是逐个文件处理
- 先在小范围测试，确认无误后再批量处理
- 建议使用 `--output-dir` 参数，保留原始文件
- 转换完成后验证文件编码是否正确

**注意事项**：
- 确保源编码参数正确，否则可能导致乱码
- 大批量转换时注意磁盘空间
- 转换前建议备份原始文件

### 2. 乱码修复场景
适用于文件中存在混合编码或乱码的情况。

**最佳实践**：
- 使用 `fix_garbled.py` 工具进行智能修复
- 先在小文件上测试修复效果
- 修复后人工验证关键内容
- 对于重要文件，建议保留原始副本

**注意事项**：
- AI修复可能不完全准确，需要人工验证
- 分段处理大文件，避免内存溢出
- 修复过程中不要使用其他工具操作文件

### 3. 批处理场景
适用于需要按照固定流程批量处理文件的情况。

**最佳实践**：
- 编写清晰的工作流配置文件
- 在配置中定义明确的输入输出路径
- 每个步骤处理完成后进行验证
- 记录处理日志，便于排查问题

**注意事项**：
- 确保工作流配置正确
- 批处理前检查输入数据
- 处理过程中监控进度
- 处理完成后检查输出结果
"""
    elif skill_type == 'tool':
        content += """## 场景分类

### 1. 单文件处理场景
适用于只需要处理单个文件的情况。

**最佳实践**：
- 使用 `--input` 参数指定文件路径
- 明确指定操作类型 `--action`
- 使用 `--output` 参数指定输出路径，避免覆盖原文件
- 处理完成后验证结果

**注意事项**：
- 确保输入文件存在且可读
- 检查操作类型是否正确
- 注意输出路径的权限

### 2. 批量处理场景
适用于需要处理多个文件的情况。

**最佳实践**：
- 使用 `--dir` 参数指定目录
- 使用 `--filter` 参数过滤需要处理的文件
- 建议使用 `--output` 参数指定输出目录
- 批量处理前先测试单个文件

**注意事项**：
- 确保目录下所有文件格式一致
- 注意磁盘空间
- 处理过程中监控进度
- 处理完成后检查结果

### 3. 数据修改场景
适用于需要修改数据内容的情况。

**最佳实践**：
- 修改前备份原始数据
- 使用 `--filter` 参数精确定位要修改的数据
- 修改后验证数据完整性
- 记录修改日志

**注意事项**：
- 确保修改逻辑正确
- 注意数据类型转换
- 避免修改关键字段
"""
    elif skill_type == 'checker':
        content += """## 场景分类

### 1. 单文件检查场景
适用于检查单个配置文件的情况。

**最佳实践**：
- 使用 `--file` 参数指定文件路径
- 检查前先了解配置文件的规范
- 仔细阅读检查结果
- 发现问题及时修复

**注意事项**：
- 确保文件路径正确
- 检查前不要修改文件
- 注意检查结果的严重程度

### 2. 批量检查场景
适用于检查整个配置目录的情况。

**最佳实践**：
- 使用 `--dir` 参数指定目录
- 使用 `--strict` 参数进行严格检查
- 检查前备份配置文件
- 检查后汇总问题并统一修复

**注意事项**：
- 批量检查可能耗时较长
- 注意检查结果的优先级
- 修复一个问题后重新检查
"""
    elif skill_type == 'tester':
        content += """## 场景分类

### 1. 配置测试场景
适用于测试配置文件是否正确的情况。

**最佳实践**：
- 使用 `--target config` 参数指定测试配置
- 测试前确保环境正确
- 使用 `--verbose` 参数查看详细输出
- 测试后分析测试结果

**注意事项**：
- 测试环境应与生产环境隔离
- 测试前备份重要数据
- 注意测试结果的准确性

### 2. 完整测试场景
适用于进行全面测试的情况。

**最佳实践**：
- 不指定 `--target` 参数，测试所有内容
- 测试前准备完整的测试数据
- 使用 `--verbose` 参数查看详细输出
- 测试后生成测试报告

**注意事项**：
- 完整测试可能耗时较长
- 确保测试数据覆盖各种场景
- 注意测试结果的统计信息
"""
    elif skill_type == 'knowledge_base':
        content += """## 场景分类

### 1. 查询场景
适用于需要查询配置信息的情况。

**最佳实践**：
- 先查看SKILL.md的目录结构
- 使用关键词搜索相关信息
- 结合实际配置示例理解
- 记录常用查询内容

**注意事项**：
- 确保查询关键词准确
- 注意配置的版本差异
- 遇到不确定的内容时谨慎使用

### 2. 学习场景
适用于学习配置规则和最佳实践的情况。

**最佳实践**：
- 系统阅读SKILL.md和references
- 结合实际配置示例学习
- 实践中验证学到的知识
- 总结经验教训

**注意事项**：
- 理论与实践结合
- 注意配置的边界情况
- 遇到问题及时查阅文档
"""
    elif skill_type == 'guide':
        content += """## 场景分类

### 1. 学习场景
适用于学习如何使用其他Skill的情况。

**最佳实践**：
- 先了解各个Skill的功能
- 查看Skill的使用指南
- 结合实际场景练习
- 总结使用经验

**注意事项**：
- 注意Skill之间的依赖关系
- 理解Skill的适用场景
- 遇到问题及时查阅文档

### 2. 协作场景
适用于多个Skill协作完成任务的情况。

**最佳实践**：
- 理解工作流程
- 按照流程调用Skill
- 注意Skill之间的数据传递
- 记录协作过程

**注意事项**：
- 确保Skill的调用顺序正确
- 注意数据的格式转换
- 处理异常情况
"""
    elif skill_type == 'planner':
        content += """## 场景分类

### 1. 流程生成场景
适用于生成新的工作流程的情况。

**最佳实践**：
- 明确任务目标
- 选择合适的流程模板
- 根据实际情况调整流程
- 验证流程的可行性

**注意事项**：
- 确保流程逻辑正确
- 注意流程的完整性
- 考虑异常情况的处理

### 2. 流程优化场景
适用于优化现有工作流程的情况。

**最佳实践**：
- 分析现有流程的瓶颈
- 应用优化建议
- 测试优化后的流程
- 对比优化效果

**注意事项**：
- 优化前备份原始流程
- 逐步优化，避免大改动
- 优化后充分测试
"""
    elif skill_type == 'hybrid':
        content += """## 场景分类

### 1. 查询场景
适用于查询配置信息的情况。

**最佳实践**：
- 使用main.py工具查询
- 使用准确的查询关键词
- 查看查询结果的详细信息
- 结合SKILL.md理解配置

**注意事项**：
- 确保查询关键词准确
- 注意查询结果的完整性
- 遇到不确定的内容时谨慎使用

### 2. 检查场景
适用于检查配置正确性的情况。

**最佳实践**：
- 使用check_config.py工具检查
- 检查前了解配置规范
- 仔细阅读检查结果
- 发现问题及时修复

**注意事项**：
- 确保文件路径正确
- 检查前不要修改文件
- 注意检查结果的严重程度

### 3. 综合使用场景
适用于同时使用查询和检查功能的情况。

**最佳实践**：
- 先查询了解配置信息
- 再检查配置正确性
- 结合两者结果进行分析
- 统一修复问题

**注意事项**：
- 注意工具的使用顺序
- 确保数据的一致性
- 记录处理过程
"""
    else:
        content += """## 场景分类

### 1. 基本使用场景
适用于使用{skill_name}完成基本任务的情况。

**最佳实践**：
- 先阅读使用指南
- 在小范围测试
- 验证结果
- 批量应用

**注意事项**：
- 确保输入参数正确
- 注意输出结果的验证
"""
    
    return content


def generate_efficient_usage_content(skill_name, skill_description, skill_type):
    """
    生成efficient-usage.md的内容
    """
    content = f"""# 最高效的使用方式

本文档提供{skill_name}的性能优化建议和高效使用技巧。

## 概述
{skill_name}：{skill_description}
类型：{skill_type}

"""
    
    # 根据不同类型生成不同的高效使用方式
    if skill_type == 'converter':
        content += """## 性能优化建议

### 1. 批量处理技巧
- 使用 `--dir` 参数批量处理目录，而不是逐个文件处理
- 合理设置输出目录，避免频繁的目录切换
- 对于大量小文件，考虑先打包再处理

### 2. 内存优化方法
- 对于超大文件，考虑分段处理
- 使用流式处理，避免一次性加载整个文件
- 及时释放不再使用的内存

### 3. 并行处理建议
- 对于独立的文件，可以考虑多进程并行处理
- 使用 `multiprocessing` 模块实现并行处理
- 注意控制并行数量，避免系统资源耗尽

## 高效使用技巧

### 技巧1：快速完成任务
- 使用 `--dir` 参数批量处理
- 预先准备好工作流配置
- 使用脚本自动化重复任务

### 技巧2：避免常见陷阱
- 转换前先检测文件编码，避免错误转换
- 转换后验证文件内容，确保转换正确
- 重要文件转换前务必备份

### 技巧3：提高处理效率
- 使用 `--output-dir` 参数，避免覆盖原文件
- 合理使用过滤条件，只处理需要的文件
- 定期清理临时文件，释放磁盘空间
"""
    elif skill_type == 'tool':
        content += """## 性能优化建议

### 1. 批量处理技巧
- 使用 `--dir` 参数批量处理目录
- 使用 `--filter` 参数精确定位需要处理的文件
- 避免不必要的文件读取和写入

### 2. 内存优化方法
- 对于大文件，使用流式处理
- 及时释放不再使用的数据
- 使用生成器处理大量数据

### 3. 并行处理建议
- 对于独立的文件，使用多进程并行处理
- 使用 `multiprocessing` 模块
- 注意控制并行数量

## 高效使用技巧

### 技巧1：快速完成任务
- 预先准备好输入数据
- 使用批量操作代替单个操作
- 使用脚本自动化重复任务

### 技巧2：避免常见陷阱
- 操作前备份原始数据
- 操作后验证结果
- 注意数据类型转换

### 技巧3：提高处理效率
- 使用过滤条件减少处理范围
- 合理使用缓存
- 优化数据结构
"""
    elif skill_type == 'checker':
        content += """## 性能优化建议

### 1. 批量检查技巧
- 使用 `--dir` 参数批量检查目录
- 使用 `--strict` 参数进行严格检查
- 检查前先过滤不需要检查的文件

### 2. 内存优化方法
- 流式读取配置文件
- 及时释放已检查的文件
- 使用缓存避免重复检查

### 3. 并行检查建议
- 对于独立的配置文件，使用多进程并行检查
- 使用 `multiprocessing` 模块
- 注意控制并行数量

## 高效使用技巧

### 技巧1：快速完成任务
- 使用批量检查代替单个检查
- 预先了解配置规范
- 使用脚本自动化检查任务

### 技巧2：避免常见陷阱
- 检查前不要修改文件
- 注意检查结果的严重程度
- 发现问题及时修复

### 技巧3：提高处理效率
- 使用过滤条件减少检查范围
- 合理使用缓存
- 优化检查逻辑
"""
    elif skill_type == 'tester':
        content += """## 性能优化建议

### 1. 测试技巧
- 使用 `--target` 参数指定测试范围
- 使用 `--verbose` 参数查看详细输出
- 测试前准备完整的测试数据

### 2. 内存优化方法
- 及时释放测试数据
- 使用流式处理大文件
- 避免重复加载相同数据

### 3. 并行测试建议
- 对于独立的测试用例，使用多进程并行测试
- 使用 `multiprocessing` 模块
- 注意控制并行数量

## 高效使用技巧

### 技巧1：快速完成任务
- 使用 `--target` 参数只测试需要的部分
- 预先准备好测试数据
- 使用脚本自动化测试任务

### 技巧2：避免常见陷阱
- 测试环境应与生产环境隔离
- 测试前备份重要数据
- 注意测试结果的准确性

### 技巧3：提高处理效率
- 使用测试数据覆盖各种场景
- 合理使用测试缓存
- 优化测试逻辑
"""
    elif skill_type == 'knowledge_base':
        content += """## 高效使用技巧

### 技巧1：快速查找信息
- 使用关键词搜索
- 查看SKILL.md的目录结构
- 记录常用查询内容

### 技巧2：避免常见陷阱
- 确保查询关键词准确
- 注意配置的版本差异
- 遇到不确定的内容时谨慎使用

### 技巧3：提高学习效率
- 系统阅读文档
- 结合实际示例学习
- 实践中验证知识
- 总结经验教训
"""
    elif skill_type == 'guide':
        content += """## 高效使用技巧

### 技巧1：快速完成任务
- 先了解各个Skill的功能
- 查看Skill的使用指南
- 按照流程调用Skill

### 技巧2：避免常见陷阱
- 注意Skill之间的依赖关系
- 理解Skill的适用场景
- 遇到问题及时查阅文档

### 技巧3：提高协作效率
- 理解工作流程
- 注意数据传递格式
- 记录协作过程
"""
    elif skill_type == 'planner':
        content += """## 高效使用技巧

### 技巧1：快速生成流程
- 明确任务目标
- 选择合适的流程模板
- 根据实际情况调整流程

### 技巧2：避免常见陷阱
- 确保流程逻辑正确
- 注意流程的完整性
- 考虑异常情况的处理

### 技巧3：提高优化效率
- 分析现有流程的瓶颈
- 应用优化建议
- 测试优化后的流程
"""
    elif skill_type == 'hybrid':
        content += """## 性能优化建议

### 1. 批量处理技巧
- 使用批量查询代替单个查询
- 使用批量检查代替单个检查
- 合理组织查询和检查的顺序

### 2. 内存优化方法
- 及时释放查询结果
- 使用缓存避免重复查询
- 流式处理大文件

### 3. 并行处理建议
- 对于独立的查询，使用多进程并行查询
- 对于独立的检查，使用多进程并行检查
- 注意控制并行数量

## 高效使用技巧

### 技巧1：快速完成任务
- 先查询了解配置信息
- 再检查配置正确性
- 统一修复问题

### 技巧2：避免常见陷阱
- 确保查询关键词准确
- 检查前不要修改文件
- 注意检查结果的严重程度

### 技巧3：提高处理效率
- 使用过滤条件减少处理范围
- 合理使用缓存
- 优化查询和检查逻辑
"""
    else:
        content += """## 高效使用技巧

### 技巧1：快速完成任务
- 预先准备好输入数据
- 使用批量操作
- 使用脚本自动化任务

### 技巧2：避免常见陷阱
- 操作前备份原始数据
- 操作后验证结果
- 注意参数的正确性

### 技巧3：提高处理效率
- 使用过滤条件减少处理范围
- 合理使用缓存
- 优化数据结构
"""
    
    return content


def generate_skill_md(skill_dir, skill_name, skill_description):
    """
    生成SKILL.md文件
    :param skill_dir: Skill目录
    :param skill_name: Skill名称
    :param skill_description: Skill描述
    """
    skill_md_content = f"""---
name: {skill_name}
description: |
  {skill_description}
allowed-tools: powershell, cmd, Edit, Read, Write, RunCommand
---

# {skill_name} 使用指南

## 功能介绍
{skill_description}

## 使用示例

### 示例1：基本使用
**用户输入**：
```
使用{skill_name}处理数据
```

**生成结果**：
- 执行相关操作
- 返回处理结果

## 技术实现

### 核心功能
- 实现{skill_description}的核心逻辑
- 提供简单易用的接口

### 实现细节
- 使用Python脚本实现核心功能
- 支持命令行参数
- 严格遵循Skill开发规范

## 注意事项
1. **命名规范**：严格遵循Skill开发规范
2. **编码规范**：使用UTF-8编码
3. **目录结构**：保持规范的目录结构

## 示例命令

### 基本命令
```powershell
# 运行{skill_name}
python scripts/main.py
```

## 输入输出示例

#### 输入：
```
使用{skill_name}处理数据
```

#### 输出：
```
正在执行{skill_name}...
处理完成！
```
"""
    
    with open(skill_dir / 'SKILL.md', 'w', encoding='utf-8') as f:
        f.write(skill_md_content)


def generate_example_script(scripts_dir):
    """
    生成示例脚本
    :param scripts_dir: 脚本目录
    """
    main_script_content = '''
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
示例脚本
"""

import argparse


def main():
    parser = argparse.ArgumentParser(description='示例脚本')
    parser.add_argument('--input', type=str, help='输入参数')
    parser.add_argument('--output', type=str, help='输出参数')
    args = parser.parse_args()
    
    print(f"执行示例脚本，输入: {args.input}, 输出: {args.output}")
    print("处理完成！")


if __name__ == '__main__':
    main()
'''
    
    with open(scripts_dir / 'main.py', 'w', encoding='utf-8') as f:
        f.write(main_script_content)


def generate_converter_skill(skill_dir, skill_name, skill_description):
    """
    生成转换器类型Skill
    """
    skill_md_content = f'''---
name: {skill_name}
description: |
  {skill_description}
allowed-tools: powershell, cmd, Edit, Read, Write, RunCommand
---

# {skill_name} 转换器

## 功能介绍
{skill_description}

## 支持功能

### 1. 编码转换
批量转换文件编码格式
- 支持GBK、UTF-8、UTF-8 BOM等编码
- 自动检测源编码
- 批量处理目录下的所有文件

### 2. 乱码修复
智能修复文件中的乱码内容
- 分段处理大文件
- 利用AI识别乱码位置
- 精确定位并替换

### 3. 批处理
根据固定工作流批量处理文件
- 支持自定义处理流程
- 批量读取、处理、输出
- 支持过滤和筛选

### 4. 批量总结
根据规则批量扫描文件并汇总
- 提取关键信息
- 生成汇总报告
- 支持多种输出格式

### 5. 代码文档生成
为代码自动生成文档
- 解析代码结构
- 提取函数说明
- 按照指定格式输出

## 使用方法

### 编码转换
```powershell
# 转换单个文件
python main.py --input file.txt --from gbk --to utf-8

# 批量转换目录
python main.py --dir ./data --from gbk --to utf-8
```

### 乱码修复
```powershell
# 修复乱码文件
python fix_garbled.py --input file.txt --encoding utf-8
```

### 批处理
```powershell
# 执行批处理任务
python batch_process.py --config workflow.json --input ./data
```

### 批量总结
```powershell
# 批量扫描并汇总
python batch_summarize.py --dir ./docs --rules rules.json
```

### 代码文档生成
```powershell
# 生成代码文档
python generate_doc.py --code-dir ./src --output ./docs --template template.md
```

## 注意事项
1. **备份重要数据**：转换前请备份原始文件
2. **分段处理**：大文件建议分段处理，避免内存溢出
3. **编码检测**：自动检测可能不准确，建议手动指定
4. **处理过程**：处理过程中避免使用其他工具，防止错乱

## 输入输出示例

#### 输入：
```
将./data目录下的所有GBK编码文件转换为UTF-8编码
```

#### 输出：
```
正在扫描./data目录...
发现15个GBK编码文件
开始转换...
转换完成：15/15
输出目录：./data/converted/
```
'''
    
    with open(skill_dir / 'SKILL.md', 'w', encoding='utf-8') as f:
        f.write(skill_md_content)
    
    # 生成编码转换脚本（放在根目录）
    convert_script = '''
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
编码转换脚本
"""

import os
import argparse
from pathlib import Path


def detect_encoding(file_path):
    """检测文件编码"""
    # 实现编码检测逻辑
    pass


def convert_file(input_path, output_path, from_encoding, to_encoding):
    """转换单个文件编码"""
    try:
        with open(input_path, 'r', encoding=from_encoding, errors='ignore') as f:
            content = f.read()
        
        with open(output_path, 'w', encoding=to_encoding) as f:
            f.write(content)
        
        return True
    except Exception as e:
        print(f"转换失败: {input_path}, 错误: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='编码转换工具')
    parser.add_argument('--input', type=str, help='输入文件路径')
    parser.add_argument('--dir', type=str, help='输入目录路径')
    parser.add_argument('--from', dest='from_encoding', type=str, default='gbk', help='源编码')
    parser.add_argument('--to', dest='to_encoding', type=str, default='utf-8', help='目标编码')
    parser.add_argument('--output-dir', type=str, help='输出目录')
    args = parser.parse_args()
    
    # 实现转换逻辑
    print("编码转换工具")


if __name__ == '__main__':
    main()
'''
    
    with open(skill_dir / 'main.py', 'w', encoding='utf-8') as f:
        f.write(convert_script)
    
    # 生成乱码修复脚本（放在根目录）
    fix_script = '''
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
乱码修复脚本
"""

import os
import argparse


def fix_garbled_text(file_path, encoding='utf-8'):
    """
    修复文件中的乱码
    分段处理，利用AI识别乱码位置
    """
    print(f"修复文件: {file_path}")
    # 实现乱码修复逻辑
    # 1. 分段读取文件
    # 2. 利用AI识别乱码
    # 3. 定位并替换乱码
    # 4. 继续处理下一段


def main():
    parser = argparse.ArgumentParser(description='乱码修复工具')
    parser.add_argument('--input', type=str, required=True, help='输入文件路径')
    parser.add_argument('--encoding', type=str, default='utf-8', help='文件编码')
    args = parser.parse_args()
    
    fix_garbled_text(args.input, args.encoding)


if __name__ == '__main__':
    main()
'''
    
    with open(skill_dir / 'fix_garbled.py', 'w', encoding='utf-8') as f:
        f.write(fix_script)
    
    # 生成批处理脚本（放在根目录）
    batch_script = '''
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批处理脚本
"""

import os
import json
import argparse


def load_workflow(config_path):
    """加载工作流配置"""
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def execute_workflow(workflow, input_dir):
    """执行批处理工作流"""
    print(f"执行工作流: {workflow['name']}")
    # 实现工作流执行逻辑


def main():
    parser = argparse.ArgumentParser(description='批处理工具')
    parser.add_argument('--config', type=str, required=True, help='工作流配置文件')
    parser.add_argument('--input', type=str, required=True, help='输入目录')
    args = parser.parse_args()
    
    workflow = load_workflow(args.config)
    execute_workflow(workflow, args.input)


if __name__ == '__main__':
    main()
'''
    
    with open(skill_dir / 'batch_process.py', 'w', encoding='utf-8') as f:
        f.write(batch_script)


def generate_tool_skill(skill_dir, skill_name, skill_description):
    """
    生成工具类型Skill
    """
    skill_md_content = f'''---
name: {skill_name}
description: |
  {skill_description}
allowed-tools: powershell, cmd, Edit, Read, Write, RunCommand
---

# {skill_name} 使用指南

## 功能介绍
{skill_description}

## 使用示例

### 示例1：基本使用
**用户输入**：
```
使用{skill_name}处理数据
```

**生成结果**：
- 执行相关操作
- 返回处理结果

## 技术实现

### 核心功能
- 实现{skill_description}的核心逻辑
- 提供简单易用的接口

### 实现细节
- 使用Python脚本实现核心功能
- 支持命令行参数
- 严格遵循Skill开发规范

## 注意事项
1. **命名规范**：严格遵循Skill开发规范
2. **编码规范**：使用UTF-8编码
3. **目录结构**：保持规范的目录结构

## 示例命令

### 基本命令
```powershell
# 运行{skill_name}
python main.py
```

## 输入输出示例

#### 输入：
```
使用{skill_name}处理数据
```

#### 输出：
```
正在执行{skill_name}...
处理完成！
```
'''
    
    with open(skill_dir / 'SKILL.md', 'w', encoding='utf-8') as f:
        f.write(skill_md_content)
    
    # 生成示例脚本（放在根目录）
    generate_example_script(skill_dir)


def generate_knowledge_base_skill(skill_dir, skill_name, skill_description):
    """
    生成知识库类型Skill
    """
    skill_md_content = f'''---
name: {skill_name}
description: |
  {skill_description}
allowed-tools: powershell, cmd, Edit, Read, Write, RunCommand
---

# {skill_name} 知识库

## 功能介绍
{skill_description}

## 核心知识

### 配置文件路径
- 主配置目录：`${{workspaceFolder}}/config/`
- 数据文件目录：`${{workspaceFolder}}/data/`

### 关键概念
1. **概念1**：详细说明
2. **概念2**：详细说明
3. **概念3**：详细说明

### 常见问题

#### Q1: 如何查询配置？
**A**: 可以通过以下方式查询：
1. 使用Read工具读取配置文件
2. 使用SearchCodebase搜索相关信息

#### Q2: 配置文件的格式是什么？
**A**: 配置文件通常使用以下格式：
- YAML格式：用于配置定义
- JSON格式：用于数据存储
- TAB格式：用于表格数据

## 使用指南

### 查询配置信息
当用户询问配置相关问题时：
1. 首先检查references目录下的文档
2. 使用Read工具读取相关配置文件
3. 综合分析后给出准确回答

### 解释配置规则
当需要解释配置规则时：
1. 引用知识库中的规则说明
2. 结合实际配置示例
3. 提供清晰的解释和建议

## 参考资料
- `references/config-guide.md` - 配置指南
- `references/faq.md` - 常见问题解答
'''
    
    with open(skill_dir / 'SKILL.md', 'w', encoding='utf-8') as f:
        f.write(skill_md_content)
    
    # 生成知识库参考文件
    config_guide_content = '''
# 配置指南

## 配置文件结构

### 主配置文件
- 位置：`config/main.conf`
- 格式：YAML
- 说明：包含系统主要配置

### 数据文件
- 位置：`data/`
- 格式：TAB分隔
- 说明：包含业务数据

## 配置规则

### 规则1：命名规范
- 使用小写字母
- 单词间使用连字符
- 避免使用特殊字符

### 规则2：格式要求
- YAML文件使用2空格缩进
- TAB文件使用UTF-8编码
- JSON文件使用紧凑格式
'''
    
    with open(skill_dir / 'references' / 'config-guide.md', 'w', encoding='utf-8') as f:
        f.write(config_guide_content)


def generate_tester_skill(skill_dir, skill_name, skill_description):
    """
    生成测试器类型Skill
    """
    skill_md_content = f'''---
name: {skill_name}
description: |
  {skill_description}
allowed-tools: powershell, cmd, Edit, Read, Write, RunCommand
---

# {skill_name} 测试器

## 功能介绍
{skill_description}

## 测试范围

### 配置文件测试
- 语法检查
- 格式验证
- 逻辑检查

### 脚本测试
- 语法正确性
- 运行测试
- 输出验证

## 测试流程

### 步骤1：准备测试环境
```powershell
# 检查测试环境
python main.py --check-env
```

### 步骤2：执行测试
```powershell
# 运行所有测试
python main.py

# 运行特定测试
python main.py --target config
```

### 步骤3：查看结果
测试结果将保存在 `test_results/` 目录下

## 测试用例

### 用例1：配置文件语法检查
**输入**：配置文件路径
**预期结果**：无语法错误
**验证方法**：使用脚本解析配置

### 用例2：数据格式验证
**输入**：数据文件路径
**预期结果**：符合格式规范
**验证方法**：检查字段类型和范围

## 注意事项
1. 测试前请备份重要数据
2. 测试环境应与生产环境隔离
3. 详细记录测试结果
'''
    
    with open(skill_dir / 'SKILL.md', 'w', encoding='utf-8') as f:
        f.write(skill_md_content)
    
    # 生成测试脚本（放在根目录）
    test_script_content = '''
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试脚本
"""

import os
import sys
import argparse
from pathlib import Path


def test_config_syntax(config_path):
    """测试配置文件语法"""
    print(f"测试配置文件: {config_path}")
    # 实现测试逻辑
    return True


def test_data_format(data_path):
    """测试数据格式"""
    print(f"测试数据文件: {data_path}")
    # 实现测试逻辑
    return True


def main():
    parser = argparse.ArgumentParser(description='测试工具')
    parser.add_argument('--target', type=str, help='测试目标')
    parser.add_argument('--verbose', action='store_true', help='显示详细输出')
    parser.add_argument('--check-env', action='store_true', help='检查测试环境')
    args = parser.parse_args()
    
    print("开始测试...")
    # 执行测试
    print("测试完成！")


if __name__ == '__main__':
    main()
'''
    
    with open(skill_dir / 'main.py', 'w', encoding='utf-8') as f:
        f.write(test_script_content)


def generate_checker_skill(skill_dir, skill_name, skill_description):
    """
    生成检查器类型Skill
    """
    skill_md_content = f'''---
name: {skill_name}
description: |
  {skill_description}
allowed-tools: powershell, cmd, Edit, Read, Write, RunCommand
---

# {skill_name} 检查器

## 功能介绍
{skill_description}

## 检查项目

### 配置文件检查
- [ ] 文件格式正确
- [ ] 必填字段完整
- [ ] 数据类型正确
- [ ] 取值范围合理

### 关联性检查
- [ ] 引用的ID存在
- [ ] 依赖关系正确
- [ ] 无循环依赖

## 检查规则

### 规则1：ID唯一性
所有ID必须在全局范围内唯一

### 规则2：引用完整性
所有引用必须指向存在的对象

### 规则3：数据一致性
相关数据之间必须保持一致

## 检查流程

### 步骤1：收集配置
```powershell
# 扫描配置文件
python main.py --scan
```

### 步骤2：执行检查
```powershell
# 运行检查
python main.py

# 检查特定文件
python main.py --file config.yaml
```

### 步骤3：生成报告
检查结果将保存在 `check_report.md`

## 常见问题及修复方案

### 问题1：ID重复
**原因**：手动添加时未检查
**修复**：自动重命名或合并

### 问题2：引用不存在
**原因**：删除了被引用的对象
**修复**：更新引用或恢复对象

### 问题3：数据类型错误
**原因**：输入格式不正确
**修复**：转换数据类型或修正输入
'''
    
    with open(skill_dir / 'SKILL.md', 'w', encoding='utf-8') as f:
        f.write(skill_md_content)
    
    # 生成检查脚本（放在根目录）
    check_script_content = '''
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查脚本
"""

import os
import sys
import argparse
from pathlib import Path


def check_id_uniqueness(configs):
    """检查ID唯一性"""
    print("检查ID唯一性...")
    # 实现检查逻辑
    return []


def check_reference_integrity(configs):
    """检查引用完整性"""
    print("检查引用完整性...")
    # 实现检查逻辑
    return []


def main():
    parser = argparse.ArgumentParser(description='检查工具')
    parser.add_argument('--file', type=str, help='要检查的文件路径')
    parser.add_argument('--dir', type=str, help='要检查的目录路径')
    parser.add_argument('--strict', action='store_true', help='严格模式')
    parser.add_argument('--scan', action='store_true', help='扫描配置文件')
    args = parser.parse_args()
    
    print("开始检查...")
    # 执行检查
    print("检查完成！")


if __name__ == '__main__':
    main()
'''
    
    with open(skill_dir / 'main.py', 'w', encoding='utf-8') as f:
        f.write(check_script_content)


def generate_guide_skill(skill_dir, skill_name, skill_description):
    """
    生成指导器类型Skill
    """
    skill_md_content = f'''---
name: {skill_name}
description: |
  {skill_description}
allowed-tools: powershell, cmd, Edit, Read, Write, RunCommand
---

# {skill_name} 指导器

## 功能介绍
{skill_description}

## 可调用工具

### Skill工具
- `skill-name-1` - 功能说明
- `skill-name-2` - 功能说明

### MCP工具
- `mcp-tool-1` - 功能说明
- `mcp-tool-2` - 功能说明

## 使用场景

### 场景1：数据处理
**用户需求**：处理特定数据
**调用流程**：
1. 使用 `data-reader` 读取数据
2. 使用 `data-processor` 处理数据
3. 使用 `data-writer` 写入结果

### 场景2：配置检查
**用户需求**：检查配置正确性
**调用流程**：
1. 使用 `config-checker` 检查配置
2. 使用 `config-fixer` 修复问题
3. 使用 `config-validator` 验证结果

## 指导原则

### 原则1：工具选择
根据任务类型选择最合适的工具

### 原则2：调用顺序
按照依赖关系确定调用顺序

### 原则3：错误处理
每个步骤都要有错误处理机制

## 示例

### 示例1：完整流程
```
用户：我需要处理玩家数据并检查配置

指导器：
1. 首先调用 `player-data-processor` 处理玩家数据
2. 然后调用 `config-checker` 检查配置
3. 最后返回处理结果
```
'''
    
    with open(skill_dir / 'SKILL.md', 'w', encoding='utf-8') as f:
        f.write(skill_md_content)


def generate_planner_skill(skill_dir, skill_name, skill_description):
    """
    生成流程专家类型Skill
    """
    skill_md_content = f'''---
name: {skill_name}
description: |
  {skill_description}
allowed-tools: powershell, cmd, Edit, Read, Write, RunCommand
---

# {skill_name} 流程专家

## 功能介绍
{skill_description}

## ReAct工作流程

### 步骤1：Reason（思考）
分析用户需求，确定任务目标

### 步骤2：Act（行动）
执行具体操作，调用相关工具

### 步骤3：Observe（观察）
观察执行结果，收集反馈信息

### 步骤4：Repeat（重复）
根据反馈调整策略，继续执行

## 典型流程模板

### 模板1：数据处理流程
```
1. 理解需求
   - 明确数据来源
   - 确定处理目标
   - 识别约束条件

2. 制定计划
   - 分解任务步骤
   - 确定工具调用顺序
   - 设定检查点

3. 执行计划
   - 按步骤执行
   - 记录中间结果
   - 处理异常情况

4. 验证结果
   - 检查结果正确性
   - 确认目标达成
   - 生成执行报告
```

### 模板2：问题排查流程
```
1. 收集信息
   - 了解问题现象
   - 获取相关日志
   - 分析错误信息

2. 定位原因
   - 逐步排查可能原因
   - 验证假设
   - 确定根本原因

3. 制定方案
   - 设计解决方案
   - 评估方案可行性
   - 选择最优方案

4. 实施修复
   - 执行修复操作
   - 验证修复效果
   - 记录修复过程
```

## 最佳实践

### 实践1：任务分解
将复杂任务分解为可管理的子任务

### 实践2：持续验证
每个阶段都要验证结果正确性

### 实践3：文档记录
详细记录执行过程和决策依据
'''
    
    with open(skill_dir / 'SKILL.md', 'w', encoding='utf-8') as f:
        f.write(skill_md_content)


def generate_hybrid_skill(skill_dir, skill_name, skill_description):
    """
    生成复合型Skill（如副本CD配置专家）
    """
    skill_md_content = f'''---
name: {skill_name}
description: |
  {skill_description}
allowed-tools: powershell, cmd, Edit, Read, Write, RunCommand
---

# {skill_name} 复合型专家

## 功能介绍
{skill_description}

## 多重角色

### 角色1：知识库
提供配置相关的知识和规则说明

#### 配置文件路径
- 主配置：`${{workspaceFolder}}/config/dungeon/`
- CD配置：`${{workspaceFolder}}/config/dungeon/cooldown/`

#### 配置规则
1. **规则1**：详细说明
2. **规则2**：详细说明
3. **潜规则**：详细说明

#### 算法说明
- 算法1：详细说明
- 算法2：详细说明

### 角色2：检查器
检查配置的正确性和完整性

#### 检查项目
- [ ] 配置格式正确
- [ ] CD时间合理
- [ ] 依赖关系正确
- [ ] 无冲突配置

#### 常见问题
1. **问题1**：原因和修复方案
2. **问题2**：原因和修复方案

### 角色3：查询器
查询特定副本的CD配置

#### 查询方式
1. 根据副本ID查询
2. 根据副本名称查询
3. 根据条件筛选

#### 返回信息
- CD时间
- 重置规则
- 相关配置

### 角色4：指导器
指导用户完成配置任务

#### 指导流程
1. 了解需求
2. 提供方案
3. 协助实施
4. 验证结果

## 使用示例

### 示例1：知识查询
**用户**：副本CD的配置规则是什么？

**专家**：
1. 引用知识库中的规则说明
2. 解释潜规则和算法
3. 提供配置示例

### 示例2：配置检查
**用户**：帮我检查副本CD配置

**专家**：
1. 读取配置文件
2. 执行检查逻辑
3. 返回检查结果和修复建议

### 示例3：信息查询
**用户**：查询副本XXX的CD时间

**专家**：
1. 定位配置文件
2. 提取CD信息
3. 返回格式化结果

### 示例4：配置指导
**用户**：如何配置新的副本CD？

**专家**：
1. 了解具体需求
2. 提供配置步骤
3. 协助生成配置
4. 验证配置正确性

## 参考资料
- `references/dungeon-config-guide.md` - 副本配置指南
- `references/cooldown-rules.md` - CD规则说明
- `references/common-issues.md` - 常见问题
'''
    
    with open(skill_dir / 'SKILL.md', 'w', encoding='utf-8') as f:
        f.write(skill_md_content)
    
    # 生成查询脚本（放在根目录）
    query_script = '''
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查询脚本
"""

import os
import sys
import argparse
from pathlib import Path


def query_dungeon_info(query, query_type=None):
    """查询副本信息"""
    print(f"查询副本信息: {query}")
    # 实现查询逻辑
    return {}


def main():
    parser = argparse.ArgumentParser(description='查询工具')
    parser.add_argument('--query', type=str, required=True, help='查询内容')
    parser.add_argument('--type', type=str, help='查询类型')
    args = parser.parse_args()
    
    result = query_dungeon_info(args.query, args.type)
    print("查询完成！")


if __name__ == '__main__':
    main()
'''
    
    with open(skill_dir / 'main.py', 'w', encoding='utf-8') as f:
        f.write(query_script)
    
    # 生成检查脚本（放在根目录）
    check_script = '''
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查脚本
"""

import os
import sys
import argparse
from pathlib import Path


def check_dungeon_config(config_path, strict=False):
    """检查副本配置"""
    print(f"检查副本配置: {config_path}")
    # 实现检查逻辑
    return []


def main():
    parser = argparse.ArgumentParser(description='检查工具')
    parser.add_argument('--file', type=str, required=True, help='要检查的文件路径')
    parser.add_argument('--strict', action='store_true', help='严格模式')
    args = parser.parse_args()
    
    result = check_dungeon_config(args.file, args.strict)
    print("检查完成！")


if __name__ == '__main__':
    main()
'''
    
    with open(skill_dir / 'check_config.py', 'w', encoding='utf-8') as f:
        f.write(check_script)
    
    # 生成参考文件
    dungeon_guide_content = '''
# 副本配置指南

## 配置文件结构

### 主配置文件
- 位置：`config/dungeon/main.yaml`
- 说明：包含副本基本配置

### CD配置文件
- 位置：`config/dungeon/cooldown/`
- 说明：包含各副本CD配置

## CD配置规则

### 规则1：时间格式
- 使用秒为单位
- 支持表达式：1h30m = 5400秒

### 规则2：重置时间
- 每日重置：00:00
- 每周重置：周一00:00

### 规则3：特殊规则
- 首次通关不计CD
- 组队副本共享CD
'''
    
    with open(skill_dir / 'references' / 'dungeon-config-guide.md', 'w', encoding='utf-8') as f:
        f.write(dungeon_guide_content)


def main():
    """
    主函数
    """
    # 测试模式：直接硬编码测试数据
    # 测试不同类型的Skill生成
    test_cases = [
        "批量转换文件编码，将GBK编码的文件转换为UTF-8编码",  # converter类型
        "用于处理玩家数据的工具，能够读取和修改玩家属性",  # tool类型
        "副本CD配置知识库，用于回答配置方式和文件路径以及潜规则、算法",  # knowledge_base类型
        "测试配置文件和脚本写法是否正确的测试器",  # tester类型
        "检查配置文件是否正确，比较相互之间的关系，找出有问题的部分",  # checker类型
        "指导agent去调用别的skill或者mcp的指导器",  # guide类型
        "根据固定下来的经验，指导生成一个ReAct的Agent的工作流程的计划",  # planner类型
        "副本CD配置专家，可以是知识库、检查器、查询器和指导器",  # hybrid类型
    ]
    
    for test_description in test_cases:
        test_name, _, test_type = parse_description(test_description)
        
        print(f"\n正在生成skill: {test_name} (类型: {test_type})")
        print("创建目录结构...")
        
        # 创建Skill结构
        skill_dir = create_skill_structure(test_name, test_description, test_type)
        
        print("编写SKILL.md文件...")
        print("生成脚本文件...")
        print(f"Skill生成完成！")
        print(f"生成路径: {skill_dir}")
    
    # 命令行模式（注释掉以避免编码问题）
    """
    # 处理命令行参数编码
    if sys.version_info[0] < 3:
        # Python 2 处理方式
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout)
    
    parser = argparse.ArgumentParser(description='Skill生成器')
    parser.add_argument('-n', '--name', type=str, help='Skill名称')
    parser.add_argument('-d', '--description', type=str, help='Skill描述')
    args = parser.parse_args()
    
    # 处理参数编码
    if args.description:
        args.description = get_encoded_arg(args.description)
    if args.name:
        args.name = get_encoded_arg(args.name)
    
    # 如果没有提供参数，使用默认值
    if not args.description:
        args.description = "自动生成的Skill"
    
    if not args.name:
        # 解析描述生成名称
        args.name, _ = parse_description(args.description)
    
    print(f"正在生成skill: {args.name}")
    print("创建目录结构...")
    
    # 创建Skill结构
    skill_dir = create_skill_structure(args.name, args.description)
    
    print("编写SKILL.md文件...")
    print("生成脚本文件...")
    print(f"Skill生成完成！")
    print(f"生成路径: {skill_dir}")
    """


if __name__ == '__main__':
    main()
