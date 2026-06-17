# 数感参考文档索引

> 渐进式披露：不要一次性加载全部。SKILL.md 是入口，本文档提供分层导航。

## 第1层：入口

| 文档 | 何时加载 |
|------|---------|
| `../SKILL.md` | 每次激活 skill 时（7条路径引导） |
| 本文档 `README.md` | 需要找参考文档时 |

## 第2层：路径配套（按需加载）

| 路径 | 配套文档 |
|------|---------|
| A.公式计算 | `error-control.md` — 浮点精度、误差控制 |
| A+B.验证 | `verify-strategy.md` — 三层验证金字塔 |
| D.理解公式 | `knowledge-calculus.md` — 微积分16条+同济方法9章 |
| D.理解公式 | `knowledge-probability.md` — 概率统计详解 |
| D.理解公式 | `knowledge-fft.md` — FFT完整推导（傅里叶级数→蝴蝶运算） |
| D.理解公式 | `knowledge-methods.md` — 方法论分层索引 |
| D.理解公式 | `knowledge-extra.md` — 数论/组合/微分方程/控制论 |
| D.理解公式 | `knowledge-base.md` — 全部78条目总索引 |
| F.空间推理 | `coordinate-systems.md` — 左手/右手系+引擎对照表 |
| F.三角几何 | `trig_tools.md` — 正弦/余弦/海伦定理+三角形全解 |
| 全部路径 | `tool-manual.md` — 每个脚本的命令示例 |

## 第3层：联想发散（举一反三时加载）

| 文档 | 内容 |
|------|------|
| `math-stories.md` | 数学史话合集（含方法论和游戏启示） |
| `stories/README.md` | 18个独立故事索引（按场景导航） |
| `knowledge-methods.md` | 游戏场景→数学方法对照表 |

## 知识库文档体系

```
knowledge-base.md               ← 总索引（78条目一览）
  ├─ knowledge-calculus.md      ← 微积分16条+同济9章证明方法论
  ├─ knowledge-probability.md   ← 概率统计8条详解
  ├─ knowledge-fft.md           ← FFT完整推导
  ├─ knowledge-methods.md       ← 35条方法论分层索引
  └─ knowledge-extra.md         ← 补充领域
```

> 知识库主体在 `formula_desc.py` 中（78条目）。.md 文档是索引和详解。

## 加载策略

```
遇到问题 → 读 SKILL.md（确定走哪条路径）
         → 读本层对应文档（理解方法）
         → 用 formula_desc lookup 查知识库
         → 用具体工具执行（参考 tool-manual.md）
```

## 脚本工具速查

| 类别 | 脚本 | 典型操作 |
|------|------|---------|
| 计算 | `eval_expr.py` | 安全表达式求值 |
| 计算 | `calc_sym.py` | 求导/积分/偏导/梯度/Hessian/数值积分 |
| 计算 | `vec_ops.py` | 向量运算+四元数+欧拉角↔矩阵 |
| 计算 | `stats_tools.py` | 统计/CDF/蒙特卡洛/PRD/保底/敏感性 |
| 计算 | `series_tools.py` | 泰勒/FFT/牛顿/卷积 |
| 感觉 | `curve_tools.py` | 采样/拟合/叙事描述/多尺度分析 |
| 感觉 | `formula_desc.py` | 公式↔描述互转+78条知识库 |
| 感觉 | `formula_explain.py` | 公式复杂度分析+分层讲解路径 |
| 感觉 | `scale_sense.py` | 数量级类比/比较 |
| 感觉 | `complex_tools.py` | 复数运算/极坐标/棣莫弗 |
| 感觉 | `plot_tools.py` | 曲线图/直方图/ASCII图 |
| 验证 | `verify.py` | 多方法交叉验证框架 |
| 验证 | `discrete_verify.py` | 离散采样+特异点检测+迭代拟合 |
| 验证 | `latex_check.py` | LaTeX格式检查/修复 |
| 组合 | `pipeline.py` | Unix管道串联工具 |
| 空间 | `spatial_sense.py` | 坐标系转换/方位描述/参考系变换 |
| 空间 | `collision_tools.py` | 球体/胶囊体/AABB/三角形/椭圆/Box碰撞 |
| 工程 | `formula_translate.py` | LaTeX↔Python/Lua/C++ |
| 工程 | `formula_compose.py` | 公式修改/创造/性质验证 |
