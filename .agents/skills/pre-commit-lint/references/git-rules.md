# Git 提交规则

## 提交信息格式

中文撰写，简洁描述改动内容。不使用 `feat:`、`fix:` 等英文前缀。

格式：
```
<模块>: <简要描述>

- <文件/目录>: <具体改动>
- <文件/目录>: <具体改动>
```

好：
```
策略引擎: 新增市场情绪因子，优化 VpBreakout 量比阈值

- rquant/strategy/factor/multi_factor.py: 新增 SentimentFactor 类
- rquant/data_source/sina.py: 新增市场情绪数据抓取
- docs/strategy设计详解.md: 更新因子列表
```

不好：
```
feat: add sentiment factor

- Updated factor.py with new logic
```

## 目录 → 提交信息映射

| 变更文件所在目录 | 建议的提交信息前缀 |
|-----------------|-------------------|
| `rquant/strategy/` | 策略引擎: ... |
| `rquant/data_source/` | 数据源: ... |
| `rquant/business/` | 业务层: ... |
| `rquant/web/` | Web 层: ... |
| `templates/` | 前端: ... |
| `static/` | 前端样式: ... |
| `docs/` | 文档: ... |
| `tests/` | 测试: ... |
| `scripts/` | 工具脚本: ... |
| `.github/workflows/` | CI: ... |
| `pyproject.toml` | 项目配置: ... |
| `requirements.txt` | 依赖: ... |

## 忽略文件

以下文件/目录不应提交：

```
__pycache__/  *.pyc  .venv/  venv/  .pytest_cache/  .ruff_cache/
*.egg-info/  .DS_Store  Thumbs.db
cache/rquant.db-shm  cache/rquant.db-wal  cache/*.json
```

## 常见被拒原因

| 原因 | 解决 |
|------|------|
| ruff check 未通过 | 运行 `ruff check --fix` 修复 |
| ruff format 未通过 | 运行 `ruff format` 格式化 |
| 有冲突标记 | 解决合并冲突后再提交 |
| 暂存区为空 | 先 `git add <files>` |
| 大文件 (>1MB) | 确认是否需要提交，考虑用 Git LFS |
