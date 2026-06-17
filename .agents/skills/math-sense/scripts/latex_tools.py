#!/usr/bin/env python3
"""
latex_tools.py — LaTeX 与函数互转工具

用法:
    echo '{"op":"latex_to_expr","latex":"\\\\frac{x^2}{2} + \\\\sin(x)"}' | python latex_tools.py
    python latex_tools.py --op "expr_to_latex" --expr "x**2/2 + sin(x)"
    python latex_tools.py --op "latex_to_description" --latex "f(x) = x^3 - 3x"

支持的操作:
    latex_to_expr, expr_to_latex, latex_to_curve, latex_to_description,
    points_to_latex_table, poly_to_latex, latex_roundtrip
"""
import sys, json, argparse, re

try:
    import sympy as sp
    HAS_SYMPY = True
except ImportError:
    HAS_SYMPY = False


def _preprocess_latex(s):
    """预处理 LaTeX 字符串：处理常见格式"""
    # 处理 frac
    s = re.sub(r'\\frac\{([^}]*)\}\{([^}]*)\}', r'(\1)/(\2)', s)
    # 处理 sqrt
    s = re.sub(r'\\sqrt\{([^}]*)\}', r'sqrt(\1)', s)
    # 处理指数
    s = re.sub(r'\^\{([^}]*)\}', r'**(\1)', s)
    s = re.sub(r'\^(\w)', r'**\1', s)
    # 处理下标（忽略，只保留变量名）
    s = re.sub(r'_\{([^}]*)\}', r'_\1', s)
    s = re.sub(r'_(\w)', r'', s)  # 去掉简单下标
    # 希腊字母
    greek_map = {
        r'\alpha': 'alpha', r'\beta': 'beta', r'\gamma': 'gamma',
        r'\delta': 'delta', r'\epsilon': 'epsilon', r'\theta': 'theta',
        r'\lambda': 'lambda', r'\mu': 'mu', r'\pi': 'pi',
        r'\sigma': 'sigma', r'\phi': 'phi', r'\omega': 'omega',
        r'\Gamma': 'Gamma', r'\Delta': 'Delta', r'\Theta': 'Theta',
        r'\Lambda': 'Lambda', r'\Pi': 'Pi', r'\Sigma': 'Sigma',
        r'\Phi': 'Phi', r'\Omega': 'Omega',
    }
    for latex_g, py_g in greek_map.items():
        s = s.replace(latex_g, py_g)
    # sin, cos 等
    for func in ['sin', 'cos', 'tan', 'log', 'ln', 'exp', 'arcsin', 'arccos', 'arctan']:
        s = re.sub(r'\\' + func + r'\b', func, s)
    s = s.replace(r'\ln', 'log')
    s = s.replace(r'\cdot', '*')
    s = s.replace(r'\times', '*')
    s = s.replace(r'\left', '')
    s = s.replace(r'\right', '')
    s = s.replace(r'\,', '')
    s = s.replace(r'\{', '{')
    s = s.replace(r'\}', '}')
    # 清理花括号
    s = s.replace('{', '(').replace('}', ')')
    # 清理多余空格
    s = re.sub(r'\s+', '', s)
    return s


def op_latex_to_expr(latex_str):
    """LaTeX → Python/Sympy 表达式"""
    if HAS_SYMPY:
        try:
            # sympy 有内置的 LaTeX 解析器
            from sympy.parsing.latex import parse_latex
            expr = parse_latex(latex_str)
            return {"python_expr": str(expr), "sympy_expr": str(expr), "latex": latex_str,
                    "latex_rendered": sp.latex(expr)}
        except Exception:
            pass

    # 降级：手动转换
    python_expr = _preprocess_latex(latex_str)
    return {"python_expr": python_expr, "latex": latex_str,
            "note": "手动转换（sympy 不可用或解析失败）"}


def op_expr_to_latex(expr_str):
    """Python 表达式 → LaTeX"""
    if HAS_SYMPY:
        try:
            expr = sp.sympify(expr_str)
            latex = sp.latex(expr)
            return {"latex": latex, "python_expr": expr_str, "sympy_expr": str(expr)}
        except Exception:
            pass
    return {"latex": expr_str, "python_expr": expr_str, "note": "手动（sympy 不可用）"}


def op_latex_to_description(latex_str):
    """LaTeX 公式 → 中文文字描述"""
    # 先转表达式
    expr_info = op_latex_to_expr(latex_str)
    python_expr = expr_info.get('python_expr', latex_str)

    # 用 sympy 分析
    description = {}
    if HAS_SYMPY:
        try:
            expr = sp.sympify(python_expr)
            free_vars = list(expr.free_symbols)
            description['variables'] = [str(v) for v in free_vars]

            if len(free_vars) == 1:
                x = free_vars[0]
                # 导数
                deriv = sp.diff(expr, x)
                description['derivative'] = str(deriv)
                # 极值尝试
                try:
                    critical = sp.solve(deriv, x)
                    description['critical_points'] = [str(c) for c in critical]
                except Exception:
                    pass
                # 二阶导数
                deriv2 = sp.diff(expr, x, 2)
                description['second_derivative'] = str(deriv2)
                # 类型判断
                if expr.is_polynomial():
                    degree = sp.degree(expr, x)
                    description['type'] = f'{degree}次多项式'
                elif expr.has(sp.sin, sp.cos, sp.tan):
                    description['type'] = '三角函数'
                elif expr.has(sp.exp):
                    description['type'] = '指数函数'
                elif expr.has(sp.log):
                    description['type'] = '对数函数'
        except Exception as e:
            description['error'] = str(e)

    return {"latex": latex_str, "python_expr": python_expr, "description": description}


def op_poly_to_latex(coefficients, var='x'):
    """多项式系数 → LaTeX 展开式"""
    n = len(coefficients) - 1
    terms = []
    for i, c in enumerate(coefficients):
        power = n - i
        if c == 0:
            continue
        c_str = f"{c:.6g}" if abs(c) != 1 or power == 0 else ("" if c > 0 else "-")
        if power == 0:
            term = f"{c:.6g}"
        elif power == 1:
            term = f"{c_str}{var}"
        else:
            term = f"{c_str}{var}^{{{power}}}"
        if i > 0 and c > 0:
            term = "+" + term
        terms.append(term)
    latex_str = ' '.join(terms)
    return {"latex": latex_str, "coefficients": coefficients}


def op_latex_roundtrip(latex_str):
    """LaTeX → expr → LaTeX，检查往返一致性"""
    step1 = op_latex_to_expr(latex_str)
    py_expr = step1.get('python_expr', '')
    step2 = op_expr_to_latex(py_expr)
    return {
        "original_latex": latex_str,
        "python_expr": py_expr,
        "reconstructed_latex": step2.get('latex', ''),
    }


OPERATIONS = {
    'latex_to_expr': lambda **kw: op_latex_to_expr(kw.get('latex', '')),
    'expr_to_latex': lambda **kw: op_expr_to_latex(kw.get('expr', '')),
    'latex_to_description': lambda **kw: op_latex_to_description(kw.get('latex', '')),
    'poly_to_latex': lambda **kw: op_poly_to_latex(kw.get('coefficients', []), kw.get('var', 'x')),
    'latex_roundtrip': lambda **kw: op_latex_roundtrip(kw.get('latex', '')),
}


def main():
    parser = argparse.ArgumentParser(
        description="LaTeX 与函数互转工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python latex_tools.py --op "latex_to_expr" --latex "\\\\frac{x^2}{2}"
  python latex_tools.py --op "expr_to_latex" --expr "x**2/2 + sin(x)"
    """
    )
    parser.add_argument('json_input', nargs='?', help='JSON 输入')
    parser.add_argument('--op', '-o', help='操作名称')
    parser.add_argument('--latex', help='LaTeX 字符串')
    parser.add_argument('--expr', '-e', help='Python/Sympy 表达式')
    parser.add_argument('--compact', '-c', action='store_true', help='紧凑输出')

    args = parser.parse_args()

    input_data = {}
    if args.json_input:
        input_data = json.loads(args.json_input)
    elif not sys.stdin.isatty():
        raw = sys.stdin.read().strip()
        if raw:
            input_data = json.loads(raw)

    op = args.op or input_data.get('op', '')
    if not op or op not in OPERATIONS:
        print(json.dumps({"ok": False, "error": f"不支持: {op}，可用: {list(OPERATIONS.keys())}"}, ensure_ascii=False))
        sys.exit(1)

    try:
        kwargs = {}
        if 'latex' in input_data or args.latex:
            kwargs['latex'] = args.latex or input_data.get('latex', '')
        if 'expr' in input_data or args.expr:
            kwargs['expr'] = args.expr or input_data.get('expr', '')
        if 'coefficients' in input_data:
            kwargs['coefficients'] = input_data['coefficients']
        if 'var' in input_data:
            kwargs['var'] = input_data['var']

        result = OPERATIONS[op](**kwargs)
        output = {"ok": True, "op": op, **result}
        print(json.dumps(output, ensure_ascii=False, indent=None if args.compact else 2, default=str))
    except Exception as e:
        output = {"ok": False, "error": str(e), "op": op}
        print(json.dumps(output, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
