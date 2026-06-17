---
name: pre-commit-lint
description: Pre-commit quality gate and Git commit workflow. Runs ruff check + ruff format, git status pre-check, auto-generates commit messages, and executes git commit. Trigger phrases include commit, 提交, git commit, 合入, 记录变更, 保存提交, 推送前. The skill ensures all code passes ruff and git pre-checks before any commit lands.
user-invocable: true
allowed-tools:
  - Bash(python *)
  - Bash(git *)
  - Read
  - Write
  - Grep
---

# Pre-commit Lint & Git Commit Gate

一站式 Git 提交流程：lint 检查 → Git 预检 → 生成提交信息 → 确认并提交。

## 工作流（按顺序执行）

### Step 1 — Ruff Lint Gate

```bash
python .agents/skills/pre-commit-lint/scripts/pre_commit_lint.py
```

脚本返回 JSON：
```json
{"check": {"passed": true|false, "errors": [...]}, "format": {"passed": true|false, "unformatted": [...]}, "all_pass": true|false}
```

- 若 `format.passed == false` → 运行 `ruff format <files>` 修复，然后重新检查
- 若 `check.passed == false` → 运行 `ruff check --fix` 修复，然后重新检查
- 仍有不能自动修复的错误 → **中断，报告用户**

### Step 2 — Git 预检

```bash
python .agents/skills/pre-commit-lint/scripts/git_commit_check.py
```

脚本返回 JSON：
```json
{"staged": [...], "unstaged": [...], "untracked": [...], "conflicts": [...], "large_files": [...], "warnings": [...]}
```

检查项：
- **暂存区变更**：`git diff --cached --name-status`
- **未暂存变更**：`git diff --name-status`
- **未跟踪文件**：`git ls-files --others --exclude-standard`
- **冲突标记**：`git diff --check` 检测冲突标记 (`<<<<<<<`)
- **大文件提醒**：>1MB 文件警告

若 `unstaged` 非空 → 提醒用户是否先 `git add`
若 `conflicts` 非空 → **中断，报告冲突文件**

### Step 3 — 生成提交信息

根据以下来源自动生成中文提交信息：
- `git diff --cached --stat` 文件变更统计
- 变更文件所在目录（参考 `references/git-rules.md` 的目录-信息映射）
- 变更内容摘要

生成格式：
```
<模块>: <简要描述>

- <文件1>: <具体改动>
- <文件2>: <具体改动>
```

不使用 `feat:` / `fix:` 等前缀，直接中文描述。

### Step 4 — 确认并提交

展示完整提交计划，包含：
- 暂存区变更清单
- 未暂存文件（如有）
- 建议的提交信息

用户确认后执行：
```bash
git commit -m "<提交信息>"
```

若用户说"跳过 lint"或"强制提交"，跳过 Step 1 但提醒 CI 可能失败。

## 参考文档表

| 主题 | 文件 | 内容 |
|------|------|------|
| Git 提交规则 | `references/git-rules.md` | 提交信息格式、忽略文件、目录映射 |

## 脚本表

| 脚本 | 用途 |
|------|------|
| `scripts/pre_commit_lint.py` | ruff check + ruff format 检查，输出 JSON |
| `scripts/git_commit_check.py` | Git 预检：status / 冲突 / 大文件，输出 JSON |

## 示例表

| 场景 | 文件 | 内容 |
|------|------|------|
| 完整提交流程 | `examples/usage.md` | 从 lint 到 commit 的完整操作序列 |
