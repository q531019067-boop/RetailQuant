#!/usr/bin/env python3
"""
trig_tools.py — 三角函数专项工具

用法:
    python trig_tools.py --op "verify_identity" --lhs "sin(a+b)" --rhs "sin(a)*cos(b)+cos(a)*sin(b)"
    python trig_tools.py --op "euler" --expr "e^(i*pi)+1"
    python trig_tools.py --op "orthogonality" --n 5
    python trig_tools.py --op "product_to_sum" --expr "sin(a)*cos(b)"
    python trig_tools.py --op "sum_to_product" --expr "sin(a)+sin(b)"
    python trig_tools.py --op "solve_trig" --expr "2*sin(x)-1" --range "[0,2*pi]"

支持的操作:
    verify_identity, euler, orthogonality,
    product_to_sum, sum_to_product,
    half_angle, double_angle,
    solve_trig, trig_series, trig_table
"""

import sys, json, math, cmath, argparse

try:
    import sympy as sp

    HAS_SYMPY = True
except ImportError:
    HAS_SYMPY = False

try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


# ====================== 三角恒等式验证 ======================


def op_verify_identity(lhs_str, rhs_str, test_points=50):
    """验证三角恒等式：在多个点采样比较"""
    if not HAS_SYMPY:
        return _verify_numeric(lhs_str, rhs_str, test_points)

    # 符号方法：化简差值
    try:
        lhs = sp.sympify(lhs_str)
        rhs = sp.sympify(rhs_str)
        diff = sp.simplify(lhs - rhs)
        symbol_match = diff == 0
    except Exception:
        symbol_match = False
        diff = None

    # 数值方法：随机采样
    numeric_match, max_err, err_points = _verify_numeric_detail(lhs_str, rhs_str, test_points)

    return {
        "symbolic_match": symbol_match,
        "numeric_match": numeric_match,
        "max_error": float(max_err) if max_err is not None else None,
        "test_points": test_points,
        "verdict": "恒等式成立" if (symbol_match or numeric_match) else "不成立",
        "note": _identity_note(lhs_str, rhs_str),
    }


def _verify_numeric(lhs_str, rhs_str, n):
    match, max_err, _ = _verify_numeric_detail(lhs_str, rhs_str, n)
    return {"numeric_match": match, "max_error": float(max_err) if max_err else None, "test_points": n}


def _verify_numeric_detail(lhs_str, rhs_str, n):
    """数值验证细节"""
    import random, math as _m

    random.seed(42)
    max_err = 0.0
    err_points = []
    all_ok = True
    # 安全求值环境
    safe = {
        "sin": _m.sin,
        "cos": _m.cos,
        "tan": _m.tan,
        "asin": _m.asin,
        "acos": _m.acos,
        "atan": _m.atan,
        "atan2": _m.atan2,
        "sinh": _m.sinh,
        "cosh": _m.cosh,
        "tanh": _m.tanh,
        "exp": _m.exp,
        "log": _m.log,
        "sqrt": _m.sqrt,
        "pi": _m.pi,
        "e": _m.e,
        "abs": abs,
    }
    for _ in range(n):
        vars_dict = {}
        for var in ["a", "b", "c", "x", "y", "z", "t", "u"]:
            if var in lhs_str or var in rhs_str:
                if var in ("t", "u"):
                    vars_dict[var] = random.uniform(0.1, 5.0)
                else:
                    vars_dict[var] = random.uniform(-3.14, 3.14)
        try:
            v_lhs = eval(lhs_str, {"__builtins__": {}}, {**safe, **vars_dict})
            v_rhs = eval(rhs_str, {"__builtins__": {}}, {**safe, **vars_dict})
        except Exception:
            all_ok = False
            break
        if isinstance(v_lhs, complex) or isinstance(v_rhs, complex):
            err = abs(v_lhs - v_rhs)
        else:
            err = abs(float(v_lhs) - float(v_rhs))
        if err > max_err:
            max_err = err
        if err > 1e-8:
            all_ok = False
            if len(err_points) < 5:
                err_points.append({"vars": vars_dict, "lhs": float(v_lhs), "rhs": float(v_rhs), "error": float(err)})
    return all_ok, max_err, err_points


def _identity_note(lhs, rhs):
    """识别常见恒等式并给出注释"""
    notes = {
        "sin(a+b)": "和角公式：sin(a+b) = sin a cos b + cos a sin b",
        "cos(a+b)": "和角公式：cos(a+b) = cos a cos b - sin a sin b",
        "sin(a-b)": "差角公式",
        "cos(a-b)": "差角公式",
        "sin(2*a)": "倍角公式：sin(2a) = 2 sin a cos a",
        "cos(2*a)": "倍角公式：cos(2a) = cos²a - sin²a = 2cos²a-1 = 1-2sin²a",
        "sin(a/2)": "半角公式",
        "cos(a/2)": "半角公式",
    }
    for k, v in notes.items():
        if k in lhs or k in rhs:
            return v
    return ""


# ====================== 欧拉公式 ======================


def op_euler(expr_str=None, n_terms=10):
    """欧拉公式 e^(ix) = cos(x) + i*sin(x) 的验证与展开"""
    results = {}

    # 基本恒等式验证
    test_angles = [0, math.pi / 6, math.pi / 4, math.pi / 3, math.pi / 2, math.pi, 3 * math.pi / 2, 2 * math.pi]
    verifications = []
    for theta in test_angles:
        euler_lhs = cmath.exp(1j * theta)
        euler_rhs = complex(math.cos(theta), math.sin(theta))
        err = abs(euler_lhs - euler_rhs)
        verifications.append(
            {
                "theta": theta,
                "theta_pi": f"{theta / math.pi:.4g}pi",
                "e^(i*theta)": f"{euler_lhs.real:.6g}+{euler_lhs.imag:.6g}i",
                "cos+i*sin": f"{euler_rhs.real:.6g}+{euler_rhs.imag:.6g}i",
                "error": float(err),
            }
        )
    results["verification"] = verifications

    # 著名的 e^(i*pi) + 1 = 0
    famous = cmath.exp(1j * math.pi) + 1
    results["euler_identity"] = {
        "formula": "e^(i*pi) + 1 = 0",
        "value": complex(famous),
        "holds": abs(famous) < 1e-12,
    }

    # 泰勒展开验证
    if HAS_SYMPY:
        try:
            x = sp.Symbol("x")
            exp_series = sp.series(sp.exp(sp.I * x), x, 0, n_terms + 1).removeO()
            cos_series = sp.series(sp.cos(x), x, 0, n_terms + 1).removeO()
            sin_series = sp.series(sp.sin(x), x, 0, n_terms + 1).removeO()
            results["taylor_verification"] = {
                "e^(ix)_series": str(exp_series),
                "cos(x)_series": str(cos_series),
                "sin(x)_series": str(sin_series),
                "match": sp.simplify(exp_series - (cos_series + sp.I * sin_series)) == 0,
            }
        except Exception:
            pass

    # 几何解释
    results["geometric"] = (
        "欧拉公式 e^(iθ) = cos(θ) + i·sin(θ) 表明：复平面上，e^(iθ) 对应单位圆上角度为 θ 的点。当 θ=π 时，该点位于 (-1, 0)，因此 e^(iπ)+1=0 将五个最重要的数学常数 (e, i, π, 1, 0) 联系在一条等式中。"
    )

    # 如果指定了表达式，求值
    if expr_str:
        try:
            safe = {"e": math.e, "pi": math.pi, "i": 1j, "sin": math.sin, "cos": math.cos, "exp": cmath.exp}
            val = eval(expr_str, {"__builtins__": {}}, safe)
            results["evaluation"] = {"expr": expr_str, "value": str(val)}
        except Exception as e:
            results["evaluation"] = {"expr": expr_str, "error": str(e)}

    return results


# ====================== 三角函数系正交性 ======================


def op_orthogonality(n_max=5):
    """验证三角函数系 {1, cos(nx), sin(nx)} 在 [-pi, pi] 上的正交性"""
    if not HAS_NUMPY:
        return {"error": "需要 numpy"}
    results = []
    x = np.linspace(-np.pi, np.pi, 1000)
    dx = 2 * np.pi / 999

    # 1 与 cos(nx) 正交
    for n in range(1, n_max + 1):
        inner = np.sum(np.cos(n * x)) * dx
        results.append({"pair": f"<1, cos({n}x)>", "inner_product": float(inner), "orthogonal": abs(inner) < 0.01})

    # 1 与 sin(nx) 正交
    for n in range(1, n_max + 1):
        inner = np.sum(np.sin(n * x)) * dx
        results.append({"pair": f"<1, sin({n}x)>", "inner_product": float(inner), "orthogonal": abs(inner) < 0.01})

    # cos(mx) 与 cos(nx)
    for m in range(1, n_max + 1):
        for n_idx in range(1, n_max + 1):
            inner = np.sum(np.cos(m * x) * np.cos(n_idx * x)) * dx
            expected = np.pi if m == n_idx else 0
            results.append(
                {
                    "pair": f"<cos({m}x), cos({n_idx}x)>",
                    "inner_product": float(inner),
                    "expected": float(expected),
                    "orthogonal": m != n_idx and abs(inner) < 0.01 or m == n_idx and abs(inner - np.pi) < 0.1,
                }
            )

    # sin(mx) 与 sin(nx)
    for m in range(1, n_max + 1):
        for n_idx in range(1, n_max + 1):
            inner = np.sum(np.sin(m * x) * np.sin(n_idx * x)) * dx
            expected = np.pi if m == n_idx else 0
            results.append(
                {
                    "pair": f"<sin({m}x), sin({n_idx}x)>",
                    "inner_product": float(inner),
                    "expected": float(expected),
                    "orthogonal": m != n_idx and abs(inner) < 0.01 or m == n_idx and abs(inner - np.pi) < 0.1,
                }
            )

    return {
        "n_max": n_max,
        "domain": "[-pi, pi]",
        "basis": [f"cos({n}x), sin({n}x)" for n in range(1, n_max + 1)],
        "tests": results,
        "summary": f"在 [-pi, pi] 上，三角函数系 {{1, cos x, sin x, cos 2x, sin 2x, ...}} 构成正交基。任意周期为 2pi 的平方可积函数可展开为傅里叶级数。",
    }


# ====================== 积化和差 / 和差化积 ======================

KNOWN_IDENTITIES = {
    "sin(a)*cos(b)": {"result": "(sin(a+b)+sin(a-b))/2", "name": "积化和差"},
    "cos(a)*sin(b)": {"result": "(sin(a+b)-sin(a-b))/2", "name": "积化和差"},
    "cos(a)*cos(b)": {"result": "(cos(a+b)+cos(a-b))/2", "name": "积化和差"},
    "sin(a)*sin(b)": {"result": "(cos(a-b)-cos(a+b))/2", "name": "积化和差"},
    "sin(a)+sin(b)": {"result": "2*sin((a+b)/2)*cos((a-b)/2)", "name": "和差化积"},
    "sin(a)-sin(b)": {"result": "2*cos((a+b)/2)*sin((a-b)/2)", "name": "和差化积"},
    "cos(a)+cos(b)": {"result": "2*cos((a+b)/2)*cos((a-b)/2)", "name": "和差化积"},
    "cos(a)-cos(b)": {"result": "-2*sin((a+b)/2)*sin((a-b)/2)", "name": "和差化积"},
}


def op_product_to_sum(expr_str):
    """积化和差"""
    if not HAS_SYMPY:
        return _manual_identity(expr_str, "product_to_sum")
    try:
        expr = sp.sympify(expr_str)
        expanded = sp.expand_trig(expr)
        result = sp.simplify(expanded)
        return {
            "input": expr_str,
            "output": str(result),
            "verification": _verify_identity_numeric(expr_str, str(result)),
        }
    except Exception as e:
        return {"error": str(e), "input": expr_str}


def op_sum_to_product(expr_str):
    """和差化积"""
    if not HAS_SYMPY:
        return _manual_identity(expr_str, "sum_to_product")
    try:
        expr = sp.sympify(expr_str)
        factored = sp.fu(expr)  # sympy 的三角化简函数
        return {
            "input": expr_str,
            "output": str(factored),
            "verification": _verify_identity_numeric(expr_str, str(factored)),
        }
    except Exception as e:
        return {"error": str(e), "input": expr_str}


def _manual_identity(expr_str, direction):
    """手动查找已知恒等式"""
    if direction == "product_to_sum":
        for pattern, info in KNOWN_IDENTITIES.items():
            if pattern.replace(" ", "") == expr_str.replace(" ", ""):
                return {"input": expr_str, "output": info["result"], "name": info["name"]}
        return {"input": expr_str, "note": "未找到匹配的积化和差公式，尝试用 sympy"}
    elif direction == "sum_to_product":
        for pattern, info in KNOWN_IDENTITIES.items():
            if pattern.replace(" ", "") == expr_str.replace(" ", ""):
                return {"input": expr_str, "output": info["result"], "name": info["name"]}
        return {"input": expr_str, "note": "未找到匹配的和差化积公式，尝试用 sympy"}


def _verify_identity_numeric(lhs_str, rhs_str, n=30):
    """数值验证恒等式"""
    import random

    random.seed(42)
    max_err = 0
    for _ in range(n):
        vars_dict = {"a": random.uniform(-3, 3), "b": random.uniform(-3, 3)}
        safe = {"sin": math.sin, "cos": math.cos, "tan": math.tan, "pi": math.pi}
        try:
            v1 = eval(lhs_str, {"__builtins__": {}}, {**safe, **vars_dict})
            v2 = eval(rhs_str, {"__builtins__": {}}, {**safe, **vars_dict})
            err = abs(float(v1) - float(v2))
            if err > max_err:
                max_err = err
        except Exception:
            return False
    return max_err < 1e-8


# ====================== 半角/倍角公式 ======================


def op_half_angle(expr_str):
    """半角公式"""
    identities = {
        "sin(a/2)": "±sqrt((1-cos(a))/2)",
        "cos(a/2)": "±sqrt((1+cos(a))/2)",
        "tan(a/2)": "±sqrt((1-cos(a))/(1+cos(a))) = sin(a)/(1+cos(a)) = (1-cos(a))/sin(a)",
    }
    result = identities.get(expr_str.replace(" ", ""))
    if result:
        return {"input": expr_str, "half_angle_formula": result}
    if HAS_SYMPY:
        try:
            expr = sp.sympify(expr_str)
            simplified = sp.simplify(expr)
            return {"input": expr_str, "simplified": str(simplified)}
        except Exception as e:
            return {"error": str(e)}
    return {"input": expr_str, "note": "未知半角表达式"}


def op_double_angle(expr_str):
    """倍角公式"""
    identities = {
        "sin(2*a)": "2*sin(a)*cos(a)",
        "cos(2*a)": "cos(a)**2 - sin(a)**2 = 2*cos(a)**2 - 1 = 1 - 2*sin(a)**2",
        "tan(2*a)": "2*tan(a)/(1-tan(a)**2)",
    }
    result = identities.get(expr_str.replace(" ", ""))
    if result:
        return {"input": expr_str, "double_angle_formula": result}
    if HAS_SYMPY:
        try:
            expr = sp.sympify(expr_str)
            expanded = sp.expand_trig(expr)
            return {"input": expr_str, "expanded": str(expanded)}
        except Exception as e:
            return {"error": str(e)}
    return {"input": expr_str, "note": "未知倍角表达式"}


# ====================== 三角方程求解 ======================


def op_solve_trig(expr_str, var="x", range_=None):
    """求解三角方程"""
    if not HAS_SYMPY:
        return {"error": "需要 sympy"}
    x = sp.Symbol(var)
    try:
        expr = sp.sympify(expr_str)
        solutions = sp.solveset(expr, x, domain=sp.S.Reals)
        result = {"solutions": str(solutions), "expr": expr_str}
        if range_:
            a, b = range_[0], range_[1]
            # 筛选在指定范围的解
            if hasattr(solutions, "intersect"):
                interval = sp.Interval(a, b)
                filtered = solutions.intersect(interval)
                result["filtered"] = str(filtered)
                # 数值化
                try:
                    numeric = [float(s.evalf()) for s in filtered if s.is_number]
                    result["numeric"] = numeric
                except Exception:
                    pass
        return result
    except Exception as e:
        return {"error": str(e), "expr": expr_str}


# ====================== 三角级数 ======================


def op_trig_series(expr_str, var="x", point=0, order=5):
    """三角函数的泰勒/麦克劳林级数"""
    if not HAS_SYMPY:
        return {"error": "需要 sympy"}
    x = sp.Symbol(var)
    try:
        f = sp.sympify(expr_str)
        series = sp.series(f, x, point, order + 1)
        return {
            "expr": expr_str,
            "series": str(series),
            "latex": sp.latex(series),
            "point": point,
            "order": order,
        }
    except Exception as e:
        return {"error": str(e)}


# ====================== 三角值表 ======================


def op_trig_table(angles_deg=None):
    """生成特殊角的三角函数值表"""
    if angles_deg is None:
        angles_deg = [0, 30, 45, 60, 90, 120, 135, 150, 180, 210, 225, 240, 270, 300, 315, 330, 360]
    table = []
    for deg in angles_deg:
        rad = math.radians(deg)
        table.append(
            {
                "angle_deg": deg,
                "angle_rad": f"{rad / math.pi:.4g}pi",
                "sin": round(math.sin(rad), 6),
                "cos": round(math.cos(rad), 6),
                "tan": round(math.tan(rad), 6) if abs(math.cos(rad)) > 1e-10 else "inf",
            }
        )
    return {"table": table, "count": len(table)}


def op_heron_area(a, b, c):
    """海伦公式：已知三边求三角形面积 S = sqrt(s(s-a)(s-b)(s-c)), s=(a+b+c)/2"""
    s = (a + b + c) / 2
    area = math.sqrt(max(0, s * (s - a) * (s - b) * (s - c)))
    valid = (a + b > c) and (a + c > b) and (b + c > a)
    return {
        "area": area,
        "semiperimeter": s,
        "sides": [a, b, c],
        "valid_triangle": valid,
        "note": "海伦公式(约公元60年)，仅用三边即可求面积" if valid else "三边无法构成三角形",
    }


def op_law_of_sines(a=None, A=None, b=None, B=None, c=None, C=None):
    """正弦定理：a/sinA = b/sinB = c/sinC = 2R。已知一对边角+任意第三量可解三角形。"""
    result = {}
    # 计算外接圆直径
    for side, angle in [(a, A), (b, B), (c, C)]:
        if side is not None and angle is not None:
            result["diameter_2R"] = side / math.sin(math.radians(angle))
            break
    # 已知两角求第三角
    given_angles = [x for x in [A, B, C] if x is not None]
    if len(given_angles) == 2:
        missing = 180 - sum(given_angles)
        if A is None:
            result["angle_A"] = missing
        if B is None:
            result["angle_B"] = missing
        if C is None:
            result["angle_C"] = missing
    if result.get("diameter_2R"):
        d = result["diameter_2R"]
        if a is None and A is not None:
            result["side_a"] = d * math.sin(math.radians(A))
        if b is None and B is not None:
            result["side_b"] = d * math.sin(math.radians(B))
        if c is None and C is not None:
            result["side_c"] = d * math.sin(math.radians(C))
    return result


def op_law_of_cosines(a=None, b=None, c=None, A=None, B=None, C=None):
    """余弦定理：c^2 = a^2 + b^2 - 2ab*cos(C)。SSS或SAS解三角形。"""
    result = {}
    # SSS: 已知三边求角
    if a and b and c:
        result["angle_A"] = math.degrees(math.acos((b * b + c * c - a * a) / (2 * b * c)))
        result["angle_B"] = math.degrees(math.acos((a * a + c * c - b * b) / (2 * a * c)))
        result["angle_C"] = math.degrees(math.acos((a * a + b * b - c * c) / (2 * a * b)))
    # SAS: 已知两边夹角求第三边
    elif a and b and C:
        result["side_c"] = math.sqrt(a * a + b * b - 2 * a * b * math.cos(math.radians(C)))
    elif a and c and B:
        result["side_b"] = math.sqrt(a * a + c * c - 2 * a * c * math.cos(math.radians(B)))
    elif b and c and A:
        result["side_a"] = math.sqrt(b * b + c * c - 2 * b * c * math.cos(math.radians(A)))
    return result


OPERATIONS = {
    "verify_identity": op_verify_identity,
    "euler": op_euler,
    "orthogonality": op_orthogonality,
    "product_to_sum": op_product_to_sum,
    "sum_to_product": op_sum_to_product,
    "half_angle": op_half_angle,
    "double_angle": op_double_angle,
    "solve_trig": op_solve_trig,
    "trig_series": op_trig_series,
    "trig_table": op_trig_table,
    "heron_area": op_heron_area,
    "law_of_sines": op_law_of_sines,
    "law_of_cosines": op_law_of_cosines,
}


def main():
    parser = argparse.ArgumentParser(
        description="三角函数专项工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python trig_tools.py --op "verify_identity" --lhs "sin(a+b)" --rhs "sin(a)*cos(b)+cos(a)*sin(b)"
  python trig_tools.py --op "euler"
  python trig_tools.py --op "orthogonality" --n 5
  python trig_tools.py --op "product_to_sum" --expr "sin(a)*cos(b)"
  python trig_tools.py --op "sum_to_product" --expr "sin(a)+sin(b)"
  python trig_tools.py --op "trig_table"
        """,
    )
    parser.add_argument("json_input", nargs="?", help="JSON 输入")
    parser.add_argument("--op", "-o", help="操作名称")
    parser.add_argument("--expr", "-e", help="表达式")
    parser.add_argument("--lhs", help="恒等式左边")
    parser.add_argument("--rhs", help="恒等式右边")
    parser.add_argument("--var", default="x", help="变量名")
    parser.add_argument("--range", help="范围 [min,max]")
    parser.add_argument("--n", type=int, default=5, help="项数")
    parser.add_argument("--point", type=float, default=0, help="展开点")
    parser.add_argument("--order", type=int, default=5, help="展开阶数")
    parser.add_argument("--compact", "-c", action="store_true", help="紧凑输出")

    args = parser.parse_args()
    input_data = {}
    if args.json_input:
        input_data = json.loads(args.json_input)
    elif not sys.stdin.isatty():
        raw = sys.stdin.read().strip()
        if raw:
            input_data = json.loads(raw)

    op = args.op or input_data.get("op", "")
    if not op or op not in OPERATIONS:
        names = ", ".join(OPERATIONS.keys())
        print(json.dumps({"ok": False, "error": f"不支持: {op}，可用: {names}"}, ensure_ascii=False))
        sys.exit(1)

    try:
        kwargs = {}
        if op == "verify_identity":
            kwargs["lhs_str"] = args.lhs or input_data.get("lhs", "")
            kwargs["rhs_str"] = args.rhs or input_data.get("rhs", "")
        elif op == "euler":
            kwargs["expr_str"] = args.expr or input_data.get("expr")
            kwargs["n_terms"] = args.n or input_data.get("n", 10)
        elif op == "orthogonality":
            kwargs["n_max"] = args.n or input_data.get("n", 5)
        elif op in ("product_to_sum", "sum_to_product", "half_angle", "double_angle"):
            kwargs["expr_str"] = args.expr or input_data.get("expr", "")
        elif op == "solve_trig":
            kwargs["expr_str"] = args.expr or input_data.get("expr", "")
            kwargs["var"] = args.var or input_data.get("var", "x")
            rng = args.range or input_data.get("range")
            kwargs["range_"] = json.loads(rng) if isinstance(rng, str) else rng
        elif op == "trig_series":
            kwargs["expr_str"] = args.expr or input_data.get("expr", "")
            kwargs["var"] = args.var or input_data.get("var", "x")
            kwargs["point"] = args.point or input_data.get("point", 0)
            kwargs["order"] = args.order or input_data.get("order", 5)
        elif op == "trig_table":
            kwargs["angles_deg"] = input_data.get("angles_deg")

        result = OPERATIONS[op](**kwargs)
        output = {"ok": True, "op": op, **result}
        out_str = json.dumps(output, ensure_ascii=False, indent=None if args.compact else 2, default=str)
        print(out_str)
    except Exception as e:
        output = {"ok": False, "error": str(e), "op": op}
        print(json.dumps(output, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
