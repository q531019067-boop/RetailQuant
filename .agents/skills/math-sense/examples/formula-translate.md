# 公式翻译 — LaTeX ↔ Python/Lua/C++ 互转

## 场景

将数学论文中的公式转换为可执行代码，或将代码公式转回 LaTeX 格式。

## 示例 1：二次公式 LaTeX → Python

```bash
python formula_translate.py --op "latex_to_code" \
  --latex "\\frac{-b+\\sqrt{b^2-4ac}}{2a}" --target "python"
```

输出：`(-b + sqrt(b**2 - 4*a*c))/(2*a)`

## 示例 2：三角函数 LaTeX → Lua

游戏 Lua 脚本中需要数学公式：

```bash
python formula_translate.py --op "latex_to_code" \
  --latex "\\sin(\\theta)\\cdot\\cos(\\phi)" --target "lua"
```

输出：`sin(theta) * cos(phi)`

## 示例 3：Lua 代码 → LaTeX

反过来将 Lua 伤害公式转回 LaTeX 以便文档展示：

```bash
python formula_translate.py --op "code_to_latex" \
  --code "atk * (1 + crit * 2.0) * (1 - armor/(armor + 1000))" --source "python"
```

## 示例 4：验证转换正确性

用 `verify_translation` 在多个测试点上对比 LaTeX 和代码的数值：

```bash
python formula_translate.py --op "verify_translation" \
  --latex "\\sin(x)" --code "sin(x)" --target "python"
```

输出所有测试点的对比结果，确保转换无误。

## 歧义处理

当遇到 `\pm`、`\int`、分段函数等无法自动转换的结构时，工具会标注警告而非盲改：

```json
{"warnings": ["± 是双值符号，需要手动拆分为两个表达式（+ 和 -）"]}
```
