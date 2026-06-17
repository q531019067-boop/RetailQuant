---
name: howto-create-skill
description: Skill 写法指南。本 skill 自身就是示范——结构、写法、路径全部可作为模板复制。
user-invocable: false
---

# 如何写 Skill

**本 skill 就是模板。** 你正在读的 SKILL.md、下面引用的 references、examples、scripts，全部遵循它自己教的规范。新建 skill 时，复制本目录结构，改内容即可。

## 目录结构

```
my-skill/
├── SKILL.md              # 入口（必须）
├── references/           # 详细文档（按主题拆分）
├── examples/             # 工况示例（按场景拆分）
└── scripts/              # Python 脚本（单一功能）
    ├── xxx.py
    ├── linux/xxx.py
    └── windows/xxx.py
```

不需要的目录不建。

## 核心规则

1. **路径不能写死绝对路径** — 禁止 `K:\Sword11\`、`/mnt/k/Sword11` 等硬编码。用相对路径（从仓库根出发）或脚本内 `os.path` 推算。examples 中用 `$S=Source/Tools/AITools/SKILLS/<name>/scripts` 变量。
2. **SKILL.md 只做索引** — 不堆具体命令，列 3 张表指向子文件。
3. **不写反面例子** — 只写正确做法，不写"不要用 xxx"。
4. **做完检查孤岛文件** — skill 目录下每个文件都必须在 SKILL.md 的某张表中被引用。漏掉的文件 = 模型看不见 = 白写。检查方法：`ls -R` 对照 SKILL.md 的 3 张表。
5. **文档拆小，渐进式披露** — 不要写大文件。按使用时机或模块拆成小文档，通过表格互相引用。模型只在需要时才 Read 对应文件，避免一次性灌入大量无关内容。原因：某个流程或原则会在多个子功能里被重复引用，拆出去后各处只需引同一份，节省上下文。
6. **抽象规则必须配示例** — 每条重要原则如果偏抽象，必须在 examples 里写一个代表性例子。大模型没有例子容易跑偏。但示例中禁止写死绝对路径（同规则 1），保证可泛化。

## 写法要点

| 要点 | 说明 | 本 skill 的示范 |
|------|------|----------------|
| Frontmatter 用 YAML | name、description、user-invocable、allowed-tools | 本文件顶部 |
| SKILL.md 只做索引 | 不堆具体命令，列 3 张表指向子文件 | 你正在读的这个文件 |
| references 按主题拆分 | 每个文件聚焦一个主题 | `references/skill-format.md` |
| examples 按场景拆分 | `# 场景：xxx` + 完整操作序列 | `examples/write-reference.md` |
| scripts 单一功能 | 每个脚本只做一件事，命令行传参 | `scripts/hello.py`、`scripts/linux/scan_projects.py` |
| 路径不写死 | 用 `$S` 变量或 `os.path` 推算 | examples 中用 `$S=Source/Tools/AITools/SKILLS/howto-create-skill/scripts` |
| 不写反面例子 | 只写正确做法 | references 中无"不要用 xxx" |
| 无孤岛文件 | 每个文件都在 SKILL.md 表中被引用 | 做完用 `ls -R` 对照 3 张表 |
| 文档拆小 | 按时机/模块拆分，互相引用，渐进式披露 | 不写大文件，需要时才 Read |
| 抽象规则配示例 | 偏抽象的原则必须有代表性例子，但不用绝对路径 | examples 里可泛化的示例 |

## 参考文档表

| 主题 | 文件 | 内容 |
|------|------|------|
| 格式规范 | `references/skill-format.md` | frontmatter、正文、references、examples、scripts 的写法 |
| 路径规范 | `references/paths.md` | 如何引用仓库资源、其他 skill、脚本路径 |

## 示例表

| 场景 | 文件 | 内容 |
|------|------|------|
| 写 reference | `examples/write-reference.md` | 如何写一个参考文档 |
| 写 example | `examples/write-example.md` | 如何写一个工况示例 |
| 写 script | `examples/write-script.md` | 如何写一个 Python 脚本 |

## 脚本表

| 脚本 | 用途 |
|------|------|
| `scripts/hello.py` | 最简脚本示范（问候） |
| `scripts/linux/scan_projects.py` | 扫描目录中的 prj 文件 |
| `scripts/linux/extract_config.py` | 从 prj 提取配置字段 |
| `scripts/windows/list_vs_editions.py` | 列出 VS2019 已安装版本 |

## 参考实例

- 简单工具型 skill：`build/`
- 复杂工作流型 skill：`workflows/autotask/`（含 agents、workflows、hooks）
