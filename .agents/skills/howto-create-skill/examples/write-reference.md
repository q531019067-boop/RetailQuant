# 场景：写一个简单的 reference

新建 `references/my-feature.md`，格式：

```markdown
# 功能名称

## 用法

​```bash
python scripts/my_tool.py <参数>
​```

## 参数

| 参数 | 说明 |
|------|------|
| 参数名 | 说明 |

## 注意事项

> 重要约束用 blockquote。
```

要点：
- 标题用功能名称，不用"xxx 说明"
- 命令用代码块，可直接复制执行
- 参数用表格，一目了然
- 约束用 `>` blockquote 高亮
