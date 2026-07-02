---
name: code-review
description: 多遍代码审查工作流。对项目代码进行系统化 review：逻辑正确性、代码结构、类型注解、格式化与 lint。触发词：review 代码、代码审查、检查代码、代码 review、lint、格式化。
---

# 代码审查工作流 (Code Review Workflow)

本 Skill 规范了对 RetailQuant / rbacktest 项目进行系统化代码审查的标准流程。它指导 AI 代理执行多遍分层 review，覆盖逻辑缺陷、结构问题、类型安全、格式规范四个维度，确保每次改动后代码质量一致。

## 审查流程

```
Pass 1: 逻辑 + Bug
├── 死代码、未使用变量/导入
├── 参数未使用、函数签名不一致
├── 边界条件（空列表、除零、None 传播）
├── 可变默认值陷阱（list/dict 作为默认参数）
└── 日期/时间格式不一致

Pass 2: 结构 + 组织
├── 巨石文件拆分（>500 行考虑拆分）
├── 重复代码提取公共函数
├── 模块职责单一性
├── 导入顺序（标准库 → 第三方 → 本地）
└── __init__.py 完整性

Pass 3: 类型 + 文档
├── 函数签名类型注解
├── 返回类型注解（含 Optional/Union）
├── docstring 完整性（参数、返回值、异常）
├── 注释与代码一致性
└── 模块级 docstring

Pass 4: Lint + Format
├── ruff check（Python）
├── ruff format（Python）
├── prettier（JS/CSS/JSX）
├── 修复所有可自动修复的问题
└── 手动修复剩余问题
```

## 涉及的目录

| 目录 | 语言 | Lint 工具 |
|------|------|-----------|
| `rbacktest/backend/` | Python | ruff |
| `rbacktest/tests/` | Python | ruff |
| `rbacktest/tools/` | Python | ruff |
| `rbacktest/frontend/src/` | JavaScript/JSX/CSS | prettier |

## 执行命令

```bash
# Python lint + format
cd /Users/kenshin/dev/github/RetailQuant
uv run ruff check rbacktest/
uv run ruff format rbacktest/

# 前端 format
cd rbacktest/frontend
npx prettier --check src/
npx prettier --write src/

# 全量测试
uv run python -m pytest rbacktest/tests/ -q
```

## 审查清单

每次 review 完成后确认以下全部通过：

- [ ] `pytest` 全部通过（当前基准：63 passed）
- [ ] `ruff check` All checks passed
- [ ] `ruff format` 无 diff
- [ ] `prettier --check` All matched files use Prettier code style
- [ ] 无死代码、无未使用导入
- [ ] 所有公共函数有类型注解和 docstring
- [ ] 边界条件已处理（空输入、None、除零）
- [ ] 日期格式一致（后端返回到前端消费）

## 常见问题速查

| 问题 | 修复 |
|------|------|
| E402 (import not at top) | 如因 sys.path 必须先于 import，加 `# noqa: E402` |
| F541 (f-string no placeholder) | 去掉 `f` 前缀 |
| F401 (unused import) | 删除未使用导入 |
| F841 (unused variable) | 删除或以下划线前缀标记 |
| 可变默认值 | `def f(x=[])` → `def f(x=None)` + 内部初始化 |
| `import json` 在函数内 | 移到文件顶层 |
