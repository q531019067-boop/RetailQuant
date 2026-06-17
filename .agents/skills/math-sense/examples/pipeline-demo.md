# 管道组合演示 — 工具串联完整流程

## 核心理念

Unix 哲学：每个工具做一件事并做好，通过管道串联完成复杂任务。

## 场景：技能伤害完整分析管道

### 管道定义

```json
{
  "pipeline": [
    {
      "stage": "sample_attributes",
      "tool": "python eval_expr.py",
      "op": "table",
      "args": {
        "expr": "[atk, crit, armor]",
        "vars": [
          {"atk": 800, "crit": 0.3, "armor": 500},
          {"atk": 1000, "crit": 0.5, "armor": 300},
          {"atk": 600, "crit": 0.2, "armor": 800}
        ]
      },
      "output_key": "attributes"
    },
    {
      "stage": "calc_damage",
      "tool": "python eval_table.py",
      "args": {
        "expr": "dmg = atk*2.5*(1+crit*2.0)*(1-armor/(armor+1000))*1.05"
      }
    },
    {
      "stage": "describe_stats",
      "tool": "python stats_tools.py",
      "args": {"op": "describe", "data": "$prev.rows[*].dmg"}
    },
    {
      "stage": "verify",
      "tool": "python verify.py",
      "args": {
        "methods": [
          {"name":"期望伤害检查","tool":"python eval_expr.py","input":{"expr":"$prev.mean","vars":{}},"expected":2000,"tolerance":500}
        ]
      }
    }
  ]
}
```

### 执行

```bash
echo '上面JSON' | python pipeline.py --verbose
```

## 简单链模式

```bash
# 生成随机属性 → 计算伤害 → 统计分布
python pipeline.py --chain \
  "python stats_tools.py --op monte_carlo --samples 1000 --expr 'atk+crit' --dists '[{\"var\":\"atk\",\"dist\":\"uniform\",\"params\":[500,1500]},{\"var\":\"crit\",\"dist\":\"uniform\",\"params\":[0,1]}]' | python eval_table.py --expr 'dmg = atk*2.5*(1+crit*2.0)'"
```

## 常用管道模式

| 模式 | 组合 |
|------|------|
| 采样→统计 | `stats_tools monte_carlo \| stats_tools describe` |
| 曲线→叙事 | `curve_tools sample \| curve_tools narrate` |
| 求值→验证 | `eval_expr \| verify` |
| 公式→讲解 | `formula_explain analyze \| formula_desc describe` |
| 数据→图表 | `stats_tools describe \| plot_tools histogram` |
