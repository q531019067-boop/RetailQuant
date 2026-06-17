# 基本示例

## 功能说明
本示例展示如何使用skill生成器创建一个基本的Skill。

## 输入输出示例

### 输入：
```
我需要一个处理NPC数据的Skill，能够读取和修改NPC模板文件。
```

### 输出：
```
正在生成skill: skill-1773633999
创建目录结构...
编写SKILL.md文件...
生成脚本文件...
Skill生成完成！
生成路径: K:\Sword3-products\trunk\tools\SKILLS\skill-1773633999
```

## 生成的文件结构
```
skill-1773633999/
├── SKILL.md
├── scripts/
│   └── main.py
├── examples/
└── references/
```

## 生成的SKILL.md内容
```yaml
---
name: skill-1773633999
description: 用于处理NPC数据的工具，能够读取和修改NPC模板文件
allowed-tools: powershell, cmd, Edit, Read, Write, RunCommand
---

# skill-1773633999 使用指南

## 功能介绍
用于处理NPC数据的工具，能够读取和修改NPC模板文件
```