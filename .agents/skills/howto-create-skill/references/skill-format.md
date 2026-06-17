# Skill 格式规范

## 核心规则

**禁止写死绝对路径。** 禁止 `K:\Sword11\`、`/mnt/k/Sword11`、`C:\Users\xxx` 等硬编码路径出现在 SKILL.md、references、examples、scripts 中。用相对路径或脚本内 `os.path` 推算。

## Frontmatter（YAML）

```yaml
---
name: my-skill                    # 必须，与目录名一致
description: 一句话触发条件。      # 必须，出现在 skill 列表中
user-invocable: true              # true=用户可 /name 调用，false=仅被引用
allowed-tools:                    # 声明使用的工具
  - Bash(python *)
  - Read
  - Write
  - Edit
  - Glob
  - Grep
---
```

### 字段说明

| 字段 | 必须 | 说明 |
|------|------|------|
| `name` | 是 | skill 名称，与目录名一致 |
| `description` | 是 | 触发条件描述，中文。写"什么时候用"，不写"功能是什么" |
| `user-invocable` | 否 | 默认 true。设为 false 则不出现在 `/` 列表中，仅被其他 skill 引用 |
| `allowed-tools` | 否 | 声明 skill 可使用的工具。省略则不限制 |

### allowed-tools 常用模式

| 模式 | 说明 |
|------|------|
| `Bash(python *)` | 允许执行 python 命令 |
| `Bash(msbuild *)` | 允许执行 msbuild |
| `Bash(mk *)` | 允许执行 mk |
| `Bash(cp *)` | 允许执行 cp |
| `Bash(svn log *)` | 允许执行 svn log（* 匹配任意参数） |
| `Read` | 允许读文件 |
| `Write` | 允许写文件 |
| `Edit` | 允许编辑文件 |
| `Glob` | 允许搜索文件名 |
| `Grep` | 允许搜索文件内容 |
| `Agent` | 允许拉起子 agent |
| `TeamCreate` | 允许创建团队 |
| `SendMessage` | 允许发送消息 |

> `Bash(command *)` 中的 `*` 匹配任意参数。写具体命令，不要写 `Bash(*)` 全放行。

## SKILL.md 正文

只做索引，列 3 张表：

1. **参考文档表**：主题 → 文件 → 内容
2. **示例表**：场景 → 文件 → 内容
3. **脚本表**：脚本 → 用途

> SKILL.md 控制在 50 行以内。具体命令、参数、配置全部放 references。

## References 写法

- 每个文件聚焦一个主题
- 命令用代码块，参数用表格
- 重要约束用 `>` blockquote
- 不写反面例子，只写正确做法

## Examples 写法

- 每个文件覆盖一组相关场景
- 格式：`# 场景：xxx` + 完整操作序列
- 路径用变量，不写死：`$S=Source/Tools/AITools/SKILLS/<name>/scripts`

## Scripts 写法

- 统一用 Python（.py）
- 每个脚本只做一件事
- 命令行传参（`sys.argv` 或 `argparse`）
- 确定性：相同输入相同输出
- 错误输出 stderr，退出码 0=成功 1=失败
- 顶部 docstring 写用法示例
- 脚本间通过 `subprocess.run([sys.executable, ...])` 调用
