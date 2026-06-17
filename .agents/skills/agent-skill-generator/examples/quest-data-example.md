# 任务数据处理示例

## 功能说明
本示例展示如何使用skill生成器创建一个处理任务数据的Skill。

## 输入输出示例

### 输入：
```
我需要一个处理任务数据的Skill，能够创建新任务、修改任务奖励，并且支持任务链管理。
```

### 输出：
```
正在生成skill: skill-1773634001
创建目录结构...
编写SKILL.md文件...
生成脚本文件...
Skill生成完成！
生成路径: K:\Sword3-products\trunk\tools\SKILLS\skill-1773634001
```

## 生成的文件结构
```
skill-1773634001/
├── SKILL.md
├── scripts/
│   ├── main.py
│   └── quest_manager.py
├── examples/
│   └── quest-creation-example.md
└── references/
    └── quest-templates.md
```

## 生成的SKILL.md内容
```yaml
---
name: skill-1773634001
description: 用于处理任务数据的工具，能够创建新任务、修改任务奖励，并且支持任务链管理
allowed-tools: powershell, cmd, Edit, Read, Write, RunCommand
---

# skill-1773634001 使用指南

## 功能介绍
用于处理任务数据的工具，能够创建新任务、修改任务奖励，并且支持任务链管理

## 核心功能
- 创建新任务
- 修改任务奖励
- 管理任务链
- 导出任务数据
```