# 场景：写一个工况示例

新建 `examples/my-scenario.md`，格式：

```markdown
# 场景：用户说"xxx"

S=Source/Tools/AITools/SKILLS/<name>/scripts
python $S/xxx.py <参数>

# 场景：用户说"yyy"

python $S/linux/yyy.py <参数>
```

要点：
- 每个条目以 `# 场景：` 开头，描述用户意图
- 下面是 agent 应执行的完整操作序列
- 路径用 `$S` 变量，不写死
- 展示 agent 的决策过程，不只是命令罗列
