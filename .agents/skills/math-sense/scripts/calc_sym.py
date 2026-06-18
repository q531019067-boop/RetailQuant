#!/usr/bin/env python3
"""
calc_sym.py — 符号/数值微积分工具（含多变量）

用法:
    echo '{"expr":"x**2+3*x+2","op":"diff","var":"x"}' | python calc_sym.py
    python calc_sym.py --expr "x**3-2*x-5" --op "root" --var "x" --guess 2
    python calc_sym.py --expr "x**2+y**2" --op "gradient" --vars '["x","y"]' --point-list "[1,2]"
    python calc_sym.py --expr "x**3+y**3" --op "hessian" --vars '["x","y"]'

支持的操作:
    diff, integrate, limit, root, solve, simplify, expand, taylor, eval,
    partial_diff, gradient, hessian, jacobian, divergence
"""

import sys, json, argparse

try:
    import sympy as sp

    HAS_SYMPY = True
except ImportError:
    HAS_SYMPY = False

try:
    import scipy.optimize as opt
    import scipy.integrate as integrate_sp

    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


def sympy_diff(expr_str, var_str, order=1, point=None):
    x = sp.Symbol(var_str)
    expr = sp.sympify(expr_str)
    deriv = sp.diff(expr, x, order)
    result = {"symbolic": str(deriv), "latex": sp.latex(deriv)}
    if point is not None:
        val = float(deriv.subs(x, point))
        result["at_point"] = point
        result["numeric"] = val
        try:
            f = sp.lambdify(x, expr, "numpy")
            h = 1e-8
            result["numeric_verify"] = float((f(point + h) - f(point - h)) / (2 * h))
        except Exception:
            pass
    return result


def sympy_integrate(expr_str, var_str, a=None, b=None):
    x = sp.Symbol(var_str)
    expr = sp.sympify(expr_str)
    if a is not None and b is not None:
        indefinite = sp.integrate(expr, x)
        result = {
            "definite": float(sp.integrate(expr, (x, a, b)).evalf()),
            "indefinite": str(indefinite),
            "latex_indefinite": sp.latex(indefinite),
            "a": a,
            "b": b,
        }
        if HAS_SCIPY:
            try:
                f = sp.lambdify(x, expr, "numpy")
                num_val, _ = integrate_sp.quad(f, a, b)
                result["numeric_verify"] = float(num_val)
            except Exception:
                pass
        return result
    indefinite = sp.integrate(expr, x)
    return {"indefinite": str(indefinite), "latex": sp.latex(indefinite)}


def sympy_limit(expr_str, var_str, point, direction="+"):
    x = sp.Symbol(var_str)
    expr = sp.sympify(expr_str)
    lim = sp.limit(expr, x, point, dir="-" if direction == "-" else "+")
    return {"limit": str(lim), "numeric": float(lim.evalf()) if lim.is_number else None}


def sympy_root(expr_str, var_str, guess=None, interval=None):
    x = sp.Symbol(var_str)
    expr = sp.sympify(expr_str)
    result = {"symbolic_roots": []}
    try:
        result["symbolic_roots"] = [str(r) for r in sp.solve(expr, x)]
    except Exception:
        pass
    if HAS_SCIPY:
        f = sp.lambdify(x, expr, "numpy")
        if guess is not None:
            try:
                root = opt.newton(f, guess)
                result["newton_root"] = float(root)
                result["f_at_root"] = float(f(root))
            except Exception as e:
                result["newton_error"] = str(e)
        elif interval and len(interval) == 2:
            try:
                root = opt.brentq(f, interval[0], interval[1])
                result["brent_root"] = float(root)
                result["f_at_root"] = float(f(root))
            except Exception as e:
                result["brent_error"] = str(e)
    return result


def sympy_solve(equations, variables):
    """符号解方程组。equations为表达式字符串列表，variables为变量名列表。"""
    syms = [sp.Symbol(v) for v in variables]
    eqs = [sp.sympify(eq) for eq in equations]
    try:
        sol = sp.solve(eqs, syms, dict=True)
        result = {
            "solutions": [{str(k): str(v) for k, v in s.items()} for s in sol],
            "variables": variables,
            "count": len(sol),
        }
    except Exception as e:
        result = {"error": str(e), "variables": variables}
    return result


def sympy_linsolve(A_list, b_list=None):
    """解线性方程组 Ax=b。A_list为系数矩阵(列表的列表)，b_list为常数向量。"""
    A = sp.Matrix(A_list)
    if b_list is not None:
        b = sp.Matrix(b_list)
        try:
            sol = A.LUsolve(b)
            return {"solution": [str(v) for v in sol], "method": "LU分解"}
        except Exception:
            return {"solution": [str(v) for v in A.gauss_jordan_solve(b)[0]], "method": "Gauss-Jordan"}
    # 齐次方程组 Ax=0
    return {"nullspace": [str(v) for v in A.nullspace()], "rank": A.rank()}


def sympy_dsolve(ode_str, func_str="y", var_str="x"):
    """符号解常微分方程。ode_str为sympy格式的ODE表达式。"""
    x = sp.Symbol(var_str)
    y = sp.Function(func_str)(x)
    try:
        ode = sp.sympify(ode_str.replace(func_str, f"({func_str})"))
        sol = sp.dsolve(ode, y)
        result = {"general_solution": str(sol), "latex": sp.latex(sol)}
    except Exception as e:
        result = {"error": str(e)}
    return result


def sympy_ode_numeric(ode_expr, func_str, var_str, y0, t_span, t_eval=None):
    """数值解ODE: dy/dx=f(x,y), y(x0)=y0。使用scipy solve_ivp。"""
    if not HAS_SCIPY:
        return {"error": "需要 scipy"}
    import numpy as np
    from scipy.integrate import solve_ivp

    y_func = sp.lambdify([sp.Symbol(var_str), sp.Symbol(func_str)], sp.sympify(ode_expr), "numpy")
    sol = solve_ivp(lambda t, y: y_func(t, y), t_span, [y0], t_eval=t_eval, method="RK45")
    return {"t": sol.t.tolist(), "y": sol.y[0].tolist(), "success": sol.success, "method": "RK45"}


def sympy_inequality(expr_str, var_str):
    """解不等式。支持 <, >, <=, >=。"""
    x = sp.Symbol(var_str)
    try:
        sol = sp.solve_univariate_inequality(sp.sympify(expr_str), x, relational=False)
        result = {"solution": str(sol), "variable": var_str}
    except Exception as e:
        result = {"error": str(e)}
    return result


def sympy_fsolve(equations, variables, guess=None):
    """数值解非线性方程组。使用scipy fsolve。"""
    if not HAS_SCIPY:
        return {"error": "需要 scipy"}
    import numpy as np
    from scipy.optimize import fsolve

    syms = [sp.Symbol(v) for v in variables]
    f = sp.lambdify(syms, [sp.sympify(eq) for eq in equations], "numpy")
    g = guess or [1] * len(variables)
    sol = fsolve(lambda x: f(*x), g)
    return {variables[i]: float(sol[i]) for i in range(len(variables))}


def sympy_simplify(expr_str):
    expr = sp.sympify(expr_str)
    s = sp.simplify(expr)
    return {"simplified": str(s), "latex": sp.latex(s)}


def sympy_expand(expr_str):
    expr = sp.sympify(expr_str)
    e = sp.expand(expr)
    return {"expanded": str(e), "latex": sp.latex(e)}


def sympy_taylor(expr_str, var_str, point=0, order=5):
    x = sp.Symbol(var_str)
    expr = sp.sympify(expr_str)
    series = sp.series(expr, x, point, order + 1)
    poly = series.removeO()
    return {"series": str(series), "polynomial": str(poly), "latex": sp.latex(series), "point": point, "order": order}


def sympy_eval(expr_str, vars_dict=None, points=None):
    expr = sp.sympify(expr_str)
    if points:
        results = []
        for pt in points:
            subs = {}
            if isinstance(pt, dict):
                subs = {sp.Symbol(k): v for k, v in pt.items()}
            elif isinstance(pt, (list, tuple)):
                free_vars = list(expr.free_symbols)
                subs = {v: pt[i] for i, v in enumerate(free_vars) if i < len(pt)}
            results.append({"point": pt, "value": float(expr.subs(subs).evalf())})
        return {"results": results}
    elif vars_dict:
        subs = {sp.Symbol(k): v for k, v in vars_dict.items()}
        return {"value": float(expr.subs(subs).evalf())}
    return {"value": float(expr.evalf())}


# ====================== 多变量微积分 ======================


def sympy_partial_diff(expr_str, vars_list, order=1, point=None):
    """偏导数"""
    symbols = [sp.Symbol(v) for v in vars_list]
    expr = sp.sympify(expr_str)
    results = {}
    for var_str, sym in zip(vars_list, symbols):
        deriv = sp.diff(expr, sym, order)
        results[f"d/d{var_str}"] = str(deriv)
        results[f"d/d{var_str}_latex"] = sp.latex(deriv)
    out = {"partial_derivatives": results, "expr": expr_str, "order": order}
    if point and len(point) == len(vars_list):
        subs = {s: point[i] for i, s in enumerate(symbols)}
        out["at_point"] = point
        out["values"] = {
            f"d/d{var_str}": float(sp.diff(expr, sym, order).subs(subs).evalf())
            for var_str, sym in zip(vars_list, symbols)
        }
    return out


def sympy_gradient(expr_str, vars_list, point=None):
    """梯度"""
    symbols = [sp.Symbol(v) for v in vars_list]
    expr = sp.sympify(expr_str)
    grad_expr = [sp.diff(expr, s) for s in symbols]
    result = {
        "gradient": [str(g) for g in grad_expr],
        "gradient_latex": sp.latex(sp.Matrix(grad_expr)),
        "variables": vars_list,
    }
    if point and len(point) == len(vars_list):
        subs = {s: point[i] for i, s in enumerate(symbols)}
        gv = [float(g.subs(subs).evalf()) for g in grad_expr]
        result["at_point"] = point
        result["gradient_value"] = gv
        result["magnitude"] = float(sum(v**2 for v in gv) ** 0.5)
        result["geometric"] = (
            f"梯度向量指向函数值增长最快的方向，模长为 {result['magnitude']:.4g}。在点{point}处，最陡上升方向为 {gv}。"
        )
    return result


def sympy_hessian(expr_str, vars_list, point=None):
    """Hessian 矩阵"""
    symbols = [sp.Symbol(v) for v in vars_list]
    expr = sp.sympify(expr_str)
    n = len(symbols)
    hess = [[sp.diff(expr, symbols[i], symbols[j]) for j in range(n)] for i in range(n)]
    result = {
        "hessian": [[str(hess[i][j]) for j in range(n)] for i in range(n)],
        "hessian_latex": sp.latex(sp.Matrix(hess)),
        "variables": vars_list,
    }
    if point and len(point) == n:
        subs = {s: point[i] for i, s in enumerate(symbols)}
        hnum = [[float(hess[i][j].subs(subs).evalf()) for j in range(n)] for i in range(n)]
        result["at_point"] = point
        result["hessian_numeric"] = hnum
        if HAS_NUMPY:
            eigvals = np.linalg.eigvals(np.array(hnum))
            result["eigenvalues"] = [float(v.real) for v in eigvals]
            all_pos = all(v.real > 1e-10 for v in eigvals)
            all_neg = all(v.real < -1e-10 for v in eigvals)
            mixed = any(v.real > 1e-10 for v in eigvals) and any(v.real < -1e-10 for v in eigvals)
            if all_pos:
                result["critical_type"] = "局部极小值点（Hessian正定）"
            elif all_neg:
                result["critical_type"] = "局部极大值点（Hessian负定）"
            elif mixed:
                result["critical_type"] = "鞍点（Hessian不定）"
            else:
                result["critical_type"] = "无法确定（Hessian半定）"
            result["geometric"] = (
                f"Hessian特征值: {[float(f'{v.real:.4g}') for v in eigvals]} → {result['critical_type']}"
            )
    return result


def sympy_jacobian(exprs_list, vars_list, point=None):
    """Jacobian 矩阵"""
    symbols = [sp.Symbol(v) for v in vars_list]
    exprs = [sp.sympify(e) for e in exprs_list]
    m, n = len(exprs), len(symbols)
    jac = [[sp.diff(exprs[i], symbols[j]) for j in range(n)] for i in range(m)]
    result = {
        "jacobian": [[str(jac[i][j]) for j in range(n)] for i in range(m)],
        "jacobian_latex": sp.latex(sp.Matrix(jac)),
        "functions": exprs_list,
        "variables": vars_list,
    }
    if point and len(point) == n:
        subs = {s: point[i] for i, s in enumerate(symbols)}
        jnum = [[float(jac[i][j].subs(subs).evalf()) for j in range(n)] for i in range(m)]
        result["at_point"] = point
        result["jacobian_numeric"] = jnum
        if m == n and HAS_NUMPY:
            result["determinant"] = float(np.linalg.det(np.array(jnum)))
    return result


def sympy_divergence(exprs_list, vars_list, point=None):
    """散度"""
    symbols = [sp.Symbol(v) for v in vars_list]
    exprs = [sp.sympify(e) for e in exprs_list]
    div = sum(sp.diff(exprs[i], symbols[i]) for i in range(len(exprs)))
    result = {"divergence": str(div), "latex": sp.latex(div)}
    if point and len(point) == len(vars_list):
        subs = {s: point[i] for i, s in enumerate(symbols)}
        result["at_point"] = point
        result["value"] = float(div.subs(subs).evalf())
        result["geometric"] = (
            "散度度量向量场在某点'源'或'汇'的强度。正值→向外发散(源)，负值→向内汇聚(汇)，零→无源无汇。"
        )
    return result


# ====================== 数值积分与几何量 ======================


def sympy_numeric_integrate(expr_str, var_str, a, b, n=1000):
    import numpy as np

    x = sp.Symbol(var_str)
    expr = sp.sympify(expr_str)
    f = sp.lambdify(x, expr, "numpy")
    xs = np.linspace(a, b, n)
    ys = f(xs)
    trapz = float(np.trapz(ys, xs))
    dx = (b - a) / (n - 1)
    if n % 2 == 0:
        n_s = n - 1
    else:
        n_s = n
    xs_s = np.linspace(a, b, n_s)
    ys_s = f(xs_s)
    if n_s > 2:
        simps = float((dx / 3) * (ys_s[0] + ys_s[-1] + 4 * np.sum(ys_s[1:-1:2]) + 2 * np.sum(ys_s[2:-2:2])))
    else:
        simps = trapz
    result = {"trapezoidal": trapz, "simpson": simps, "n": n, "a": a, "b": b}
    try:
        exact = float(sp.integrate(expr, (x, a, b)).evalf())
        result["exact"] = exact
        result["trapz_error"] = abs(trapz - exact)
        result["simpson_error"] = abs(simps - exact)
    except Exception:
        pass
    result["geometric"] = f"曲线在[{a},{b}]下面积。梯形≈{trapz:.6g}，辛普森≈{simps:.6g}。"
    return result


def sympy_curve_length(expr_str, var_str, a, b, n=1000):
    import numpy as np

    x = sp.Symbol(var_str)
    expr = sp.sympify(expr_str)
    deriv = sp.diff(expr, x)
    arc_integrand = sp.sqrt(1 + deriv**2)
    f_int = sp.lambdify(x, arc_integrand, "numpy")
    xs = np.linspace(a, b, n)
    ys = f_int(xs)
    length = float(np.trapz(ys, xs))
    try:
        exact_len = sp.integrate(arc_integrand, (x, a, b))
        result = {"arc_length": float(exact_len.evalf()), "exact": str(exact_len)}
    except Exception:
        result = {"arc_length": length, "numeric": True}
    result["a"] = a
    result["b"] = b
    result["geometric"] = f"曲线 x∈[{a},{b}] 弧长≈{result['arc_length']:.6g}。"
    return result


def sympy_curvature(expr_str, var_str, at_point=None):
    x = sp.Symbol(var_str)
    expr = sp.sympify(expr_str)
    f1 = sp.diff(expr, x)
    f2 = sp.diff(f1, x)
    curv = sp.Abs(f2) / (1 + f1**2) ** (sp.Rational(3, 2))
    result = {"curvature_formula": str(curv), "latex": sp.latex(curv)}
    if at_point is not None:
        val = float(curv.subs(x, at_point).evalf())
        result["at_point"] = at_point
        result["curvature"] = val
        radius = 1 / val if abs(val) > 1e-15 else float("inf")
        result["radius_of_curvature"] = radius
        result["geometric"] = f"x={at_point}处曲率={val:.6g}，曲率半径={radius:.4g}。"
    return result


def sympy_area_between(expr1_str, expr2_str, var_str, a, b):
    import numpy as np

    x = sp.Symbol(var_str)
    f = sp.sympify(expr1_str)
    g = sp.sympify(expr2_str)
    diff = sp.Abs(f - g)
    try:
        area = sp.integrate(diff, (x, a, b))
        result = {"area": float(area.evalf()), "exact": str(area)}
    except Exception:
        f_n = sp.lambdify(x, diff, "numpy")
        xs = np.linspace(a, b, 2000)
        result = {"area": float(np.trapz(f_n(xs), xs)), "numeric": True}
    result["between"] = [expr1_str, expr2_str]
    result["a"] = a
    result["b"] = b
    result["geometric"] = f"曲线 {expr1_str} 和 {expr2_str} 在[{a},{b}]间面积≈{result['area']:.6g}。"
    return result


OPERATIONS = {
    "diff": sympy_diff,
    "integrate": sympy_integrate,
    "limit": sympy_limit,
    "root": sympy_root,
    "solve": sympy_solve,
    "linsolve": sympy_linsolve,
    "simplify": lambda expr, **kw: sympy_simplify(expr),
    "expand": lambda expr, **kw: sympy_expand(expr),
    "taylor": sympy_taylor,
    "eval": sympy_eval,
    "partial_diff": sympy_partial_diff,
    "gradient": sympy_gradient,
    "hessian": sympy_hessian,
    "jacobian": sympy_jacobian,
    "divergence": sympy_divergence,
    "integrate_numeric": sympy_numeric_integrate,
    "curve_length": sympy_curve_length,
    "curvature": sympy_curvature,
    "area_between": sympy_area_between,
}


def main():
    if not HAS_SYMPY:
        print(json.dumps({"ok": False, "error": "需要安装 sympy: pip install sympy"}, ensure_ascii=False))
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="符号/数值微积分工具 — 基于 sympy + scipy",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  echo '{"expr":"x**2+3*x+2","op":"diff","var":"x","point":2}' | python calc_sym.py
  python calc_sym.py --expr "sin(x)" --op "integrate" --var "x" --a 0 --b pi
  python calc_sym.py --expr "x**2+y**2" --op "gradient" --vars '["x","y"]' --point-list "[1,2]"
""",
    )
    parser.add_argument("json_input", nargs="?", help="JSON 输入字符串")
    parser.add_argument("--expr", "-e", help="表达式字符串")
    parser.add_argument("--op", "-o", help="操作名称")
    parser.add_argument("--var", help="变量名（单变量）")
    parser.add_argument("--vars", help="变量列表 JSON（多变量）")
    parser.add_argument("--point", type=float, help="求值点（单变量）")
    parser.add_argument("--point-list", help="求值点列表 JSON（多变量）")
    parser.add_argument("--a", type=float, help="定积分下限/求根区间左")
    parser.add_argument("--b", type=float, help="定积分上限/求根区间右")
    parser.add_argument("--guess", type=float, help="求根初始猜测")
    parser.add_argument("--order", type=int, default=1, help="导数阶数/泰勒阶数")
    parser.add_argument("--numeric", action="store_true", help="仅输出数值结果")
    parser.add_argument("--compact", "-c", action="store_true", help="紧凑输出")

    args = parser.parse_args()

    input_data = {}
    if args.json_input:
        try:
            input_data = json.loads(args.json_input)
        except json.JSONDecodeError:
            print(json.dumps({"ok": False, "error": "JSON 解析失败"}, ensure_ascii=False))
            sys.exit(1)
    elif not sys.stdin.isatty():
        raw = sys.stdin.read().strip()
        if raw:
            try:
                input_data = json.loads(raw)
            except json.JSONDecodeError:
                print(json.dumps({"ok": False, "error": "stdin JSON 解析失败"}, ensure_ascii=False))
                sys.exit(1)

    expr = args.expr or input_data.get("expr", "")
    op = args.op or input_data.get("op", "")
    var = args.var or input_data.get("var", "x")

    if op not in ("jacobian", "divergence") and not expr:
        print(json.dumps({"ok": False, "error": "缺少 expr"}, ensure_ascii=False))
        sys.exit(1)
    if not op:
        print(json.dumps({"ok": False, "error": "缺少 op"}, ensure_ascii=False))
        sys.exit(1)
    if op not in OPERATIONS:
        print(json.dumps({"ok": False, "error": f"不支持: {op}，可用: {list(OPERATIONS.keys())}"}, ensure_ascii=False))
        sys.exit(1)

    try:
        kwargs = {"expr_str": expr, "var_str": var}
        if op in ("diff",):
            kwargs["order"] = args.order or input_data.get("order", 1)
            point = args.point or input_data.get("point")
            kwargs["point"] = point
        elif op == "integrate":
            kwargs["a"] = args.a if args.a is not None else input_data.get("a")
            kwargs["b"] = args.b if args.b is not None else input_data.get("b")
        elif op in ("limit",):
            kwargs["point"] = args.point if args.point is not None else input_data.get("point", 0)
        elif op in ("root", "solve"):
            kwargs["guess"] = args.guess or input_data.get("guess")
            if args.a is not None and args.b is not None:
                kwargs["interval"] = [args.a, args.b]
            else:
                kwargs["interval"] = input_data.get("interval")
        elif op == "taylor":
            kwargs["point"] = args.point if args.point is not None else input_data.get("point", 0)
            kwargs["order"] = args.order or input_data.get("order", 5)
        elif op == "eval":
            kwargs["vars_dict"] = input_data.get("vars", {})
            kwargs["points"] = input_data.get("points")
        elif op in ("partial_diff", "gradient", "hessian", "jacobian", "divergence"):
            vars_list = json.loads(args.vars) if args.vars else input_data.get("vars", ["x", "y"])
            kwargs["vars_list"] = vars_list
            pt = args.point_list or input_data.get("point")
            if pt:
                kwargs["point"] = json.loads(pt) if isinstance(pt, str) else pt
            if op == "partial_diff":
                kwargs["order"] = args.order or input_data.get("order", 1)
            if op in ("jacobian", "divergence"):
                el = args.expr or input_data.get("expr", "")
                kwargs["exprs_list"] = (
                    json.loads(el) if isinstance(el, str) and el.startswith("[") else input_data.get("exprs", [el])
                )
                kwargs["expr_str"] = kwargs["exprs_list"][0] if kwargs["exprs_list"] else ""

        result = OPERATIONS[op](**kwargs)
        output = {"ok": True, "op": op, "expr": expr, **result}
        print(json.dumps(output, ensure_ascii=False, indent=None if args.compact else 2, default=str))
    except Exception as e:
        output = {"ok": False, "error": str(e), "op": op, "expr": expr}
        print(json.dumps(output, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
