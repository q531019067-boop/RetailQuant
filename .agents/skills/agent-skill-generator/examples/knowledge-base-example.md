# 知识库类型Skill示例

## 功能说明
本示例展示如何生成一个知识库类型的Skill，用于回答配置相关的问题。

## 输入
```
副本CD配置知识库，用于回答配置方式和文件路径以及潜规则、算法
```

## 输出
```
正在生成skill: dungeon-knowledge-base (类型: knowledge_base)
创建目录结构...
编写SKILL.md文件...
生成脚本文件...
Skill生成完成！
生成路径: K:\Sword3-products\trunk\tools\SKILLS\dungeon-knowledge-base
```

## 生成的文件结构
```
dungeon-knowledge-base/
├── SKILL.md              # 知识库主文档
├── scripts/              # [可选] 脚本目录
├── examples/             # [可选] 示例目录
└── references/           # [必需] 参考资料
    └── config-guide.md   # 配置指南
```

## 使用场景

### 场景1：查询配置规则
**用户**：副本CD的配置规则是什么？

**知识库**：
1. 引用知识库中的规则说明
2. 解释潜规则和算法
3. 提供配置示例

### 场景2：查询文件路径
**用户**：副本配置文件在哪里？

**知识库**：
- 主配置：`${workspaceFolder}/config/dungeon/`
- CD配置：`${workspaceFolder}/config/dungeon/cooldown/`

## 核心特点
- 提供配置相关的知识和规则
- 包含常见问题解答
- 指导如何查询配置信息
- 解释配置规则和潜规则