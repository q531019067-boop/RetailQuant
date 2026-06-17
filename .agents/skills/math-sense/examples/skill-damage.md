# 技能伤害公式 — 多步骤计算与交叉验证

## 场景

验证 Sword5 游戏中技能伤害公式的正确性。公式为：
```
最终伤害 = 基础攻击力 × 技能系数 × (1 + 暴击率 × 暴击倍率) × (1 - 护甲/(护甲 + 1000)) × 等级修正
```

## Step 1：定义变量和基准值

```
基础攻击力 = 800
技能系数 = 2.5
暴击率 = 0.3
暴击倍率 = 2.0
护甲 = 500
等级修正 = 1.05  (等级差5级，每级+1%)
```

## Step 2：分步手工计算（用 eval_expr）

```bash
# 子表达式1：暴击加成
echo '{"expr":"1 + crit_rate * crit_mult","vars":{"crit_rate":0.3,"crit_mult":2.0}}' \
  | python eval_expr.py
# → 1.6

# 子表达式2：护甲减免
echo '{"expr":"1 - armor/(armor + 1000)","vars":{"armor":500}}' \
  | python eval_expr.py
# → 0.666...

# 最终伤害
echo '{"expr":"base * coef * (1+crit_rate*crit_mult) * (1-armor/(armor+1000)) * lvl","vars":{"base":800,"coef":2.5,"crit_rate":0.3,"crit_mult":2.0,"armor":500,"lvl":1.05}}' \
  | python eval_expr.py
# → 2240.0
```

## Step 3：批量验证（不同属性组合）

创建 `test_cases.json`：
```json
[
  {"atk":800, "coef":2.5, "crit":0.3, "armor":500, "lvl":1.05},
  {"atk":1000,"coef":2.5, "crit":0.5, "armor":300, "lvl":1.10},
  {"atk":600, "coef":3.0, "crit":0.2, "armor":800, "lvl":1.00}
]
```

```bash
python eval_table.py --json test_cases.json \
  --expr "dmg = atk*coef*(1+crit*2.0)*(1-armor/(armor+1000))*lvl"
```

## Step 4：交叉验证

用 `verify.py` 调度三种方法：

```json
{
  "name": "伤害公式验证",
  "methods": [
    {"name":"eval_expr手工","tool":"python eval_expr.py","input":{"expr":"800*2.5*1.6*0.6667*1.05","vars":{}},"expected":2240,"tolerance":1},
    {"name":"sympy符号","tool":"python calc_sym.py","input":{"expr":"800*2.5*1.6*(1-500/1500)*1.05","op":"eval"},"expected":2240,"tolerance":0.01},
    {"name":"蒙特卡洛","tool":"python stats_tools.py","input":{"expr":"atk*coef*(1+crit*2)*(1-armor/(armor+1000))*lvl","distributions":[{"var":"crit","dist":"uniform","params":[0,1]}],"n_samples":10000}}
  ],
  "consensus": "all"
}
```

## Step 5：分析边际收益

用 `calc_sym.py` 计算偏导数——哪个属性对伤害提升最大：

```bash
python calc_sym.py --expr "atk*coef*(1+crit*2.0)*(1-armor/(armor+1000))*lvl" \
  --op "gradient" --vars '["atk","crit","armor"]' --point-list "[800,0.3,500]"
```

梯度分量大小排序 → 得知当前配置下"攻击力"的边际收益最高。
