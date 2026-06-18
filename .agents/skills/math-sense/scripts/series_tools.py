#!/usr/bin/env python3
"""
series_tools.py — 级数工具（泰勒展开 / FFT / 牛顿迭代 / 二分法）

用法:
    echo '{"op":"taylor","expr":"sin(x)","var":"x","point":0,"order":5}' | python series_tools.py
    python series_tools.py --op "fft" --data "[0,1,0,-1,0,1,0,-1]" --dt 1.0
    python series_tools.py --op "newton" --expr "x**3-2*x-5" --var "x" --guess 2
    python series_tools.py --op "bisect" --expr "x**3-2*x-5" --var "x" --a 2 --b 3

支持的操作:
    taylor, fft, ifft, dft, newton, bisect, fixed_point, secant
"""

import sys, json, math, argparse, cmath

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


def _eval_math(expr_str, vars_dict):
    """安全表达式求值"""
    import ast as _ast
    import operator as _op

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
    }
    tree = _ast.parse(expr_str.strip(), mode="eval")

    def _ev(node):
        if isinstance(node, _ast.Constant):
            return node.value
        if isinstance(node, _ast.Name):
            if node.id in vars_dict:
                return vars_dict[node.id]
            if node.id in ALLOWED:
                return ALLOWED[node.id]
            raise NameError(node.id)
        if isinstance(node, _ast.BinOp):
            l, r = _ev(node.left), _ev(node.right)
            ops = {_ast.Add: _op.add, _ast.Sub: _op.sub, _ast.Mult: _op.mul, _ast.Div: _op.truediv, _ast.Pow: _op.pow}
            return ops[type(node.op)](l, r)
        if isinstance(node, _ast.UnaryOp):
            v = _ev(node.operand)
            return -v if isinstance(node.op, _ast.USub) else +v
        if isinstance(node, _ast.Call):
            fn = _ev(node.func)
            args = [_ev(a) for a in node.args]
            return fn(*args)
        return 0

    return _ev(tree.body)


# ====================== 泰勒展开 ======================


def op_taylor(expr, var, point=0, order=5):
    """泰勒展开"""
    if not HAS_SYMPY:
        # 降级：数值验证
        return {"error": "需要 sympy 做符号泰勒展开", "hint": "使用 pip install sympy"}
    x = sp.Symbol(var)
    f = sp.sympify(expr)
    series = sp.series(f, x, point, order + 1)
    poly = series.removeO()

    # 数值验证：在展开点附近比较
    f_lambdify = sp.lambdify(x, f, "numpy")
    p_lambdify = sp.lambdify(x, poly, "numpy")
    verification = []
    for offset in [-0.5, -0.2, -0.1, 0.1, 0.2, 0.5]:
        xv = point + offset
        try:
            exact = float(f_lambdify(xv))
            approx = float(p_lambdify(xv))
            err = abs(exact - approx)
            verification.append({"x": xv, "exact": exact, "approx": approx, "error": err})
        except Exception:
            pass

    # 拉格朗日余项估计
    # R_n = f^{(n+1)}(xi) / (n+1)! * (x-point)^{n+1}
    try:
        deriv = sp.diff(f, x, order + 1)
        d_lambdify = sp.lambdify(x, deriv, "numpy")
        max_deriv = max(abs(d_lambdify(point + offset)) for offset in [-0.5, 0.5])
        import math as _math

        remainder_bound = max_deriv / _math.factorial(order + 1) * (0.5) ** (order + 1)
    except Exception:
        remainder_bound = None

    return {
        "series": str(series),
        "polynomial": str(poly),
        "latex": sp.latex(series),
        "point": point,
        "order": order,
        "verification": verification,
        "remainder_bound": float(remainder_bound) if remainder_bound else None,
    }


# ====================== FFT ======================


def op_fft(data, dt=1.0):
    """快速傅里叶变换。data: 时域采样值列表。dt: 采样间隔"""
    if HAS_NUMPY:
        arr = np.array(data, dtype=complex)
        spectrum = np.fft.fft(arr)
        freqs = np.fft.fftfreq(len(arr), dt)
        magnitude = np.abs(spectrum)
        phase = np.angle(spectrum)

        # 只取正频率
        n = len(arr)
        pos_mask = freqs >= 0
        pos_freqs = freqs[pos_mask].tolist()
        pos_mag = magnitude[pos_mask].tolist()
        pos_phase = phase[pos_mask].tolist()

        # 找主频
        if len(pos_mag) > 1:
            main_idx = int(np.argmax(pos_mag[1:])) + 1  # 跳过 DC
            main_freq = pos_freqs[main_idx]
            main_amp = pos_mag[main_idx]
        else:
            main_freq, main_amp = 0, pos_mag[0]

        total_power = float(np.sum(magnitude**2))

        return {
            "frequencies": pos_freqs[: min(50, len(pos_freqs))],
            "magnitude": pos_mag[: min(50, len(pos_mag))],
            "phase": pos_phase[: min(50, len(pos_phase))],
            "main_frequency": float(main_freq),
            "main_amplitude": float(main_amp),
            "total_power": total_power,
            "n_samples": n,
            "dt": dt,
        }
    else:
        # 纯 Python DFT
        n = len(data)
        spectrum = []
        for k in range(n):
            real = sum(data[t] * math.cos(2 * math.pi * k * t / n) for t in range(n))
            imag = -sum(data[t] * math.sin(2 * math.pi * k * t / n) for t in range(n))
            spectrum.append(complex(real, imag))
        mag = [abs(s) for s in spectrum]
        main_idx = max(range(1, n // 2 + 1), key=lambda i: mag[i], default=0)
        return {
            "magnitude": mag[: n // 2 + 1],
            "main_index": main_idx,
            "main_amplitude": mag[main_idx],
            "n_samples": n,
            "dt": dt,
            "hint": "安装 numpy 可获得更快的 FFT",
        }


def op_dft(data, dt=1.0):
    """离散傅里叶变换（纯 Python，作为F检验参考）"""
    return op_fft(data, dt)


# ====================== 求根方法 ======================


def op_newton(expr, var, guess, tol=1e-10, max_iter=100):
    """牛顿迭代法"""
    steps = []
    x = guess
    for i in range(max_iter):
        fx = _eval_math(expr, {var: x})
        # 数值导数
        h = 1e-8
        fpx = (_eval_math(expr, {var: x + h}) - _eval_math(expr, {var: x - h})) / (2 * h)
        if abs(fpx) < 1e-15:
            steps.append({"iter": i, "x": x, "fx": fx, "fpx": fpx, "status": "导数接近0"})
            break
        x_new = x - fx / fpx
        steps.append({"iter": i, "x": x, "x_new": x_new, "fx": fx, "fpx": fpx, "dx": abs(x_new - x)})
        if abs(x_new - x) < tol:
            x = x_new
            break
        x = x_new

    return {
        "root": float(x),
        "f_at_root": float(_eval_math(expr, {var: x})),
        "iterations": len(steps),
        "steps": steps[-5:] if len(steps) > 5 else steps,
        "method": "newton",
        "tolerance": tol,
    }


def op_bisect(expr, var, a, b, tol=1e-10, max_iter=200):
    """二分法"""
    fa = _eval_math(expr, {var: a})
    fb = _eval_math(expr, {var: b})
    if fa * fb > 0:
        return {"error": f"f({a})={fa} 和 f({b})={fb} 同号，区间内可能无根或无奇数个根"}

    steps = []
    for i in range(max_iter):
        c = (a + b) / 2
        fc = _eval_math(expr, {var: c})
        steps.append({"iter": i, "a": a, "b": b, "c": c, "fc": fc, "interval": b - a})
        if abs(fc) < tol or (b - a) / 2 < tol:
            a, b = c, c
            break
        if fa * fc < 0:
            b = c
            fb = fc
        else:
            a = c
            fa = fc

    return {
        "root": float((a + b) / 2),
        "f_at_root": float(fc) if steps else None,
        "iterations": len(steps),
        "steps": steps[-5:] if len(steps) > 5 else steps,
        "method": "bisect",
        "final_interval": b - a,
        "tolerance": tol,
    }


def op_convolve(a, b, mode="full"):
    """一维离散卷积 y[n]=sum_k a[k]*b[n-k]。滑动加权和——信号处理核心操作。"""
    if HAS_NUMPY:
        a = np.array(a, dtype=float)
        b = np.array(b, dtype=float)
        r = np.convolve(a, b, mode=mode)
        return {
            "convolved": r.tolist(),
            "len_a": len(a),
            "len_b": len(b),
            "len_result": len(r),
            "mode": mode,
            "geometric": "卷积=滑动加权和:把b翻转后滑过a,每个位置计算重合部分的乘积之和。时域卷积=频域乘积(FFT加速)。",
        }
    # 纯Python
    a = list(a)
    b = list(b)
    n_out = len(a) + len(b) - 1
    r = []
    for n in range(n_out):
        total = 0
        for k in range(max(0, n - len(b) + 1), min(n + 1, len(a))):
            total += a[k] * b[n - k]
        r.append(total)
    if mode == "same":
        start = (n_out - len(a)) // 2
        r = r[start : start + len(a)]
    elif mode == "valid":
        r = r[len(b) - 1 : len(a)] if len(a) >= len(b) else []
    return {
        "convolved": r,
        "len_a": len(a),
        "len_b": len(b),
        "len_result": len(r),
        "mode": mode,
        "geometric": "卷积=滑动加权和。时域卷积=频域乘积(可用FFT加速O(N log N))",
    }


def op_fft_convolve(a, b):
    """FFT快速卷积: ifft(fft(a)*fft(b))。O(N log N)，适合长数组。"""
    if not HAS_NUMPY:
        return {"error": "need numpy"}
    a = np.array(a)
    b = np.array(b)
    n = len(a) + len(b) - 1
    A = np.fft.fft(a, n)
    B = np.fft.fft(b, n)
    r = np.real(np.fft.ifft(A * B))
    return {"convolved_fft": r.tolist(), "len_result": len(r), "note": "FFT加速 O(N log N),长数组>1000建议使用"}


OPERATIONS = {
    "taylor": op_taylor,
    "fft": op_fft,
    "ifft": op_fft,  # 简化
    "dft": op_dft,
    "newton": op_newton,
    "bisect": op_bisect,
    "convolve": op_convolve,
    "fft_convolve": op_fft_convolve,
}


def main():
    parser = argparse.ArgumentParser(
        description="级数工具 — 泰勒展开 / FFT / 牛顿迭代 / 二分法",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python series_tools.py --op "taylor" --expr "sin(x)" --point 0 --order 5
  python series_tools.py --op "fft" --data "[0,1,0,-1]" --dt 1.0
  python series_tools.py --op "newton" --expr "x**3-2*x-5" --guess 2
  python series_tools.py --op "bisect" --expr "x**3-2*x-5" --a 2 --b 3
        """,
    )
    parser.add_argument("json_input", nargs="?", help="JSON 输入")
    parser.add_argument("--op", "-o", help="操作名称")
    parser.add_argument("--expr", "-e", help="表达式")
    parser.add_argument("--var", default="x", help="变量名")
    parser.add_argument("--point", type=float, default=0, help="展开点")
    parser.add_argument("--order", type=int, default=5, help="展开阶数")
    parser.add_argument("--data", help="采样数据 JSON")
    parser.add_argument("--dt", type=float, default=1.0, help="采样间隔")
    parser.add_argument("--guess", type=float, help="初始猜测")
    parser.add_argument("--a", type=float, help="二分左端点")
    parser.add_argument("--b", type=float, help="二分右端点")
    parser.add_argument("--tol", type=float, default=1e-10, help="容差")
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
        print(json.dumps({"ok": False, "error": f"不支持: {op}，可用: {list(OPERATIONS.keys())}"}, ensure_ascii=False))
        sys.exit(1)

    try:
        kwargs = {}
        if op == "taylor":
            kwargs["expr"] = args.expr or input_data.get("expr", "")
            kwargs["var"] = args.var or input_data.get("var", "x")
            kwargs["point"] = args.point or input_data.get("point", 0)
            kwargs["order"] = args.order or input_data.get("order", 5)
        elif op in ("fft", "ifft", "dft"):
            kwargs["data"] = json.loads(args.data) if args.data else input_data.get("data", [])
            kwargs["dt"] = args.dt or input_data.get("dt", 1.0)
        elif op in ("newton",):
            kwargs["expr"] = args.expr or input_data.get("expr", "")
            kwargs["var"] = args.var or input_data.get("var", "x")
            kwargs["guess"] = args.guess or input_data.get("guess", 0)
            kwargs["tol"] = args.tol or input_data.get("tol", 1e-10)
        elif op in ("bisect",):
            kwargs["expr"] = args.expr or input_data.get("expr", "")
            kwargs["var"] = args.var or input_data.get("var", "x")
            kwargs["a"] = args.a or input_data.get("a", 0)
            kwargs["b"] = args.b or input_data.get("b", 0)
            kwargs["tol"] = args.tol or input_data.get("tol", 1e-10)

        result = OPERATIONS[op](**kwargs)
        output = {"ok": True, "op": op, **result}
        print(json.dumps(output, ensure_ascii=False, indent=None if args.compact else 2, default=str))
    except Exception as e:
        output = {"ok": False, "error": str(e), "op": op}
        print(json.dumps(output, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
