# 公式加工与创造

## 场景 1：修改现有公式

> "给这个伤害公式加上一个等级衰减因子"

```bash
python formula_compose.py --op "modify" \
  --expr "atk * 2.5 * (1 + crit * 2.0)" \
  --change "乘以衰减因子"
```

输出：`(atk * 2.5 * (1 + crit * 2.0))*exp(-d*x)`

## 场景 2：从需求创造公式

> "需要一个S形曲线，在x=0处取0.5，x→-∞时趋于0，x→+∞时趋于1"

```bash
python formula_compose.py --op "compose" \
  --need "需要一个S形曲线，有上下界，在x=0处取0.5，饱和到1"
```

输出推荐：`sigmoid` 函数 — `1/(1+exp(-k*x))`（调整 k 控制陡峭度）

## 场景 3：验证创造的公式是否满足需求

对候选公式 `1/(1+exp(-x))` 做性质检查：

```bash
python formula_compose.py --op "verify" \
  --expr "1/(1+exp(-x))" \
  --properties '["有界","单调递增","值域(0,1)"]'
```

输出：全部通过 ✓

## 场景 4：查看可用函数组件库

```bash
python formula_compose.py --op "components"
```

输出增长/饱和/振荡/特殊四类函数的表达式和性质，像搭积木一样组合。

## 典型工作流

```
1. compose → 获得候选公式
2. verify  → 验证数学性质
3. modify  → 微调参数和结构
4. discrete_verify → 离散采样最终验证
```
