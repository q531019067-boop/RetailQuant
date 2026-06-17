# 曲线与几何 — 采样 + 拟合 + 叙事 + 可视化

## 场景

从 Sword5 的技能伤害测试数据出发，反推伤害减免公式。

### 测试数据（护甲 → 减免比例）

```json
[[0,0],[100,0.09],[200,0.167],[500,0.333],[1000,0.5],[2000,0.667],[5000,0.833]]
```

## Step 1：自适应采样 + 叙事描述

```bash
python curve_tools.py --op "narrate" \
  --points '[[0,0],[100,0.09],[200,0.167],[500,0.333],[1000,0.5],[2000,0.667],[5000,0.833]]'
```

叙事输出示例：
> "在区间 [0, 5000] 上，函数单调递增，增长速率递减（边际效应）。"
> "从采样点分布看，函数呈饱和增长特征，可能符合 armor/(armor+K) 形式。"

## Step 2：自动拟合 — 尝试多种模型

```bash
python curve_tools.py --op "fit_auto" \
  --points '[[0,0],[100,0.09],[200,0.167],[500,0.333],[1000,0.5],[2000,0.667],[5000,0.833]]'
```

输出排名：
1. `log` — R²=0.998
2. `poly2` — R²=0.995
3. `exp` — R²=0.987
...

但真正的公式应该是 `armor/(armor+1000)` — 这是有理函数，不是对数。需要用领域知识修正。

## Step 3：手动验证猜测公式

```bash
# 计算 armor/(armor+1000) 在各点的值
python eval_expr.py --table \
  --expr "armor/(armor+1000)" \
  --vars '[{"armor":0},{"armor":100},{"armor":200},{"armor":500},{"armor":1000},{"armor":2000},{"armor":5000}]'
```

对比测试数据，计算残差：
```bash
python eval_table.py --json test_data.json \
  --expr "residual = actual - armor/(armor+1000)"
```

## Step 4：多尺度分析

```bash
python curve_tools.py --op "multi_scale" \
  --expr "armor/(armor+1000)" --range "[0,5000]"
```

粗/中/细三个尺度确认函数在各分辨率下行为一致。

## Step 5：可视化

```bash
python plot_tools.py --op "comparison" \
  --exprs '["armor/(armor+1000)"]' --range "[0,5000]"
```

## 几何向量示例

计算两个技能作用范围的重叠判断（球体碰撞检测）：

```bash
# 两个技能中心点距离
python vec_ops.py --op "distance" --a "[10,0,5]" --b "[15,3,8]"

# 如果距离 < 半径1 + 半径2，则判定为碰撞
```
