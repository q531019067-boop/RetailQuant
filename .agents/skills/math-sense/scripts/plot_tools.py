#!/usr/bin/env python3
"""
plot_tools.py — 函数曲线与统计图表绘制工具

用法:
    python plot_tools.py --op "curve" --expr "sin(x)*exp(-0.1*x)" --range "[0,20]"
    python plot_tools.py --op "histogram" --data "[1,2,2,3,3,3,4,4,5]"
    python plot_tools.py --op "comparison" --exprs '["sin(x)","cos(x)","sin(x)*cos(x)"]' --range "[0,6.28]"
    python plot_tools.py --op "ascii" --data "[3,5,2,8,6,4,7]" --width 40

支持的操作:
    curve, histogram, scatter, comparison, polar, ascii
"""

import sys, json, math, os, argparse

try:
    import matplotlib

    matplotlib.use("Agg")  # 无 GUI 后端
    import matplotlib.pyplot as plt
    import numpy as np

    HAS_MPL = True
except ImportError:
    HAS_MPL = False


def _eval_simple(expr_str, vars_dict):
    import ast as _ast, math as _math, operator as _op

    ALLOWED = {
        "sin": _math.sin,
        "cos": _math.cos,
        "tan": _math.tan,
        "exp": _math.exp,
        "log": _math.log,
        "sqrt": _math.sqrt,
        "abs": abs,
        "pow": pow,
        "pi": _math.pi,
        "e": _math.e,
    }
    tree = _ast.parse(expr_str.strip(), mode="eval")

    def _ev(n):
        if isinstance(n, _ast.Constant):
            return n.value
        if isinstance(n, _ast.Name):
            if n.id in vars_dict:
                return vars_dict[n.id]
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
        raise ValueError(type(n).__name__)

    return _ev(tree.body)


def _ensure_output_dir(path):
    d = os.path.dirname(path)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)
    return path


# ====================== Matplotlib 图表 ======================


def op_curve(expr, var, range_, n=200, output=None, title=None, xlabel="x", ylabel="f(x)", grid=True):
    """绘制函数曲线"""
    if not HAS_MPL:
        return _fallback_ascii_curve(expr, var, range_, n)
    x_min, x_max = range_
    xs = np.linspace(x_min, x_max, n)
    ys = np.array([_eval_simple(expr, {var: float(x)}) for x in xs])
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(xs, ys, "b-", linewidth=1.5, label=expr)
    ax.axhline(y=0, color="gray", linewidth=0.5, linestyle="--")
    ax.axvline(x=0, color="gray", linewidth=0.5, linestyle="--")
    if grid:
        ax.grid(True, alpha=0.3)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title or f"f({var}) = {expr}")
    ax.legend()
    if not output:
        output = os.path.join(os.getcwd(), f"curve_{hash(expr) % 10000}.png")
    _ensure_output_dir(output)
    fig.savefig(output, dpi=100, bbox_inches="tight")
    plt.close(fig)
    return {
        "image": output,
        "range": range_,
        "n": n,
        "y_min": float(np.min(ys)),
        "y_max": float(np.max(ys)),
        "y_mean": float(np.mean(ys)),
    }


def op_histogram(data, bins=20, output=None, title="Histogram", xlabel="Value", ylabel="Frequency"):
    """直方图"""
    if not HAS_MPL:
        return _ascii_histogram(data, bins)
    arr = np.array(data, dtype=float)
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(arr, bins=bins, color="steelblue", edgecolor="white", alpha=0.85)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(True, alpha=0.3, axis="y")
    # 叠加统计线
    mean = float(np.mean(arr))
    ax.axvline(x=mean, color="red", linestyle="--", linewidth=1, label=f"Mean={mean:.3f}")
    ax.legend()
    if not output:
        output = os.path.join(os.getcwd(), f"histogram_{hash(str(data)) % 10000}.png")
    _ensure_output_dir(output)
    fig.savefig(output, dpi=100, bbox_inches="tight")
    plt.close(fig)
    return {
        "image": output,
        "bins": bins,
        "mean": mean,
        "std": float(np.std(arr)),
        "count": len(arr),
    }


def op_scatter(x, y, output=None, title="Scatter", xlabel="X", ylabel="Y"):
    """散点图"""
    if not HAS_MPL:
        return {"error": "需要 matplotlib"}
    x_arr = np.array(x, dtype=float)
    y_arr = np.array(y, dtype=float)
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.scatter(x_arr, y_arr, c="steelblue", alpha=0.6, s=20, edgecolors="none")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    # 回归线
    if len(x_arr) > 2:
        coeffs = np.polyfit(x_arr, y_arr, 1)
        line_x = np.array([x_arr.min(), x_arr.max()])
        ax.plot(line_x, np.polyval(coeffs, line_x), "r--", linewidth=1, label=f"y={coeffs[0]:.3f}x+{coeffs[1]:.3f}")
        ax.legend()
    if not output:
        output = os.path.join(os.getcwd(), f"scatter_{hash(str(x)) % 10000}.png")
    _ensure_output_dir(output)
    fig.savefig(output, dpi=100, bbox_inches="tight")
    plt.close(fig)
    r = float(np.corrcoef(x_arr, y_arr)[0, 1]) if len(x_arr) > 2 else 0
    return {"image": output, "correlation": r, "count": len(x_arr)}


def op_comparison(exprs, var, range_, n=200, output=None, title=None):
    """多曲线对比"""
    if not HAS_MPL:
        return {"error": "需要 matplotlib"}
    x_min, x_max = range_
    xs = np.linspace(x_min, x_max, n)
    fig, ax = plt.subplots(figsize=(10, 5))
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]
    for i, expr in enumerate(exprs):
        ys = np.array([_eval_simple(expr, {var: float(x)}) for x in xs])
        ax.plot(xs, ys, color=colors[i % len(colors)], linewidth=1.5, label=expr)
    ax.axhline(y=0, color="gray", linewidth=0.5, linestyle="--")
    ax.grid(True, alpha=0.3)
    ax.set_xlabel(var)
    ax.set_ylabel("y")
    ax.set_title(title or f"Comparison of {len(exprs)} functions")
    ax.legend()
    if not output:
        output = os.path.join(os.getcwd(), f"comparison_{hash(str(exprs)) % 10000}.png")
    _ensure_output_dir(output)
    fig.savefig(output, dpi=100, bbox_inches="tight")
    plt.close(fig)
    return {"image": output, "functions": exprs, "n": n}


def op_polar(expr_r, var_theta, n=360, output=None, title=None):
    """极坐标图"""
    if not HAS_MPL:
        return {"error": "需要 matplotlib"}
    thetas = np.linspace(0, 2 * np.pi, n)
    rs = np.array([_eval_simple(expr_r, {var_theta: float(t)}) for t in thetas])
    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw={"projection": "polar"})
    ax.plot(thetas, rs, "b-", linewidth=1.5)
    ax.set_title(title or f"r({var_theta}) = {expr_r}")
    ax.grid(True, alpha=0.3)
    if not output:
        output = os.path.join(os.getcwd(), f"polar_{hash(expr_r) % 10000}.png")
    _ensure_output_dir(output)
    fig.savefig(output, dpi=100, bbox_inches="tight")
    plt.close(fig)
    return {"image": output, "n": n}


# ====================== ASCII 图表（无 matplotlib 降级） ======================


def _ascii_histogram(data, bins=20):
    """纯文本直方图"""
    if not data:
        return {"error": "无数据"}
    mn, mx = min(data), max(data)
    w = (mx - mn) / bins if bins > 0 and mx > mn else 1
    counts = [0] * bins
    for v in data:
        idx = min(int((v - mn) / w), bins - 1) if w > 0 else 0
        counts[idx] += 1
    max_count = max(counts) if counts else 1
    height = 15
    lines = []
    for row in range(height, 0, -1):
        threshold = max_count * row / height
        line = "".join("█" if c >= threshold else ("▄" if c >= threshold * 0.5 else " ") for c in counts)
        lines.append(f"  {line}")
    lines.append("  " + "▔" * bins)
    bin_labels = [f"{mn + i * w:.1f}" for i in range(0, bins + 1, max(1, bins // 5))]
    lines.append("  " + "  ".join(bin_labels[:6]))
    return {"ascii_chart": "\n".join(lines), "count": len(data), "bins": bins}


def _fallback_ascii_curve(expr, var, range_, n):
    """纯文本曲线"""
    x_min, x_max = range_
    w = 70
    h = 20
    xs = []
    ys = []
    for i in range(n):
        x = x_min + (x_max - x_min) * i / (n - 1)
        y = _eval_simple(expr, {var: x})
        xs.append(x)
        ys.append(y)
    y_min, y_max = min(ys), max(ys)
    y_range = y_max - y_min if y_max > y_min else 1
    grid = [[" " for _ in range(w)] for _ in range(h)]
    for i in range(n):
        col = min(int((xs[i] - x_min) / (x_max - x_min) * (w - 1)), w - 1)
        row = h - 1 - min(int((ys[i] - y_min) / y_range * (h - 1)), h - 1)
        grid[row][col] = "●"
    lines = [f"  [{y_max:.3f}] " + "".join(row) for row in grid]
    lines.append(f"  [{y_min:.3f}] " + "─" * w)
    return {"ascii_chart": "\n".join(lines), "ascii_note": "安装 matplotlib 可获得高清图片输出"}


def op_ascii_plot(data=None, expr=None, var="x", range_=None, width=60, height=20, mode="line"):
    """纯 ASCII 图表"""
    if data:
        data = json.loads(data) if isinstance(data, str) else data
        mn, mx = min(data), max(data)
        rng = mx - mn if mx > mn else 1
        grid = [[" " for _ in range(width)] for _ in range(height)]
        for i, v in enumerate(data):
            col = int(i / len(data) * (width - 1))
            row = height - 1 - int((v - mn) / rng * (height - 1))
            grid[min(row, height - 1)][col] = "●"
        lines = [f"{mx:7.3f}|" + "".join(r) for r in grid]
        lines.append(f"{mn:7.3f}|" + "─" * width)
        return {"ascii_chart": "\n".join(lines), "n": len(data)}
    elif expr and range_:
        return _fallback_ascii_curve(expr, var, range_, max(50, width))
    return {"error": "需要 data 或 expr+range"}


OPERATIONS = {
    "curve": op_curve,
    "histogram": op_histogram,
    "scatter": op_scatter,
    "comparison": op_comparison,
    "polar": op_polar,
    "ascii": op_ascii_plot,
}


def main():
    parser = argparse.ArgumentParser(
        description="函数曲线与统计图表绘制工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python plot_tools.py --op "curve" --expr "sin(x)*exp(-0.1*x)" --range "[0,20]"
  python plot_tools.py --op "histogram" --data "[1,2,2,3,3,3,4,4,5]"
  python plot_tools.py --op "comparison" --exprs '["sin(x)","cos(x)"]' --range "[0,6.28]"
  python plot_tools.py --op "ascii" --data "[3,5,2,8,6,4,7]"
""",
    )
    parser.add_argument("--op", "-o", help="操作名称")
    parser.add_argument("--expr", "-e", help="函数表达式")
    parser.add_argument("--exprs", help="多表达式 JSON")
    parser.add_argument("--var", default="x", help="变量名")
    parser.add_argument("--range", help="范围 [min,max]")
    parser.add_argument("--data", help="数据 JSON")
    parser.add_argument("--x", help="X数据 JSON")
    parser.add_argument("--y", help="Y数据 JSON")
    parser.add_argument("--n", type=int, default=200, help="采样点数")
    parser.add_argument("--bins", type=int, default=20, help="直方图bins")
    parser.add_argument("--output", help="输出图片路径")
    parser.add_argument("--title", help="图表标题")
    parser.add_argument("--width", type=int, default=60, help="ASCII宽度")
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
        if op == "curve":
            kwargs["expr"] = args.expr or input_data.get("expr", "")
            kwargs["var"] = args.var or input_data.get("var", "x")
            rng = args.range or input_data.get("range", [-10, 10])
            kwargs["range_"] = json.loads(rng) if isinstance(rng, str) else rng
            kwargs["n"] = args.n or input_data.get("n", 200)
            kwargs["output"] = args.output or input_data.get("output")
            kwargs["title"] = args.title or input_data.get("title")
        elif op == "histogram":
            d = args.data or input_data.get("data", [])
            kwargs["data"] = json.loads(d) if isinstance(d, str) else d
            kwargs["bins"] = args.bins or input_data.get("bins", 20)
            kwargs["output"] = args.output or input_data.get("output")
        elif op == "scatter":
            kwargs["x"] = json.loads(args.x) if isinstance(args.x, str) else input_data.get("x", [])
            kwargs["y"] = json.loads(args.y) if isinstance(args.y, str) else input_data.get("y", [])
            kwargs["output"] = args.output or input_data.get("output")
        elif op == "comparison":
            kwargs["exprs"] = json.loads(args.exprs) if args.exprs else input_data.get("exprs", [])
            kwargs["var"] = args.var or input_data.get("var", "x")
            rng = args.range or input_data.get("range", [-10, 10])
            kwargs["range_"] = json.loads(rng) if isinstance(rng, str) else rng
            kwargs["output"] = args.output or input_data.get("output")
        elif op == "polar":
            kwargs["expr_r"] = args.expr or input_data.get("expr", "")
            kwargs["var_theta"] = args.var or input_data.get("var", "theta")
            kwargs["output"] = args.output or input_data.get("output")
        elif op == "ascii":
            kwargs["data"] = args.data or input_data.get("data")
            kwargs["expr"] = args.expr or input_data.get("expr")
            kwargs["range_"] = json.loads(args.range) if isinstance(args.range, str) else input_data.get("range")
            kwargs["width"] = args.width or input_data.get("width", 60)

        result = OPERATIONS[op](**kwargs)
        output = {"ok": True, "op": op, **result}
        out_str = json.dumps(output, ensure_ascii=False, indent=None if args.compact else 2, default=str)
        if "ascii_chart" in result and result["ascii_chart"]:
            print(result["ascii_chart"])
        else:
            print(out_str)
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
