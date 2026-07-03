---
name: code-review
description: 多遍代码审查工作流。对项目代码进行系统化 review：架构设计、逻辑正确性、代码结构、类型安全。触发词：review 代码、代码审查、检查代码、代码 review、lint、格式化。
---

# 代码审查工作流 (Code Review Workflow)

本 Skill 规范了对 RetailQuant / rbacktest 项目进行系统化代码审查的标准流程。它指导 AI 代理执行多遍分层 review，覆盖架构设计、逻辑缺陷、结构问题、类型安全、格式规范五个维度。

## 审查流程

```
Pass 0: 架构 + 设计（新增——最先执行）
├── 高内聚低耦合：一个模块是否做了太多事？能否拆成 2-3 个小模块？
├── 封装完整性：私有函数被跨模块引用？配置读取散落在各处？
├── 数据流清晰度：同一个概念（如 results 对象）是否在不同层有统一的结构？
├── 硬编码审计：魔法数字、魔法字符串、路径硬编码假设
├── 循环依赖：import 关系是否形成环？
├── 死代码：废弃的功能、未使用的 CSS class、空的回调
├── 技术债务：旧设计残留（action 概念已移除但代码还在引用）
├── 单一数据源：同一个常量是否在多个位置定义？事件类型是否散落各处？
└── 模块边界：功能划分是否明显？不同职责是否混在一个文件里？

Pass 1: 逻辑 + Bug
├── 死代码、未使用变量/导入
├── 参数未使用、函数签名不一致
├── 边界条件（空列表、除零、None 传播）
├── 可变默认值陷阱（list/dict 作为默认参数）
└── 日期/时间格式不一致

Pass 2: 结构 + 组织
├── 巨石文件拆分（>300 行考虑拆分）
├── 重复代码提取公共函数
├── 模块职责单一性
├── 导入顺序（标准库 → 第三方 → 本地）
└── __init__.py 完整性

Pass 3: 类型 + 文档
├── 函数签名类型注解
├── 返回类型注解（含 Optional/Union）
├── docstring 完整性（参数、返回值、异常）
├── 注释与代码一致性
└── 文档与代码一致性（README 是否反映最新架构）

Pass 4: Lint + Format
├── ruff check（Python）
├── ruff format（Python）
├── prettier（JS/CSS/JSX）
└── 修复所有可自动修复的问题
```

## 涉及的目录

| 目录 | 语言 | Lint 工具 |
|------|------|-----------|
| `rbacktest/backend/` | Python | ruff |
| `rbacktest/tests/` | Python | ruff |
| `rbacktest/tools/` | Python | ruff |
| `rbacktest/frontend/src/` | JavaScript/JSX/CSS | prettier |
| `rbacktest/*.md` | Markdown | markdownlint 人工审查文档一致性 |

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

# Markdown lint（从项目根目录跑，确保读到 .markdownlint.json 配置）
cd /Users/kenshin/dev/github/RetailQuant
npx markdownlint-cli2 rbacktest/*.md docs/*.md .agents/skills/code-review/SKILL.md

# 全量测试
uv run python -m pytest rbacktest/tests/ -q
```

## 审查清单

每次 review 完成后确认以下全部通过：

- [ ] `pytest` 全部通过（当前基准：46 passed）
- [ ] `vitest` 全部通过（当前基准：9 passed）
- [ ] `ruff check` All checks passed
- [ ] `ruff format` 无 diff
- [ ] `prettier --check` All matched files use Prettier code style
- [ ] **文档-代码-测试三者一致**：
  - 修改了函数签名 → 所有调用处和测试调用处同步更新
  - 新增了模块 → 有对应的测试覆盖（至少验证可导入）
  - 删除了功能 → 相关的测试用例同步删除或更新
  - 修改了 API（prop/参数名）→ 前端组件文档和测试同步更新
  - 每个测试的断言值与方法实际返回值一致（不是「恰好通过」而是「正确验证」）
- [ ] 无死代码、无未使用导入、无废弃 CSS class
- [ ] 无循环依赖、无跨模块私有函数引用
- [ ] 所有公共函数有类型注解和 docstring
- [ ] 边界条件已处理（空输入、None、除零）
- [ ] 配置项不硬编码（通过 toml 或环境变量读取）
- [ ] 事件类型/常量有单一定义源，不散落在多个文件
- [ ] 模块职责单一，不混入无关关注点

## 常见问题速查

| 问题 | 修复 |
|------|------|
| E402 (import not at top) | 如因 sys.path 必须先于 import，加 `# noqa: E402` |
| F401 (unused import) | 删除未使用导入 |
| F841 (unused variable) | 删除或以下划线前缀标记 |
| 可变默认值 | `def f(x=[])` → `def f(x=None)` + 内部初始化 |
| 循环导入 | 提取共享定义到独立的 `types.py` / `constants.py` |
| 私有函数跨模块 | 改名去掉 `_` 前缀或暴露公开 API |
| 事件类型散落 | 定义 `class EventType` 单例，所有文件引用它 |
| 配置硬编码 | 写入 `rbacktest.toml`，通过 `load_agent_config()` 读取 |
| 文档-代码-测试不一致 | 修改后立即跑测试验证，函数签名变更 → 同步更新调用处和测试 |
| 测试恰好通过但实际是错的 | 检查断言值是否真的等于代码返回值（不要靠巧合） |
