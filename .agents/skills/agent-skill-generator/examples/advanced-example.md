# 高级示例

## 功能说明
本示例展示如何使用skill生成器创建一个包含完整功能的Skill。

## 输入输出示例

### 输入：
```
我需要一个处理技能数据的Skill，能够添加新技能、修改技能属性，并且支持批量操作。
```

### 输出：
```
正在生成skill: skill-1773634000
创建目录结构...
编写SKILL.md文件...
生成脚本文件...
Skill生成完成！
生成路径: K:\Sword3-products\trunk\tools\SKILLS\skill-1773634000
```

## 生成的文件结构
```
skill-1773634000/
├── SKILL.md
├── scripts/
│   ├── main.py
│   └── skill_manager.py
├── examples/
│   └── usage-example.md
└── references/
    └── skill-ids.md
```

## 生成的SKILL.md内容
```yaml
---
name: skill-1773634000
description: 用于处理技能数据的工具，能够添加新技能、修改技能属性，并且支持批量操作
allowed-tools: powershell, cmd, Edit, Read, Write, RunCommand
---

# skill-1773634000 使用指南

## 功能介绍
用于处理技能数据的工具，能够添加新技能、修改技能属性，并且支持批量操作

## 核心功能
- 添加新技能
- 修改技能属性
- 批量操作技能数据
- 导出技能数据
```