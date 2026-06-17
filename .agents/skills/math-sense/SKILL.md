---
name: math-sense
description: 数感——帮大模型建立数学直觉。引导式的数学助手：不是丢给你一堆工具，而是告诉你"遇到什么问题→走哪条路→用哪个工具→怎么验证"。覆盖公式计算、微积分、向量几何、曲线拟合、统计分析、掉落率推导、技能伤害验算等场景。
user-invocable: true
allowed-tools:
  - Bash(python *)
  - Read
  - Write
  - Grep
  - Glob
---

# 数感

> 大模型做数学容易出错——不是能力不够，是缺少一套可靠的**工作流程**。
> 本 skill 不让你自己摸索。跟着下面的路径走，每一步告诉你用什么工具、怎么验证。

## 遇到数学问题？先判断属于哪类

| 你的情况 | 走这条路 |
|---------|---------|
| "我有一个公式，需要算出数值" | → [路径A：公式计算](#路径a公式计算) |
| "我算了一个结果，不确定对不对" | → [路径B：交叉验证](#路径b交叉验证) |
| "我有一段数据/采样点，想找规律" | → [路径C：数据建模](#路径c从数据找规律) |
| "我想理解一个公式的含义" | → [路径D：理解公式](#路径d理解一个公式) |
| "我要创造或修改一个公式" | → [路径E：公式工程](#路径e创造或修改公式) |
| "我遇到了空间/方向/坐标系问题" | → [路径F：空间推理](#路径f空间推理) |
| "我需要证明一个命题" | → [路径G：数学证明](#路径g数学证明) |

---

## 路径A：公式计算

**第1步** — 用安全求值器算结果
```bash
echo '{"expr":"你的表达式","vars":{"x":3,"y":5}}' | python eval_expr.py
```
- 单次计算用 `eval_expr`，批量数据用 `eval_table`
- 禁止心算、禁止手算——全部交给工具

**第2步** — 如果涉及微积分，用符号引擎
```bash
python calc_sym.py --expr "你的表达式" --op "diff" --var "x"  # 求导
python calc_sym.py --expr "你的表达式" --op "integrate" --var "x" --a 0 --b 1  # 定积分
```
- 多变量：`partial_diff` `gradient` `hessian`

**第3步** — 用不同语言/工具交叉确认（见路径B）

---

## 路径B：交叉验证

**原则**：一个结果不算数，至少用两种方法确认。

**第1步** — 符号验证
```bash
python calc_sym.py --expr "你的表达式" --op "eval"  # sympy 精确求值
```

**第2步** — 数值验证
```bash
python eval_expr.py --expr "你的表达式" --vars '{...}'  # 手工代入计算
```

**第3步** — 统计验证（如果是概率问题）
```bash
python stats_tools.py --op "monte_carlo" --samples 10000 --expr "你的表达式" ...
```

**第4步** — 自动对比
```bash
python verify.py  # 输入验证计划 JSON，自动调度以上方法并出报告
```

---

## 路径C：从数据找规律

**第1步** — 描述数据特征
```bash
python stats_tools.py --op "describe" --data "[...]"  # 均值/方差/分布
python curve_tools.py --op "narrate" --points "[[x1,y1],...]"  # 叙事描述
```

**第2步** — 尝试拟合
```bash
python curve_tools.py --op "fit_auto" --points "[[x1,y1],...]"  # 自动尝试多种模型
python discrete_verify.py --op "fit_iterative" --points "..." --method "polynomial"  # 迭代拟合
```

**第3步** — 验证拟合结果
```bash
python discrete_verify.py --op "check" --expr "拟合出的公式" --properties '["单调递增","过原点"]'
```

---

## 路径D：理解一个公式

**第1步** — 查知识库看有没有已知解释
```bash
python formula_desc.py --op "lookup" --query "你的公式关键词"  # 正向查
python formula_desc.py --op "search" --query "用语言描述"  # 反向搜
```

**第2步** — 生成叙事描述
```bash
python curve_tools.py --op "narrate" --expr "你的公式" --range "[a,b]"
```

**第3步** — 生成讲解路径（如果公式复杂）
```bash
python formula_explain.py --op "explain" --expr "你的公式"
```
- 会输出：复杂度分析 → 拆解 → 分层讲解步骤 → 预判读者疑问

**第4步** — 画图直观化
```bash
python plot_tools.py --op "curve" --expr "你的公式" --range "[a,b]"
```

**第5步** — 找类比感受数量级
```bash
python scale_sense.py --op "analogy" --value 计算结果 --category "length"
```

---

## 路径E：创造或修改公式

**第1步** — 从需求找候选公式
```bash
python formula_compose.py --op "compose" --need "需要一个S形曲线，x=0处取0.5"
```

**第2步** — 修改现有公式
```bash
python formula_compose.py --op "modify" --expr "现有公式" --change "乘以衰减因子"
```

**第3步** — 验证新公式是否满足需求
```bash
python formula_compose.py --op "verify" --expr "新公式" --properties '["有界","单调递增"]'
```

**第4步** — 离散采样最终确认
```bash
python discrete_verify.py --op "check" --expr "新公式" --range "[0,100]" --properties '["极值点个数=1"]'
```

---

## 路径F：空间推理

**第1步** — 把语言描述转为数学表达
```bash
python spatial_sense.py --op "describe_to_math" --desc "相机在角色后方5米，偏左30度"
```

**第2步** — 计算相对位置/距离/方位
```bash
python spatial_sense.py --op "relative" --a "角色坐标" --b "目标坐标" --a-facing 朝向角度
```

**第3步** — 坐标系转换
```bash
python spatial_sense.py --op "coordinate_convert" --x ... --y ... --z ... --from-sys cartesian --to-sys spherical
python spatial_sense.py --op "transform" --point "..." --from-frame world --to-frame camera --camera-pos "..." --camera-yaw ...
```

**第4步** — 四元数旋转（如果需要平滑旋转）
```bash
python vec_ops.py --op "quat_slerp" --q1 "..." --q2 "..." --t 0.5
```

---

## 路径G：数学证明

提供 23 个正交化 Python 工具和 81 条知识条目。

**第1步** — 把问题翻译成数学结构
```bash
# 先查知识库，看有没有已知的数学模型匹配这个问题
python formula_desc.py --op "search" --query "用自然语言描述你的问题"
```
- 关键：识别问题中的数学结构——是"优化"？"周期"？"概率"？"递推"？
- 如果找不到直接匹配，加载 `references/knowledge-methods.md` 看分层索引

**第2步** — 根据问题特征，获取推荐的证明方法
```bash
python formula_desc.py --op "method" --problem "你的问题特征关键词"
```
- 返回：推荐方法 + 为什么适用 + 反例约束（什么情况下不适用）
- 如果返回多条，选 `strength="strong"` 的优先

**第3步** — 用符号引擎做形式化推导
```bash
# 如果是恒等式 → 符号化简验证
python trig_tools.py --op "verify_identity" --lhs "左边" --rhs "右边"

# 如果是代数式 → sympy 化简
python calc_sym.py --expr "你的表达式" --op "simplify"

# 如果是方程 → 求解根
python calc_sym.py --expr "你的表达式" --op "solve" --var "x"

# 如果是极值问题 → 求导+求驻点
python calc_sym.py --expr "你的表达式" --op "diff" --var "x"
python series_tools.py --op "newton" --expr "导数=0" --guess 初始值
```

**第4步** — 数值验证（用具体数值代入，确认推导正确）
```bash
# 随机取 30+ 个点验算
python verify.py --file verify_plan.json
# verify_plan.json: {"methods":[
#   {"name":"符号推导","tool":"python calc_sym.py","input":{...}},
#   {"name":"数值代入","tool":"python eval_expr.py","input":{...}},
#   {"name":"蒙特卡洛","tool":"python stats_tools.py","input":{...}}
# ],"consensus":"all"}
```

**第5步** — 检查反例约束
- 回到第2步返回的 `counter_example`，确认你的问题不落在反例范围内
- 如果落在反例范围 → 该方法不适用，回到第2步换一个方法

> **常见陷阱**：数值验证通过 ≠ 数学证明成立。数值验证是"没找到反例"，不是"不存在反例"。对于严格证明，符号推导（第3步）是必需的。


---

## 知识查询

- **公式含义**：`formula_desc lookup "关键词"`
- **反查公式**：`formula_desc search "描述"`
- **推荐方法**：`formula_desc method "问题特征"`
- **全部类别**：`formula_desc categories`
- **浏览某类**：`formula_desc list --category calculus`
- **知识库总览**：加载 `references/knowledge-base.md`
- **方法论索引**：加载 `references/knowledge-methods.md`

## 参考文档（渐进式披露）

> 文档按需加载——SKILL.md 是入口，具体内容在 references/ 下，根据触发条件分派。
> 全面索引见 `references/README.md`

| 需要什么 | 触发词 | 加载哪个 |
|---------|--------|---------|
| 所有工具的命令速查 | "怎么用""命令""参数""示例" | `references/tool-manual.md` |
| 验证策略和方法选择 | "验证""交叉验证""验算""复核" | `references/verify-strategy.md` |
| 浮点精度陷阱和误差控制 | "精度""误差""浮点""舍入""溢出" | `references/error-control.md` |
| 知识库全部条目索引 | "查找公式""有什么条目""索引" | `references/knowledge-base.md` |
| 概率论与统计深度讲解 | "概率""统计""分布""期望""方差" | `references/knowledge-probability.md` |
| 方法论套用指南 | "怎么证明""方法选择""适用条件" | `references/knowledge-methods.md` |
| 补充领域（数论/组合/DE/控制论） | "素数""排列""微分方程""PID" | `references/knowledge-extra.md` |
| 微积分概念详解 | "导数""积分""极限""链式法则""泰勒" | `references/knowledge-calculus.md` |
| FFT 完整推导 | "FFT""傅里叶变换""频谱""频域" | `references/knowledge-fft.md` |
| 三角函数全系参考 | "三角""sin""cos""海伦""正弦定理" | `references/trig_tools.md` |
| 数学史话/举一反三/联想发散 | "故事""历史""发现""联想""举一反三" | `references/math-stories.md` |
| 需要灵感和直觉 | "直觉""感觉""形象""类比""想象" | `references/stories/` 按索引选读 |
| 坐标系/手系转换+欧拉角↔四元数 | "左手""右手""坐标系""万向节锁" | `references/coordinate-systems.md` |
| 碰撞检测/几何体求交 | "碰撞""相交""胶囊体""球体""AABB""Box" | `scripts/collision_tools.py` |
| 复数运算/极坐标/棣莫弗 | "复数""虚数""极坐标""棣莫弗""旋转" | `scripts/complex_tools.py` |
| 公式代码互转(LaTeX↔Python/Lua/C++) | "LaTeX转代码""公式转Python""代码转公式" | `scripts/formula_translate.py` |
| LaTeX格式化/检查/互转 | "LaTeX""latex""公式格式""排版" | `scripts/latex_tools.py` |

## 联想触发

> 以下场景应主动加载 `references/math-stories.md` 建立跨领域联想：

| 触发场景 | 加载后能获得什么 |
|---------|-----------------|
| 用户问"这个公式怎么来的""谁发明的" | 8个历史故事（哈雷/牛顿/欧拉/贝叶斯/傅里叶/PageRank/七桥/四色） |
| 需要解释方法的应用价值 | 8个CS案例（SVD→Netflix, FFT→JPEG, 梯度→AlphaGo…） |
| 看到问题需要举一反三 | 游戏场景→数学方法对照表 |
| 用户说"这个太难了""数学好枯燥" | 生动的故事让数学变得有趣 |

## 铁律

1. **禁心算** — 任何数值计算交给 `eval_expr`
2. **禁单信** — 一个结果至少用两种方法验证
3. **先理解再计算** — 先查知识库建立直觉
4. **不确定就追问** — 公式转换有歧义时标注警告而非盲改
5. **分层讲解** — 复杂公式先拆解再逐层解释