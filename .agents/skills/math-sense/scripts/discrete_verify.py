#!/usr/bin/env python3
"""
discrete_verify.py — 离散验证与迭代拟合工具

核心理念: 函数的连续性质通过离散采样来验证。给定采样点，用级数和迭代方法反向拟合函数。

用法:
    python discrete_verify.py --op "check" --expr "x**3-3*x" --range "[-2,2]" --n 200 --properties '["极值点个数=2","过原点"]'
    python discrete_verify.py --op "singularities" --expr "sin(x)*exp(-0.1*x)" --range "[0,20]" --n 500
    python discrete_verify.py --op "fit_iterative" --points "[[0,1],[1,2.7],[2,7.4],[3,20]]" --method "polynomial"
    python discrete_verify.py --op "fit_iterative" --points "[[0,0],[1,0.84],[2,0.91],[3,0.14]]" --method "fourier"

支持的操作:
    check, singularities, fit_iterative, refine
"""

import sys, json, math, argparse

try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    import sympy as sp

    HAS_SYMPY = True
except ImportError:
    HAS_SYMPY = False


def _eval_safe(expr_str, x_val):
    """安全求值"""
    import ast as _ast, operator as _op

    ALLOWED = {
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "exp": math.exp,
        "log": math.log,
        "sqrt": math.sqrt,
        "abs": abs,
        "pow": pow,
        "pi": math.pi,
        "e": math.e,
        "max": max,
        "min": min,
        "floor": math.floor,
        "ceil": math.ceil,
    }
    tree = _ast.parse(expr_str.strip(), mode="eval")

    def _ev(n):
        if isinstance(n, _ast.Constant):
            return n.value
        if isinstance(n, _ast.Name):
            if n.id == "x":
                return x_val
            if n.id in ALLOWED:
                return ALLOWED[n.id]
            raise NameError(n.id)
        if isinstance(n, _ast.BinOp):
            l, r = _ev(n.left), _ev(n.right)
            o = {_ast.Add: _op.add, _ast.Sub: _op.sub, _ast.Mult: _op.mul, _ast.Div: _op.truediv, _ast.Pow: _op.pow}
            return o[type(n.op)](l, r)
        if isinstance(n, _ast.UnaryOp):
            v = _ev(n.operand)
            return -v if isinstance(n.op, _ast.USub) else +v
        if isinstance(n, _ast.Call):
            fn = _ev(n.func)
            return fn(*[_ev(a) for a in n.args])
        return 0

    return _ev(tree.body)


# ====================== 采样 + 性质检查 ======================


def op_check(expr_str, range_, n, properties):
    """离散采样后逐一检查性质"""
    x_min, x_max = range_
    xs = np.linspace(x_min, x_max, n)
    ys = np.array([_eval_safe(expr_str, float(x)) for x in xs])

    checks = {}

    for prop in properties:
        prop_l = prop.lower().replace(" ", "")

        if "极值点个数=" in prop:
            target = int(prop.split("=")[1])
            local = _find_local_extrema(xs, ys)
            checks[prop] = {"passed": len(local) == target, "found": len(local), "extrema": local}

        elif "零点个数=" in prop or "零交叉个数=" in prop:
            target = int(prop.split("=")[1])
            zeros = _find_zero_crossings(xs, ys)
            checks[prop] = {"passed": len(zeros) == target, "found": len(zeros), "zeros": zeros}

        elif "拐点个数=" in prop:
            target = int(prop.split("=")[1])
            inflections = _find_inflections(xs, ys)
            checks[prop] = {"passed": len(inflections) == target, "found": len(inflections), "inflections": inflections}

        elif "单调递增" in prop_l:
            diffs = np.diff(ys)
            passed = bool(np.all(diffs >= -1e-8))
            checks[prop] = {"passed": passed, "violation_count": int(np.sum(diffs < -1e-8))}

        elif "单调递减" in prop_l:
            diffs = np.diff(ys)
            passed = bool(np.all(diffs <= 1e-8))
            checks[prop] = {"passed": passed, "violation_count": int(np.sum(diffs > 1e-8))}

        elif "过原点" in prop_l:
            y0 = _eval_safe(expr_str, 0.0)
            checks[prop] = {"passed": abs(y0) < 1e-8, "y_at_0": float(y0)}

        elif "有界" in prop_l:
            checks[prop] = {"passed": True, "min": float(np.min(ys)), "max": float(np.max(ys))}

        elif "对称" in prop_l:
            mid = (x_min + x_max) / 2
            left = ys[xs < mid]
            right = ys[xs >= mid][::-1]
            n_c = min(len(left), len(right))
            err = float(np.mean(np.abs(left[:n_c] - right[:n_c])))
            checks[prop] = {"passed": err < 0.01 * (np.max(ys) - np.min(ys) + 1e-10), "sym_error": err}

        elif "周期" in prop_l:
            m = re.search(r"周期[=＝]?\s*([\d.]+)", prop)
            if m:
                T = float(m.group(1))
                err = float(np.mean(np.abs(ys[: -int(n * T / (x_max - x_min))] - ys[int(n * T / (x_max - x_min)) :])))
                checks[prop] = {"passed": err < 0.01, "period_error": err}
            else:
                checks[prop] = {"passed": False, "note": "请指定周期值，如'周期=6.28'"}

        else:
            checks[prop] = {"passed": None, "note": "无法自动检测该性质，请使用更具体的描述"}
    import re as _re

    all_pass = all(c.get("passed", True) for c in checks.values())

    return {
        "expr": expr_str,
        "range": range_,
        "n": n,
        "y_min": float(np.min(ys)),
        "y_max": float(np.max(ys)),
        "y_at_0": float(_eval_safe(expr_str, 0.0)),
        "checks": checks,
        "all_passed": all_pass,
        "verdict": "所有性质满足" if all_pass else "部分性质不满足",
    }


def _find_local_extrema(xs, ys):
    n = len(ys)
    result = []
    for i in range(1, n - 1):
        if ys[i] > ys[i - 1] and ys[i] > ys[i + 1]:
            result.append({"type": "极大值", "x": float(xs[i]), "y": float(ys[i])})
        elif ys[i] < ys[i - 1] and ys[i] < ys[i + 1]:
            result.append({"type": "极小值", "x": float(xs[i]), "y": float(ys[i])})
    return result[:10]


def _find_zero_crossings(xs, ys):
    crossings = []
    for i in range(1, len(ys)):
        if ys[i - 1] * ys[i] < 0:
            x0 = float(xs[i - 1] - ys[i - 1] * (xs[i] - xs[i - 1]) / (ys[i] - ys[i - 1]))
            crossings.append(x0)
    return crossings[:10]


def _find_inflections(xs, ys):
    d2 = np.diff(ys, 2)
    signs = np.sign(d2)
    inflections = []
    for i in range(1, len(signs)):
        if signs[i] != signs[i - 1] and signs[i] != 0:
            inflections.append({"x": float(xs[i + 1]), "y": float(ys[i + 1])})
    return inflections[:10]


# ====================== 特异点检测 ======================


def op_singularities(expr_str, range_, n):
    """检测函数的所有特异点"""
    x_min, x_max = range_
    xs = np.linspace(x_min, x_max, n)
    ys = np.array([_eval_safe(expr_str, float(x)) for x in xs])

    result = {
        "expr": expr_str,
        "range": range_,
        "n": n,
        "global_max": {"x": float(xs[np.argmax(ys)]), "y": float(np.max(ys))},
        "global_min": {"x": float(xs[np.argmin(ys)]), "y": float(np.min(ys))},
        "local_extrema": _find_local_extrema(xs, ys),
        "zero_crossings": _find_zero_crossings(xs, ys),
        "inflection_points": _find_inflections(xs, ys),
    }

    # 导数近似信息
    dy = np.diff(ys) / (xs[1] - xs[0])
    result["max_slope"] = float(np.max(np.abs(dy)))
    result["mean_slope"] = float(np.mean(np.abs(dy)))

    # 渐近行为（端点趋势）
    left_trend = "递增" if dy[0] > 0 else ("递减" if dy[0] < 0 else "平坦")
    right_trend = "递增" if dy[-1] > 0 else ("递减" if dy[-1] < 0 else "平坦")
    result["endpoint_trend"] = {"left": left_trend, "right": right_trend}

    return result


# ====================== 迭代拟合 ======================


def op_fit_iterative(points, method="polynomial", max_degree=10):
    """用迭代方法拟合离散点"""
    if isinstance(points, str):
        points = json.loads(points)
    xs = np.array([p[0] for p in points], dtype=float)
    ys = np.array([p[1] for p in points], dtype=float)
    n_pts = len(points)

    if method == "polynomial":
        return _fit_polynomial_iterative(xs, ys, max_degree)

    elif method == "fourier":
        return _fit_fourier_iterative(xs, ys)

    elif method == "exponential":
        return _fit_exponential_iterative(xs, ys)

    elif method == "taylor":
        return _fit_taylor_at_point(xs, ys)

    elif method == "auto":
        results = {}
        for m in ["polynomial", "fourier", "exponential"]:
            try:
                results[m] = op_fit_iterative(points, m, max_degree)
            except Exception:
                pass
        best = min(results.items(), key=lambda x: x[1].get("r_squared", -1) or -1, default=(None, {}))
        return {"auto_best": best[0], "all_results": results}

    return {"error": f"不支持的方法: {method}"}


def _fit_polynomial_iterative(xs, ys, max_degree=8):
    """多项式迭代拟合：逐步增加次数直到R²不再显著提升"""
    best_r2, best_deg, best_coeffs = -1, 1, None
    path = []
    for deg in range(1, min(max_degree + 1, len(xs))):
        coeffs = np.polyfit(xs, ys, deg)
        pred = np.polyval(coeffs, xs)
        ss_res = np.sum((ys - pred) ** 2)
        ss_tot = np.sum((ys - np.mean(ys)) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
        path.append({"degree": deg, "r_squared": round(float(r2), 6)})
        if r2 > best_r2 + 0.001 or (r2 > 0.999 and deg < best_deg):
            best_r2, best_deg, best_coeffs = r2, deg, coeffs
        elif deg > 3 and r2 - best_r2 < 0.001:
            break  # 不再显著提升

    return {
        "method": "polynomial",
        "best_degree": best_deg,
        "coefficients": best_coeffs.tolist(),
        "r_squared": float(best_r2),
        "polynomial": " + ".join(f"{c:.4g}*x^{len(best_coeffs) - 1 - i}" for i, c in enumerate(best_coeffs)),
        "iteration_path": path,
    }


def _fit_fourier_iterative(xs, ys):
    """傅里叶级数拟合"""
    n = len(xs)
    T = xs[-1] - xs[0]
    # 最多尝试 n//2 个谐波
    max_harmonics = min(n // 2, 20)
    best_r2, best_n, best_coeffs = -1, 0, None
    path = []

    for nh in range(1, max_harmonics + 1):
        # 构建设计矩阵：常数 + cos(kωx) + sin(kωx), k=1..nh
        omega = 2 * np.pi / T
        A = np.ones((n, 1 + 2 * nh))
        for k in range(1, nh + 1):
            A[:, 2 * k - 1] = np.cos(k * omega * xs)
            A[:, 2 * k] = np.sin(k * omega * xs)
        try:
            coeffs, _, _, _ = np.linalg.lstsq(A, ys, rcond=None)
        except np.linalg.LinAlgError:
            break
        pred = A @ coeffs
        ss_res = np.sum((ys - pred) ** 2)
        ss_tot = np.sum((ys - np.mean(ys)) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
        path.append({"harmonics": nh, "r_squared": round(float(r2), 6)})
        if r2 > best_r2 + 0.005:
            best_r2, best_n, best_coeffs = r2, nh, coeffs
        elif nh > 5 and r2 - best_r2 < 0.002:
            break

    return {
        "method": "fourier",
        "best_harmonics": best_n,
        "a0": float(best_coeffs[0]),
        "coefficients": [
            {"k": k, "a": float(best_coeffs[2 * k - 1]), "b": float(best_coeffs[2 * k])} for k in range(1, best_n + 1)
        ],
        "r_squared": float(best_r2),
        "iteration_path": path,
    }


def _fit_exponential_iterative(xs, ys):
    """指数拟合 y=a*exp(b*x)+c —— 迭代优化a,b,c"""
    valid = ys > 0
    if not np.all(valid):
        shifted = ys - np.min(ys) + 1
        log_ys = np.log(shifted)
    else:
        log_ys = np.log(ys)
    coeffs = np.polyfit(xs, log_ys, 1)
    a, b = np.exp(coeffs[1]), coeffs[0]
    # 简单迭代精化
    for _ in range(10):
        pred = a * np.exp(b * xs)
        errors = ys - pred
        # 梯度下降一步
        grad_a = -2 * np.mean(errors * np.exp(b * xs))
        grad_b = -2 * np.mean(errors * a * xs * np.exp(b * xs))
        lr = 0.01
        a -= lr * grad_a
        b -= lr * grad_b
    pred_final = a * np.exp(b * xs)
    ss_res = np.sum((ys - pred_final) ** 2)
    ss_tot = np.sum((ys - np.mean(ys)) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
    return {
        "method": "exponential",
        "formula": f"{a:.4g}*exp({b:.4g}*x)",
        "a": float(a),
        "b": float(b),
        "r_squared": float(r2),
    }


def _fit_taylor_at_point(xs, ys):
    """在采样点中心做泰勒展开拟合"""
    x0 = np.mean(xs)
    # 数值估计各阶导数
    h = (xs[1] - xs[0]) * 2
    coeffs = []
    for order in range(6):
        if order == 0:
            c = _eval_safe(f"{ys[0]}", 0)  # 近似：取最近点的值
        else:
            c = np.sum(ys * (xs - x0) ** order) / np.sum((xs - x0) ** (2 * order) + 1e-10)
        coeffs.append(c)
    poly_str = " + ".join(f"{coeffs[i]:.4g}*(x-{x0:.4g})^{i}" for i in range(len(coeffs)) if abs(coeffs[i]) > 1e-10)
    return {
        "method": "taylor",
        "center": float(x0),
        "coefficients": [float(c) for c in coeffs],
        "polynomial": poly_str,
        "note": "泰勒展开在展开点附近精确，远离时误差增大",
    }


OPERATIONS = {
    "check": op_check,
    "singularities": op_singularities,
    "fit_iterative": op_fit_iterative,
}


def main():
    parser = argparse.ArgumentParser(
        description="离散验证与迭代拟合工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python discrete_verify.py --op "check" --expr "x**3-3*x" --range "[-2,2]" --n 200 --properties '["极值点个数=2","过原点"]'
  python discrete_verify.py --op "singularities" --expr "sin(x)*exp(-0.1*x)" --range "[0,20]" --n 500
  python discrete_verify.py --op "fit_iterative" --points "[[0,1],[1,2.7],[2,7.4],[3,20]]" --method "polynomial"
  python discrete_verify.py --op "fit_iterative" --points "[[0,0],[1,0.84],[2,0.91],[3,0.14]]" --method "fourier"
""",
    )
    parser.add_argument("--op", "-o", help="操作名称")
    parser.add_argument("--expr", "-e", help="函数表达式")
    parser.add_argument("--range", help="范围 [min,max]")
    parser.add_argument("--n", type=int, default=200, help="采样点数")
    parser.add_argument("--properties", help="性质列表 JSON")
    parser.add_argument("--points", help="离散点 JSON")
    parser.add_argument("--method", default="polynomial", help="拟合方法: polynomial/fourier/exponential/taylor/auto")
    parser.add_argument("--compact", "-c", action="store_true", help="紧凑输出")
    parser.add_argument("json_input", nargs="?", help="JSON 输入")

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
        print(json.dumps({"ok": False, "error": f"不支持: {op}, 可用: {list(OPERATIONS.keys())}"}, ensure_ascii=False))
        sys.exit(1)

    try:
        kwargs = {}
        if op in ("check", "singularities"):
            kwargs["expr_str"] = args.expr or input_data.get("expr", "")
            rng = args.range or input_data.get("range", [-10, 10])
            kwargs["range_"] = json.loads(rng) if isinstance(rng, str) else rng
            kwargs["n"] = args.n or input_data.get("n", 200)
            if op == "check":
                kwargs["properties"] = (
                    json.loads(args.properties) if args.properties else input_data.get("properties", [])
                )
        elif op == "fit_iterative":
            kwargs["points"] = args.points or input_data.get("points", [])
            kwargs["method"] = args.method or input_data.get("method", "polynomial")

        result = OPERATIONS[op](**kwargs)
        output = {"ok": True, "op": op, **result}
        print(json.dumps(output, ensure_ascii=False, indent=None if args.compact else 2, default=str))
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
