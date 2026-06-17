# 工具使用手册

每个脚本通过 `--help` 查看完整参数。以下是快速参考。

## 计算工具

### eval_expr.py
安全表达式求值（ast白名单，拒绝 `eval()`）。

```
echo '{"expr":"x**2+2*x+1","vars":{"x":3}}' | python eval_expr.py
python eval_expr.py --expr "sin(pi/6)+sqrt(9)"
python eval_expr.py --table --expr "x+y" --vars '[{"x":1,"y":2},{"x":3,"y":4}]'
python eval_expr.py --precision 50 --expr "1/3"
```

### eval_table.py
批量表格求值：读取 CSV/JSON，对每行执行表达式，添加新列，聚合排序。

```
python eval_table.py --csv data.csv --expr "damage = atk*(1+crit)" --format json
python eval_table.py --json rows.json --expr "z=x+y" --where "x>0"
echo '{"rows":[...]}' | python eval_table.py --expr "y=x*2"
```

### calc_sym.py
单/多变量微积分（sympy + scipy）。

```
python calc_sym.py --expr "x**2+3*x+2" --op "diff" --var "x" --point 2
python calc_sym.py --expr "sin(x)" --op "integrate" --var "x" --a 0 --b pi
python calc_sym.py --expr "x**3-2*x-5" --op "root" --var "x" --guess 2
python calc_sym.py --expr "x**2+y**2" --op "gradient" --vars '["x","y"]' --point-list "[1,2]"
python calc_sym.py --expr "x**3+y**3" --op "hessian" --vars '["x","y"]'
```

### vec_ops.py
向量矩阵 + 四元数旋转。

```
echo '{"op":"dot","a":[1,2,3],"b":[4,5,6]}' | python vec_ops.py
python vec_ops.py --op "lerp" --a "[0,0]" --b "[10,10]" --t 0.5
python vec_ops.py --op "quat_from_axis_angle" --axis "[0,1,0]" --angle 90
python vec_ops.py --op "quat_slerp" --q1 "[1,0,0,0]" --q2 "[0.707,0,0.707,0]" --t 0.5
```

### stats_tools.py
统计 + CDF + 蒙特卡洛。

```
echo '{"op":"describe","data":[1,2,3,4,5]}' | python stats_tools.py
python stats_tools.py --op "cdf_build" --items '[{"value":1,"weight":10},{"value":2,"weight":30}]'
python stats_tools.py --op "monte_carlo" --samples 10000 --expr "x+y" --dists '[...]'
```

### series_tools.py
泰勒展开 / FFT / 牛顿法 / 二分法。

```
python series_tools.py --op "taylor" --expr "sin(x)" --point 0 --order 5
python series_tools.py --op "fft" --data "[0,1,0,-1]" --dt 1.0
python series_tools.py --op "newton" --expr "x**3-2*x-5" --guess 2
```

## 感觉工具

### curve_tools.py
叙事引擎：采样 → 拟合 → 多尺度文字描述。

```
python curve_tools.py --op "sample" --expr "sin(x)" --range "[0,6.28]" --n 100
python curve_tools.py --op "narrate" --expr "x**3-3*x" --range "[-2,2]"
python curve_tools.py --op "multi_scale" --expr "exp(-x**2)*sin(5*x)" --range "[0,3]"
python curve_tools.py --op "describe" --expr "sin(x)" --mode "narrative"
```

### formula_desc.py
公式↔描述互转（64条知识库 + 方法论推荐）。

```
python formula_desc.py --op "lookup" --query "导数定义"
python formula_desc.py --op "search" --query "三角形三边求面积"
python formula_desc.py --op "method" --problem "优化最优配置"
python formula_desc.py --op "describe" --formula "e^(i*pi)+1"
```

### formula_explain.py
公式拆解 + 分层讲解路径生成。

```
python formula_explain.py --op "analyze" --expr "exp(-x**2/(2*s**2))/(s*sqrt(2*pi))"
python formula_explain.py --op "explain" --expr "P(A|B)=P(B|A)P(A)/P(B)"
```

### scale_sense.py
数量感：数值 → 类比/比例语言。

```
python scale_sense.py --op "compare" --a 1000000 --b 1000 --label-a "服务器QPS" --label-b "路由器QPS"
python scale_sense.py --op "analogy" --value 150000 --category "length"
python scale_sense.py --op "proportion" --ratio 0.037
```

### complex_tools.py
复数运算 + 几何解释。

```
python complex_tools.py --op "rect_to_polar" --a 3 --b 4
python complex_tools.py --op "rotate" --a 1 --b 0 --angle 90
python complex_tools.py --op "roots" --a 1 --b 0 --n 3
```

### plot_tools.py
曲线图/直方图/散点图（matplotlib）。

```
python plot_tools.py --op "curve" --expr "sin(x)*exp(-0.1*x)" --range "[0,20]"
python plot_tools.py --op "histogram" --data "[1,2,2,3,3,3,4,4,5]"
python plot_tools.py --op "comparison" --exprs '["sin(x)","cos(x)"]' --range "[0,6.28]"
```

### latex_tools.py
LaTeX ↔ Python 表达式互转。

```
python latex_tools.py --op "latex_to_expr" --latex "\\frac{x^2}{2}"
python latex_tools.py --op "expr_to_latex" --expr "x**2/2 + sin(x)"
```

### formula_translate.py
LaTeX ↔ Python/Lua/C++ 代码互转 + 验证。有歧义时标注警告而非盲改。

```
python formula_translate.py --op "latex_to_code" --latex "\\frac{-b+\\sqrt{b^2-4ac}}{2a}" --target "python"
python formula_translate.py --op "latex_to_code" --latex "\\sin(\\theta)" --target "lua"
python formula_translate.py --op "code_to_latex" --code "(-b+sqrt(b**2-4*a*c))/(2*a)" --source "python"
python formula_translate.py --op "verify_translation" --latex "\\sin(x)" --code "sin(x)" --target "python"
```

### formula_compose.py
公式修改 + 从需求创造公式 + 性质验证。函数组件库含增长/饱和/振荡/特殊四类。

```
python formula_compose.py --op "modify" --expr "x**2" --change "乘以衰减因子"
python formula_compose.py --op "compose" --need "需要一个S形曲线，有上下界，在x=0处取0.5"
python formula_compose.py --op "verify" --expr "1/(1+exp(-x))" --properties '["有界","单调递增","值域(0,1)"]'
python formula_compose.py --op "components"
```

### discrete_verify.py
离散采样验证函数性质 + 级数/迭代反向拟合。适用场景：从测试数据反推公式，验证函数是否满足设计约束。

```
python discrete_verify.py --op "check" --expr "x**3-3*x" --range "[-2,2]" --n 200 --properties '["极值点个数=2","过原点"]'
python discrete_verify.py --op "singularities" --expr "sin(x)*exp(-0.1*x)" --range "[0,20]" --n 500
python discrete_verify.py --op "fit_iterative" --points "[[0,1],[1,2.7],[2,7.4],[3,20]]" --method "polynomial"
python discrete_verify.py --op "fit_iterative" --points "[[0,0],[1,0.84],[2,0.91],[3,0.14]]" --method "fourier"
```

## 验证工具

### verify.py
多方法交叉验证框架。

```
echo '{"name":"验证","methods":[...]}' | python verify.py
python verify.py --file verify_plan.json
```

### trig_tools.py
三角恒等式/欧拉公式/正交性验证。

```
python trig_tools.py --op "verify_identity" --lhs "sin(a+b)" --rhs "sin(a)*cos(b)+cos(a)*sin(b)"
python trig_tools.py --op "euler"
python trig_tools.py --op "orthogonality" --n 5
```

### latex_check.py
LaTeX 格式 8 条规则检测 + 修复。

```
python latex_check.py --op "check" --file doc.md
python latex_check.py --op "fix" --file doc.md --output fixed.md
```

## 组合工具

### pipeline.py
Unix 管道串联所有工具。

```
echo '{"pipeline":[...]}' | python pipeline.py
python pipeline.py --chain "python stats_tools.py | python eval_expr.py"
```
