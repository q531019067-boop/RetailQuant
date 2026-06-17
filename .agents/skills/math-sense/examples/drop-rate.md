# 掉落率推导 — CDF构建 + 采样验证 + 蒙特卡洛

## 场景

游戏有三个掉落等级：金(10%)、银(30%)、铜(60%)。验证掉落系统是否正确实现了这个概率分布。

## Step 1：构建 CDF

```bash
python stats_tools.py --op "cdf_build" \
  --items '[{"value":"金","weight":10},{"value":"银","weight":30},{"value":"铜","weight":60}]'
```

输出：
- 金：cum_prob = 0.10（区间 [0, 0.10)）
- 银：cum_prob = 0.40（区间 [0.10, 0.40)）
- 铜：cum_prob = 1.00（区间 [0.40, 1.00)）

## Step 2：CDF 采样验证

```bash
python stats_tools.py --op "cdf_sample" \
  --cdf '[{"value":"金","cum_prob":0.1},{"value":"银","cum_prob":0.4},{"value":"铜","cum_prob":1.0}]' \
  --samples 10000 --seed 42
```

输出采样频率，对比理论概率。

## Step 3：蒙特卡洛模拟（自动生成分布）

```bash
python stats_tools.py --op "monte_carlo" --samples 100000 --seed 42 \
  --expr "drop_value" \
  --dists '[{"var":"drop_value","dist":"uniform","params":[0,1]}]'
```

然后对结果做 describe + histogram：

```bash
# 用 eval_expr 的 table 模式处理模拟结果...
```

## Step 4：假设检验

用 `verify.py` 验证"采样分布是否显著偏离理论分布"：

- 理论期望：金10% 银30% 铜60%
- 10000 次采样的实际频率
- 用卡方检验或 K-S 检验
- p > 0.05 → 不能拒绝"分布正确"的原假设

## Step 5：保底机制分析

如果加入保底（连续9次不出金，第10次必出金），计算真实期望概率：

```bash
python series_tools.py --op "newton" \
  --expr "实际金的期望概率公式" --guess 0.15
```

结合马尔可夫链模型：
```bash
# 用 formula_desc.py 查找马尔可夫链方法
python formula_desc.py --op "search" --query "马尔可夫 状态转移"
```
