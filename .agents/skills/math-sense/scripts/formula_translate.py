#!/usr/bin/env python3
"""
formula_translate.py — 数学公式↔代码 多语言互转

用法:
    python formula_translate.py --op "latex_to_code" --latex "\\frac{-b\\pm\\sqrt{b^2-4ac}}{2a}" --target "python"
    python formula_translate.py --op "code_to_latex" --code "(-b+sqrt(b**2-4*a*c))/(2*a)" --source "python"
    python formula_translate.py --op "latex_to_code" --latex "\\int_0^1 x^2 dx" --target "lua"
    python formula_translate.py --op "latex_to_code" --latex "\\sin(\\theta)" --target "c++"

支持的操作:
    latex_to_code, code_to_latex, verify_translation
"""
import sys, json, re, math, argparse

try:
    import sympy as sp
    HAS_SYMPY = True
except ImportError:
    HAS_SYMPY = False


# ====================== LaTeX 解析 ======================

def _preprocess_latex(s):
    """将 LaTeX 转为 Python 可解析表达式"""
    # 分式
    s = re.sub(r'\\frac\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}', r'(\1)/(\2)', s)
    s = re.sub(r'\\sqrt\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}', r'sqrt(\1)', s)
    s = re.sub(r'\\sqrt\[(\d+)\]\{([^{}]*)\}', r'(\2)**(1/(\1))', s)
    s = re.sub(r'\^\{([^{}]*)\}', r'**(\1)', s)
    s = re.sub(r'\^(\w+)', r'**\1', s)
    s = re.sub(r'_\{([^{}]*)\}', r'_\1', s)
    s = re.sub(r'_(\w+)', r'', s)
    # 三角函数
    for latex_fn, py_fn in trig_map.items():
        s = re.sub(latex_fn + r'\b', py_fn, s)
    # 对数
    s = re.sub(r'\\ln\b', 'log', s)
    s = re.sub(r'\\log_(\w+)', r'log(\1)', s)
    s = re.sub(r'\\log\{([^}]*)\}', r'log10(\1)', s)
    # 希腊字母
    greek = {'\\\\alpha':'a', '\\\\beta':'b', '\\\\gamma':'g', '\\\\delta':'d', '\\\\epsilon':'e',
             '\\\\theta':'t', '\\\\lambda':'l', '\\\\mu':'m', '\\\\pi':'pi', '\\\\sigma':'s',
             '\\\\phi':'ph', '\\\\omega':'w', '\\\\Gamma':'G', '\\\\Delta':'D', '\\\\Theta':'Th',
             '\\\\Sigma':'S', '\\\\Omega':'W'}
    for gk, py in greek.items():
        s = s.replace(gk, py)
    # 符号
    s = s.replace(r'\cdot', '*').replace(r'\times', '*').replace(r'\pm', '±')
    s = s.replace(r'\mp', '干').replace(r'\infty', 'inf').replace(r'\partial', 'd')
    s = s.replace(r'\int', 'integrate').replace(r'\sum', 'sum').replace(r'\prod', 'prod')
    s = s.replace(r'\left', '').replace(r'\right', '').replace(r'\,', '')
    s = s.replace(r'\{', '{').replace(r'\}', '}')
    # 清理
    s = s.replace('{', '(').replace('}', ')')
    s = re.sub(r'\s+', '', s)
    return s


def _detect_ambiguous(expr_str):
    """检测转换中的歧义"""
    warnings = []
    if '±' in expr_str:
        warnings.append("± 是双值符号，需要手动拆分为两个表达式（+ 和 -）")
    if '干' in expr_str:
        warnings.append("干 符号需要手动处理")
    if re.search(r'integrate|\\int', expr_str):
        warnings.append("积分需要手动指定积分变量和上下限")
    if re.search(r'sum|\\sum', expr_str):
        warnings.append("求和需要手动指定求和范围和变量")
    if re.search(r'\^\{[^}]*\\prime', expr_str):
        warnings.append("导数符号需要明确求导变量和阶数")
    if re.search(r'\\begin\{', expr_str):
        warnings.append("矩阵/分段函数等复杂环境需要手动转换")
    return warnings


# ====================== LaTeX → 代码 ======================

def _to_python(expr_str):
    """LaTeX → Python 代码"""
    # 如果能用 sympy 解析，优先用 sympy 生成
    if HAS_SYMPY:
        try:
            from sympy.parsing.latex import parse_latex
            expr = parse_latex(expr_str)
            py_code = str(expr).replace('**', '**')
            return _format_code(py_code, 'python', expr_str)
        except Exception:
            pass
    # 降级：手动转换
    py_expr = _preprocess_latex(expr_str)
    return _format_code(py_expr, 'python', expr_str)


def _to_lua(expr_str):
    """LaTeX → Lua 代码"""
    py_expr = _preprocess_latex(expr_str) if not HAS_SYMPY else _try_sympy(expr_str)
    # Lua 语法差异
    lua = py_expr.replace('**', '^')           # Python ** → Lua ^
    lua = lua.replace(' and ', ' and ')         # 逻辑
    lua = lua.replace(' or ', ' or ')
    lua = lua.replace(' not ', 'not ')
    lua = lua.replace('True', 'true').replace('False', 'false')
    lua = lua.replace('None', 'nil')
    lua = lua.replace('math.', 'math.')         # math 模块相同
    lua = lua.replace('inf', 'math.huge')
    return _format_code(lua, 'lua', expr_str)


def _to_cpp(expr_str):
    """LaTeX → C++ 代码"""
    py_expr = _preprocess_latex(expr_str) if not HAS_SYMPY else _try_sympy(expr_str)
    # C++ 语法差异
    cpp = py_expr
    cpp = cpp.replace('**', 'std::pow(')        # 需要特殊处理幂
    # 简单幂转换：x**n → std::pow(x, n)
    cpp = re.sub(r'(\w+)\*\*(\d+)', r'std::pow(\1, \2)', cpp)
    cpp = re.sub(r'\(([^)]+)\)\*\*(\d+)', r'std::pow(\1, \2)', cpp)
    cpp = cpp.replace('sin(', 'std::sin(').replace('cos(', 'std::cos(')
    cpp = cpp.replace('tan(', 'std::tan(').replace('sqrt(', 'std::sqrt(')
    cpp = cpp.replace('log(', 'std::log(').replace('exp(', 'std::exp(')
    cpp = cpp.replace('abs(', 'std::abs(').replace('fabs(', 'std::fabs(')
    cpp = cpp.replace('pow(', 'std::pow(')
    cpp = cpp.replace('pi', 'M_PI').replace('inf', 'std::numeric_limits<double>::infinity()')
    cpp = cpp.replace('True', 'true').replace('False', 'false')
    return _format_code(cpp, 'c++', expr_str)


def _try_sympy(expr_str):
    """尝试 sympy 解析"""
    try:
        from sympy.parsing.latex import parse_latex
        return str(parse_latex(expr_str))
    except Exception:
        return _preprocess_latex(expr_str)


def _format_code(code, target, original_latex):
    """格式化输出"""
    warnings = _detect_ambiguous(original_latex)
    return {
        "code": code,
        "language": target,
        "original_latex": original_latex,
        "warnings": warnings,
        "note": f"已转换为 {target.upper()} 代码" if not warnings else f"含 {len(warnings)} 个歧义需要手动处理",
    }


# ====================== 代码 → LaTeX ======================

CODE_TO_LATEX_MAP = {
    'python': {
        '**': lambda m: '^{' + m.group(2) + '}',
        'sqrt': lambda m: r'\sqrt{' + m.group(1) + '}',
    },
}

def _code_to_latex(code_str, source_lang):
    """Python/Lua/C++ 代码 → LaTeX"""
    if HAS_SYMPY:
        try:
            expr = sp.sympify(code_str)
            latex = sp.latex(expr)
            return {"latex": latex, "code": code_str, "language": source_lang, "verified": True}
        except Exception:
            pass

    # 手动转换
    latex = code_str
    # Python **n → ^{n}
    latex = re.sub(r'\*\*(\{?\d+\}?)', lambda m: '^{' + m.group(1).strip('{}') + '}', latex)
    latex = re.sub(r'\*\*(\w+)', r'^{\1}', latex)
    # sqrt(x) → \sqrt{x}
    latex = re.sub(r'sqrt\(([^)]+)\)', r'\\sqrt{\1}', latex)
    # sin/cos/tan
    for fn in ['sin', 'cos', 'tan', 'log', 'exp']:
        latex = re.sub(fn + r'\(([^)]+)\)', rf'\\{fn}{{\1}}', latex)
    # 乘除
    latex = latex.replace('*', r' \cdot ').replace('/', '}{')
    # 分数：如果还有 (a)/(b) 模式
    latex = re.sub(r'\(([^)]+)\)/\(([^)]+)\)', r'\\frac{\1}{\2}', latex)
    latex = re.sub(r'(\w+)/(\w+)', r'\\frac{\1}{\2}', latex)
    latex = latex.replace('pi', r'\pi').replace('inf', r'\infty')

    return {"latex": latex, "code": code_str, "language": source_lang, "verified": False,
            "note": "手动转换（未通过 sympy 验证）"}


# ====================== 验证转换 ======================

def _eval_safe(expr_str, vars_dict):
    """安全求值（复用 eval_expr 逻辑）"""
    import ast as _ast, math as _math, operator as _op
    ALLOWED = {'sin':_math.sin,'cos':_math.cos,'tan':_math.tan,'exp':_math.exp,'log':_math.log,
               'sqrt':_math.sqrt,'abs':abs,'pow':pow,'pi':_math.pi,'e':_math.e}
    try:
        tree = _ast.parse(expr_str.strip(), mode='eval')
        def _ev(n):
            if isinstance(n, _ast.Constant): return n.value
            if isinstance(n, _ast.Name):
                if n.id in vars_dict: return vars_dict[n.id]
                if n.id in ALLOWED: return ALLOWED[n.id]
                raise NameError(n.id)
            if isinstance(n, _ast.BinOp):
                l,r=_ev(n.left),_ev(n.right)
                o={_ast.Add:_op.add,_ast.Sub:_op.sub,_ast.Mult:_op.mul,_ast.Div:_op.truediv,_ast.Pow:_op.pow}
                return o[type(n.op)](l,r)
            if isinstance(n, _ast.UnaryOp):
                v=_ev(n.operand); return -v if isinstance(n.op,_ast.USub) else +v
            if isinstance(n, _ast.Call):
                fn=_ev(n.func); return fn(*[_ev(a) for a in n.args])
            raise ValueError(type(n).__name__)
        return _ev(tree.body)
    except Exception as e:
        return f"ERROR: {e}"


def op_verify_translation(latex_str, code_str, target_lang, test_points=None):
    """验证 LaTeX 和生成的代码在数值上等价"""
    if test_points is None:
        test_points = [{"x": v} for v in [0.1, 0.5, 1.0, 2.0, 3.0]]

    # 从 LaTeX 解析
    latex_expr = _preprocess_latex(latex_str)

    results = []
    all_match = True
    for pt in test_points:
        v_latex = _eval_safe(latex_expr, pt)
        v_code = _eval_safe(code_str, pt)
        if isinstance(v_latex, str) or isinstance(v_code, str):
            results.append({"point": pt, "latex_value": v_latex, "code_value": v_code, "match": False})
            all_match = False
        else:
            try:
                match = math.isclose(float(v_latex), float(v_code), rel_tol=1e-8)
            except Exception:
                match = str(v_latex) == str(v_code)
            results.append({"point": pt, "latex_value": float(v_latex), "code_value": float(v_code), "match": match})
            if not match: all_match = False

    return {
        "verified": all_match,
        "test_points": len(test_points),
        "passed": sum(1 for r in results if r.get('match')),
        "details": results[:5],
        "verdict": "转换正确：所有测试点数值一致" if all_match else "存在不一致，请检查转换",
    }


# ====================== 操作注册 ======================

TARGETS = {'python': _to_python, 'lua': _to_lua, 'c++': _to_cpp, 'cpp': _to_cpp}


def op_latex_to_code(latex_str, target='python'):
    """LaTeX → 代码"""
    if target not in TARGETS:
        return {"error": f"不支持目标语言: {target}，可用: {list(TARGETS.keys())}"}
    return TARGETS[target](latex_str)


def op_code_to_latex(code_str, source='python'):
    """代码 → LaTeX"""
    return _code_to_latex(code_str, source)


OPERATIONS = {
    'latex_to_code': op_latex_to_code,
    'code_to_latex': op_code_to_latex,
    'verify_translation': op_verify_translation,
}


def main():
    parser = argparse.ArgumentParser(
        description="数学公式↔代码 多语言互转",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python formula_translate.py --op "latex_to_code" --latex "\\\\frac{-b+\\\\sqrt{b^2-4ac}}{2a}" --target "python"
  python formula_translate.py --op "latex_to_code" --latex "\\\\sin(\\\\theta)" --target "lua"
  python formula_translate.py --op "code_to_latex" --code "(-b+sqrt(b**2-4*a*c))/(2*a)" --source "python"
  python formula_translate.py --op "verify_translation" --latex "\\\\sin(x)" --code "sin(x)" --target "python"
""")
    parser.add_argument('--op', '-o', help='操作名称')
    parser.add_argument('--latex', help='LaTeX 公式')
    parser.add_argument('--code', help='代码字符串')
    parser.add_argument('--target', default='python', help='目标语言: python/lua/c++')
    parser.add_argument('--source', default='python', help='源语言: python/lua/c++')
    parser.add_argument('--compact', '-c', action='store_true', help='紧凑输出')
    parser.add_argument('json_input', nargs='?', help='JSON 输入')

    args = parser.parse_args()
    input_data = {}
    if args.json_input: input_data = json.loads(args.json_input)
    elif not sys.stdin.isatty():
        raw = sys.stdin.read().strip()
        if raw: input_data = json.loads(raw)

    op = args.op or input_data.get('op', '')
    if not op or op not in OPERATIONS:
        print(json.dumps({"ok": False, "error": f"不支持: {op}, 可用: {list(OPERATIONS.keys())}"}, ensure_ascii=False))
        sys.exit(1)

    try:
        kwargs = {}
        if op == 'latex_to_code':
            kwargs['latex_str'] = args.latex or input_data.get('latex', '')
            kwargs['target'] = args.target or input_data.get('target', 'python')
        elif op == 'code_to_latex':
            kwargs['code_str'] = args.code or input_data.get('code', '')
            kwargs['source'] = args.source or input_data.get('source', 'python')
        elif op == 'verify_translation':
            kwargs['latex_str'] = args.latex or input_data.get('latex', '')
            kwargs['code_str'] = args.code or input_data.get('code', '')
            kwargs['target_lang'] = args.target or input_data.get('target', 'python')

        result = OPERATIONS[op](**kwargs)
        output = {"ok": True, "op": op, **result}
        print(json.dumps(output, ensure_ascii=False, indent=None if args.compact else 2, default=str))
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()