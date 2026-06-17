# 使用示例

## 场景 1：完整提交流程

用户说"提交代码"时，agent 按以下序列执行：

```bash
# Step 1 — Ruff Lint Gate
python .agents/skills/pre-commit-lint/scripts/pre_commit_lint.py

# 如果 format 未通过，自动修复
ruff format <unformatted_files>

# 如果 check 未通过，尝试自动修复
ruff check --fix <files_with_errors>

# 重新检查
python .agents/skills/pre-commit-lint/scripts/pre_commit_lint.py
# → {"all_pass": true} → 继续

# Step 2 — Git 预检
python .agents/skills/pre-commit-lint/scripts/git_commit_check.py

# 输出示例：
# {
#   "staged": [{"status": "M", "path": "rquant/strategy/factor/multi_factor.py"}],
#   "unstaged": [],
#   "untracked": ["docs/new_feature.md"],
#   "conflicts": [],
#   "large_files": [],
#   "warnings": ["存在 1 个未跟踪文件: docs/new_feature.md"],
#   "all_clear": true
# }

# Step 3 — 生成提交信息
# 基于 git diff --cached --stat 和文件路径自动生成

# Step 4 — 确认并提交
git commit -m "策略引擎: 新增市场情绪因子

- rquant/strategy/factor/multi_factor.py: 新增 SentimentFactor 类"
```

## 场景 2：有未暂存变更

```
git_commit_check.py 返回 unstaged 非空：
  → agent 提醒: "检测到 3 个未暂存的变更文件，是否先 git add？"
  → 用户确认后执行 git add
  → 重新运行 git_commit_check.py
  → 继续提交流程
```

## 场景 3：lint 未通过

```
pre_commit_lint.py 返回 all_pass=false, check.errors 非空：
  → 运行 ruff check --fix 修复
  → 重新检查仍有错误（如 F821 undefined name）
  → agent 报告: "无法自动修复以下 lint 错误，请手动处理："
  → 列出错误详情，中断提交
```

## 场景 4：强制跳过 lint

用户说"跳过 lint 直接提交"：
  → 跳过 Step 1
  → 直接进入 Step 2 Git 预检
  → 警告: "ruff lint 未运行，CI 可能失败"
  → 用户确认后提交
