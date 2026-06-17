#!/usr/bin/env python3
"""
eval_expr.py — 安全表达式求值器

用法:
    echo '{"expr": "x**2 + 2*x + 1", "vars": {"x": 3}}' | python eval_expr.py
    python eval_expr.py '{"expr": "sin(pi/6) + sqrt(9)"}'
    python eval_expr.py --expr "attack * (1 + crit)" --vars '{"attack":1000,"crit":0.5}'
    python eval_expr.py --table --expr "x+y" --vars '[{"x":1,"y":2},{"x":3,"y":4}]'
    python eval_expr.py --precision 50 --expr "1/3"

输出 JSON:
    {"ok": true, "result": 16.0, "expr": "x**2 + 2*x + 1"}
    {"ok": false, "error": "undefined: z"}

设计:
    - ast 白名单安全解析，拒绝一切危险操作
    - 支持 math 模块函数和常量
    - 支持 --table 模式批量求值
    - 支持 --precision 高精度 decimal 模式
"""
import sys, json, ast, math, operator, argparse
from decimal import Decimal, getcontext


# ====================== SafeEval Core ======================

ALLOWED_FUNCTIONS = {
    'sin': math.sin, 'cos': math.cos, 'tan': math.tan,
    'asin': math.asin, 'acos': math.acos, 'atan': math.atan, 'atan2': math.atan2,
    'sinh': math.sinh, 'cosh': math.cosh, 'tanh': math.tanh,
    'sqrt': math.sqrt, 'log': math.log, 'log10': math.log10, 'log2': math.log2,
    'exp': math.exp, 'pow': pow,
    'fabs': math.fabs, 'abs': abs, 'floor': math.floor, 'ceil': math.ceil,
    'trunc': math.trunc, 'fmod': math.fmod,
    'degrees': math.degrees, 'radians': math.radians,
    'hypot': math.hypot, 'erf': math.erf, 'erfc': math.erfc,
    'gamma': math.gamma, 'lgamma': math.lgamma,
    'max': max, 'min': min, 'round': round,
    'int': int, 'float': float, 'bool': bool,
    'sum': sum, 'len': len,
}

ALLOWED_CONSTANTS = {
    'pi': math.pi, 'e': math.e, 'tau': math.tau,
    'inf': math.inf, 'nan': math.nan,
    'True': True, 'False': False, 'None': None,
}


class SafeEval:
    """安全的表达式求值器，使用 ast 白名单"""

    ALLOWED_NODES = {
        ast.Expression, ast.Constant, ast.Name, ast.Load,
        ast.BinOp, ast.UnaryOp, ast.USub, ast.UAdd, ast.Not,
        ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
        ast.Compare, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
        ast.BoolOp, ast.And, ast.Or,
        ast.IfExp, ast.Call, ast.keyword,
        ast.Attribute, ast.Subscript, ast.Slice,
        ast.List, ast.Tuple,
    }

    def __init__(self, vars_dict=None):
        self.vars = dict(vars_dict or {})

    def _check_node(self, node):
        if type(node) not in self.ALLOWED_NODES:
            raise ValueError(f"不允许的语法节点: {type(node).__name__}")
        for child in ast.iter_child_nodes(node):
            self._check_node(child)

    def _eval_node(self, node):
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Name):
            if node.id in self.vars:
                return self.vars[node.id]
            if node.id in ALLOWED_CONSTANTS:
                return ALLOWED_CONSTANTS[node.id]
            raise NameError(f"未定义变量: {node.id}")
        elif isinstance(node, ast.BinOp):
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            ops = {
                ast.Add: operator.add, ast.Sub: operator.sub,
                ast.Mult: operator.mul, ast.Div: operator.truediv,
                ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
                ast.Pow: operator.pow,
            }
            return ops[type(node.op)](left, right)
        elif isinstance(node, ast.UnaryOp):
            v = self._eval_node(node.operand)
            ops = {ast.USub: operator.neg, ast.UAdd: operator.pos, ast.Not: operator.not_}
            return ops[type(node.op)](v)
        elif isinstance(node, ast.Compare):
            left = self._eval_node(node.left)
            for op, comp in zip(node.ops, node.comparators):
                right = self._eval_node(comp)
                cmps = {
                    ast.Eq: operator.eq, ast.NotEq: operator.ne,
                    ast.Lt: operator.lt, ast.LtE: operator.le,
                    ast.Gt: operator.gt, ast.GtE: operator.ge,
                }
                if not cmps[type(op)](left, right):
                    return False
                left = right
            return True
        elif isinstance(node, ast.BoolOp):
            vals = [self._eval_node(v) for v in node.values]
            return all(vals) if isinstance(node.op, ast.And) else any(vals)
        elif isinstance(node, ast.IfExp):
            return self._eval_node(node.body) if self._eval_node(node.test) else self._eval_node(node.orelse)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in ALLOWED_FUNCTIONS:
                args = [self._eval_node(a) for a in node.args]
                kwargs = {kw.arg: self._eval_node(kw.value) for kw in node.keywords}
                return ALLOWED_FUNCTIONS[node.func.id](*args, **kwargs)
            if isinstance(node.func, ast.Attribute):
                obj = self._eval_node(node.func.value)
                if node.func.attr in ('real', 'imag', 'conjugate'):
                    return getattr(obj, node.func.attr)
            raise ValueError(f"不允许的函数调用: {ast.dump(node.func)}")
        elif isinstance(node, ast.Attribute):
            obj = self._eval_node(node.value)
            if node.attr in ('real', 'imag'):
                return getattr(obj, node.attr)
            raise ValueError(f"不允许的属性访问: {node.attr}")
        elif isinstance(node, ast.Subscript):
            obj = self._eval_node(node.value)
            if isinstance(node.slice, ast.Constant):
                idx = node.slice.value
            elif isinstance(node.slice, ast.Slice):
                lower = self._eval_node(node.slice.lower) if node.slice.lower else None
                upper = self._eval_node(node.slice.upper) if node.slice.upper else None
                step = self._eval_node(node.slice.step) if node.slice.step else None
                return obj[lower:upper:step]
            else:
                idx = self._eval_node(node.slice)
            return obj[idx]
        elif isinstance(node, ast.List):
            vals = [self._eval_node(e) for e in node.elts]
            # 检查是否可以转为 numpy 数组
            return vals
        elif isinstance(node, ast.Tuple):
            return tuple(self._eval_node(e) for e in node.elts)
        raise ValueError(f"不支持的节点类型: {type(node).__name__}")

    def eval(self, expr_str):
        tree = ast.parse(expr_str.strip(), mode='eval')
        self._check_node(tree)
        return self._eval_node(tree.body)


# ====================== Decimal 高精度模式 ======================

def eval_decimal(expr_str, vars_dict, precision=50):
    """使用 decimal 高精度求值"""
    getcontext().prec = precision
    # 将变量转为 Decimal
    dec_vars = {}
    for k, v in (vars_dict or {}).items():
        dec_vars[k] = Decimal(str(v))
    dec_vars.update({
        'pi': Decimal(str(math.pi)),
        'e': Decimal(str(math.e)),
    })

    # 限制可用的操作
    import re
    safe_expr = re.sub(r'[^0-9a-zA-Z_\+\-\*\/\(\)\.\,\s]', '', expr_str)
    for k in dec_vars:
        safe_expr = safe_expr.replace(k, f'dec_vars["{k}"]')

    try:
        result = eval(safe_expr, {"__builtins__": {}, "dec_vars": dec_vars, "Decimal": Decimal})
        return float(result)
    except Exception as e:
        raise ValueError(f"Decimal 求值失败: {e}")


# ====================== 序列化辅助 ======================

def to_json_safe(obj):
    """将结果转为 JSON 可序列化"""
    if isinstance(obj, (int, float, bool, str, type(None))):
        return obj
    if isinstance(obj, complex):
        return {"real": obj.real, "imag": obj.imag}
    if isinstance(obj, (list, tuple)):
        return [to_json_safe(x) for x in obj]
    if isinstance(obj, dict):
        return {k: to_json_safe(v) for k, v in obj.items()}
    # numpy
    try:
        import numpy as np
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (np.floating, np.integer)):
            return float(obj)
    except ImportError:
        pass
    return str(obj)


# ====================== 主入口 ======================

def main():
    parser = argparse.ArgumentParser(
        description="安全表达式求值器 — 基于 ast 白名单",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  echo '{"expr":"sin(pi/6) + sqrt(9)"}' | python eval_expr.py
  python eval_expr.py --expr "x**2 + 2*x + 1" --vars '{"x":3}'
  python eval_expr.py --table --expr "x+y" --vars '[{"x":1,"y":2},{"x":3,"y":4}]'
  python eval_expr.py --precision 50 --expr "1/3"
        """
    )
    parser.add_argument('json_input', nargs='?', help='JSON 输入字符串')
    parser.add_argument('--expr', '-e', help='表达式字符串')
    parser.add_argument('--vars', '-v', help='变量 JSON (dict 或 list)')
    parser.add_argument('--table', '-t', action='store_true', help='表格模式: vars 为 list，逐行求值')
    parser.add_argument('--precision', '-p', type=int, default=0, help='Decimal 高精度位数')
    parser.add_argument('--compact', '-c', action='store_true', help='紧凑输出（减少空格）')

    args = parser.parse_args()

    # 解析输入
    input_data = {}
    if args.json_input:
        try:
            input_data = json.loads(args.json_input)
        except json.JSONDecodeError:
            print(json.dumps({"ok": False, "error": "JSON 解析失败"}, ensure_ascii=False))
            sys.exit(1)

    # stdin 输入
    elif not sys.stdin.isatty():
        raw = sys.stdin.read().strip()
        if raw:
            try:
                input_data = json.loads(raw)
            except json.JSONDecodeError:
                print(json.dumps({"ok": False, "error": "stdin JSON 解析失败"}, ensure_ascii=False))
                sys.exit(1)

    # 命令行参数覆盖
    expr = args.expr or input_data.get('expr', '')
    vars_data = None

    if args.vars:
        vars_data = json.loads(args.vars)
    elif 'vars' in input_data:
        vars_data = input_data['vars']

    if not expr:
        print(json.dumps({"ok": False, "error": "缺少表达式 (--expr 或 JSON 中的 'expr')"}, ensure_ascii=False))
        sys.exit(1)

    # Table 模式
    if args.table or isinstance(vars_data, list):
        if not isinstance(vars_data, list):
            print(json.dumps({"ok": False, "error": "table 模式需要 vars 为 list"}, ensure_ascii=False))
            sys.exit(1)
        results = []
        for row in vars_data:
            try:
                if args.precision > 0:
                    val = eval_decimal(expr, row, args.precision)
                else:
                    val = SafeEval(row).eval(expr)
                results.append({"ok": True, "result": to_json_safe(val)})
            except Exception as e:
                results.append({"ok": False, "error": str(e)})
        print(json.dumps({"ok": True, "results": results, "count": len(results), "expr": expr},
                         ensure_ascii=False, indent=None if args.compact else 2))
        return

    # 单次求值
    try:
        if args.precision > 0:
            result = eval_decimal(expr, vars_data or {}, args.precision)
        else:
            result = SafeEval(vars_data or {}).eval(expr)
        output = {"ok": True, "result": to_json_safe(result), "expr": expr}
        print(json.dumps(output, ensure_ascii=False, indent=None if args.compact else 2))
    except Exception as e:
        output = {"ok": False, "error": str(e), "expr": expr}
        print(json.dumps(output, ensure_ascii=False, indent=None if args.compact else 2), file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
