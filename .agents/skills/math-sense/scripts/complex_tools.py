#!/usr/bin/env python3
"""
complex_tools.py — 复数运算与几何解释工具

用法:
    python complex_tools.py --op "rect_to_polar" --a 3 --b 4
    python complex_tools.py --op "rotate" --a 1 --b 0 --angle 90
    python complex_tools.py --op "roots" --a 1 --b 0 --n 3
    python complex_tools.py --op "de_moivre" --r 1 --theta 45 --n 2
    python complex_tools.py --op "arithmetic" --a "3+4j" --b "1-2j" --func "mul"

支持的操作:
    arithmetic, modulus, argument, conjugate,
    rect_to_polar, polar_to_rect, rotate,
    de_moivre, roots, visualize
"""

import sys, json, math, cmath, argparse


def _parse_complex(s):
    """解析复数：'3+4j', '(3,4)', [3,4], {'re':3,'im':4}"""
    if isinstance(s, complex):
        return s
    if isinstance(s, (list, tuple)) and len(s) >= 2:
        return complex(s[0], s[1])
    if isinstance(s, dict):
        return complex(s.get("re", 0), s.get("im", 0))
    if isinstance(s, str):
        s = s.strip()
        if s.startswith("(") and s.endswith(")"):
            parts = s[1:-1].split(",")
            return complex(float(parts[0]), float(parts[1]))
        if s.startswith("[") and s.endswith("]"):
            parts = json.loads(s)
            return complex(parts[0], parts[1])
        return complex(s.replace("i", "j").replace(" ", ""))
    return complex(s)


def _to_json(z):
    """复数→JSON友好输出"""
    return {
        "re": z.real,
        "im": z.imag,
        "string": f"{z.real:.6g}{z.imag:+6g}j",
        "modulus": abs(z),
        "argument_rad": cmath.phase(z),
        "argument_deg": math.degrees(cmath.phase(z)),
    }


def _geometric_multiply(z1, z2):
    """复数乘法的几何解释"""
    r1, t1 = abs(z1), cmath.phase(z1)
    r2, t2 = abs(z2), cmath.phase(z2)
    return (
        f"复数乘法的几何意义：模长相乘（{r1:.4g}×{r2:.4g}={r1 * r2:.4g}），"
        f"辐角相加（{math.degrees(t1):.1f}°+{math.degrees(t2):.1f}°={math.degrees(t1 + t2):.1f}°）。"
        f"在复平面上，乘以复数相当于伸缩+旋转。"
    )


def _geometric_divide(z1, z2):
    """复数除法的几何解释"""
    r1, t1 = abs(z1), cmath.phase(z1)
    r2, t2 = abs(z2), cmath.phase(z2)
    return (
        f"复数除法的几何意义：模长相除（{r1:.4g}÷{r2:.4g}={r1 / r2:.4g}），"
        f"辐角相减（{math.degrees(t1):.1f}°-{math.degrees(t2):.1f}°={math.degrees(t1 - t2):.1f}°）。"
    )


# ====================== 操作实现 ======================


def op_arithmetic(a_str, b_str, func):
    """基本运算"""
    a = _parse_complex(a_str)
    b = _parse_complex(b_str)
    ops = {
        "add": ("+", a + b, "加法对应复平面上向量的平行四边形法则"),
        "sub": ("-", a - b, "减法等于加上相反数，几何上对应向量差"),
        "mul": ("×", a * b, _geometric_multiply(a, b)),
        "div": ("÷", a / b if b != 0 else complex(float("nan")), _geometric_divide(a, b) if b != 0 else "除数不能为零"),
    }
    if func not in ops:
        return {"error": f"不支持: {func}，可用: add/sub/mul/div"}
    op_symbol, result, geometric = ops[func]
    return {
        "op": func,
        "symbol": op_symbol,
        "a": _to_json(a),
        "b": _to_json(b),
        "result": _to_json(result),
        "geometric": geometric,
    }


def op_modulus(a_str):
    z = _parse_complex(a_str)
    r = abs(z)
    return {
        "z": _to_json(z),
        "modulus": r,
        "modulus_squared": r * r,
        "geometric": f"模 |z|={r:.6g} 表示复平面上点到原点的距离（毕达哥拉斯定理: sqrt({z.real:.4g}²+{z.imag:.4g}²)）。",
    }


def op_argument(a_str):
    z = _parse_complex(a_str)
    arg_rad = cmath.phase(z)
    arg_deg = math.degrees(arg_rad)
    # 分数π表示
    pi_ratio = arg_rad / math.pi
    pi_str = ""
    for num, den in [(1, 6), (1, 4), (1, 3), (1, 2), (2, 3), (3, 4), (5, 6), (1, 1)]:
        if abs(pi_ratio - num / den) < 0.001:
            pi_str = f" = {num}π/{den}" if num > 1 else (f" = π/{den}" if den > 1 else " = π")
            break
    if not pi_str and abs(pi_ratio + 1) < 0.001:
        pi_str = " = -π"
    return {
        "z": _to_json(z),
        "argument_rad": arg_rad,
        "argument_deg": arg_deg,
        "pi_ratio": f"{arg_rad / math.pi:.4g}π{pi_str}",
        "geometric": f"辐角 θ={arg_deg:.2f}°({arg_rad / math.pi:.4g}π) 是复平面上从正实轴逆时针旋转到该点的角度。",
    }


def op_conjugate(a_str):
    z = _parse_complex(a_str)
    conj = z.conjugate()
    return {
        "z": _to_json(z),
        "conjugate": _to_json(conj),
        "geometric": f"共轭复数将虚部取反，几何上对应关于实轴的镜像反射。z·z̄ = |z|² = {abs(z) ** 2:.4g}",
    }


def op_rect_to_polar(a, b):
    """直角坐标→极坐标"""
    z = complex(a, b)
    r, theta = abs(z), cmath.phase(z)
    return {
        "rectangular": {"x": a, "y": b, "string": f"{a}{b:+}j"},
        "polar": {
            "r": r,
            "theta_rad": theta,
            "theta_deg": math.degrees(theta),
            "string": f"{r:.6g}·e^(i·{math.degrees(theta):.2f}°)",
            "latex": f"{r:.4g}e^{{i{math.degrees(theta):.1f}^\\circ}}",
        },
        "geometric": f"点({a},{b})到原点距离 r={r:.4g}，与正实轴夹角 θ={math.degrees(theta):.1f}°。",
    }


def op_polar_to_rect(r, theta_deg):
    """极坐标→直角坐标"""
    theta = math.radians(theta_deg)
    x = r * math.cos(theta)
    y = r * math.sin(theta)
    z = complex(x, y)
    return {
        "polar": {"r": r, "theta_deg": theta_deg},
        "rectangular": {"x": x, "y": y, "string": f"{x:.6g}{y:+6g}j"},
        "z": _to_json(z),
        "geometric": f"模长 r={r}，辐角 θ={theta_deg}° 唯一确定了复平面上的点 ({x:.4g}, {y:.4g})。",
    }


def op_rotate(a, b, angle_deg):
    """复数旋转：乘以 e^(iθ)"""
    z = complex(a, b)
    rot = cmath.exp(1j * math.radians(angle_deg))
    z_rot = z * rot
    return {
        "original": _to_json(z),
        "rotation_angle_deg": angle_deg,
        "rotation_factor": _to_json(rot),
        "rotated": _to_json(z_rot),
        "geometric": f"将点 ({a},{b}) 绕原点逆时针旋转 {angle_deg}° 后到达 ({z_rot.real:.4g}, {z_rot.imag:.4g})。"
        f"这相当于乘以 e^(i·{angle_deg}°) = cos({angle_deg}°)+i·sin({angle_deg}°)。",
    }


def op_de_moivre(r, theta_deg, n):
    """棣莫弗定理：(r(cosθ+isinθ))^n = r^n (cos(nθ)+i sin(nθ))"""
    theta = math.radians(theta_deg)
    z = r * (math.cos(theta) + 1j * math.sin(theta))
    # 公式计算
    r_n = r**n
    theta_n = n * theta
    zn_formula = r_n * (math.cos(theta_n) + 1j * math.sin(theta_n))
    # 直接计算验证
    zn_direct = z**n
    err = abs(zn_formula - zn_direct)
    return {
        "z_polar": {"r": r, "theta_deg": theta_deg, "string": f"{r}·(cos{theta_deg}°+i·sin{theta_deg}°)"},
        "n": n,
        "result_polar": {
            "r": r_n,
            "theta_deg": math.degrees(theta_n) % 360,
            "string": f"{r_n:.6g}·(cos{math.degrees(theta_n) % 360:.1f}°+i·sin{math.degrees(theta_n) % 360:.1f}°)",
        },
        "result_rectangular": _to_json(zn_formula),
        "direct_verify": _to_json(zn_direct),
        "error": float(err),
        "geometric": (
            f"棣莫弗定理：将复数自乘 {n} 次，模长变为原来的 {n} 次方（{r}^{n}={r_n:.4g}），"
            f"辐角变为原来的 {n} 倍（{theta_deg}°×{n}={math.degrees(theta_n) % 360:.1f}°）。"
            f"在复平面上，这相当于将点沿圆周均匀'展开'{n}倍角度。"
        ),
    }


def op_roots(a, b, n):
    """n次方根：z^(1/n) 的 n 个根"""
    z = complex(a, b)
    r = abs(z)
    theta = cmath.phase(z)
    roots = []
    for k in range(n):
        root_r = r ** (1 / n)
        root_theta = (theta + 2 * math.pi * k) / n
        root = root_r * (math.cos(root_theta) + 1j * math.sin(root_theta))
        roots.append(
            {
                "k": k,
                "z": _to_json(root),
                "theta_deg": math.degrees(root_theta) % 360,
                "polar": f"{root_r:.6g}·e^(i·{math.degrees(root_theta) % 360:.1f}°)",
            }
        )
    return {
        "z": _to_json(z),
        "n": n,
        "roots": roots,
        "geometric": (
            f"复数 {z.real:.4g}{z.imag:+4g}j 的 {n} 次方根均匀分布在半径为 {r ** (1 / n):.4g} 的圆上，"
            f"相邻两根夹角为 360°/{n}={360 / n:.0f}°。这揭示了代数基本定理：n次多项式恰有n个复根。"
        ),
    }


def op_visualize(a, b):
    """复平面上的可视化文字描述"""
    z = complex(a, b)
    r, theta = abs(z), cmath.phase(z)
    theta_deg = math.degrees(theta)
    quadrant = (
        1
        if z.real >= 0 and z.imag >= 0
        else (2 if z.real < 0 and z.imag >= 0 else (3 if z.real < 0 and z.imag < 0 else 4))
    )
    quad_names = {1: "第一象限（右上）", 2: "第二象限（左上）", 3: "第三象限（左下）", 4: "第四象限（右下）"}

    # 与单位圆的关系
    unit_circle = (
        "在单位圆上" if abs(r - 1) < 0.001 else (f"在单位圆{'外' if r > 1 else '内'}（距离圆心 {abs(r - 1):.4g}）")
    )

    # 特殊角检测
    special_angles = {
        0: "正实轴",
        90: "正虚轴",
        180: "负实轴",
        270: "负虚轴",
        45: "一三象限对角线",
        135: "二四象限对角线",
    }
    angle_desc = ""
    for ang, name in special_angles.items():
        if abs(theta_deg - ang) < 0.5 or abs(theta_deg - ang - 360) < 0.5:
            angle_desc = f"，恰好落在{name}上"
            break

    # 共轭
    conj = z.conjugate()

    parts = [
        f"复数 z = {z.real:.4g}{z.imag:+4g}j 位于复平面的{quad_names.get(quadrant, '')}。",
        f"它到原点的距离为 |z| = {r:.4g}，{unit_circle}。",
        f"从正实轴逆时针旋转 {theta_deg:.1f}° 到达该点{angle_desc}。",
        f"它的共轭 z̄ = {conj.real:.4g}{conj.imag:+4g}j 关于实轴对称。",
        f"乘以 e^(iφ) 相当于绕原点旋转 φ 角度；乘以实数 k 相当于径向伸缩 k 倍。",
    ]

    return {
        "z": _to_json(z),
        "quadrant": quadrant,
        "visualization": "".join(parts),
        "polar_form": f"{r:.4g}·(cos{theta_deg:.1f}°+i·sin{theta_deg:.1f}°)",
        "exponential_form": f"{r:.4g}·e^(i·{theta_deg:.1f}°)",
    }


OPERATIONS = {
    "arithmetic": op_arithmetic,
    "modulus": op_modulus,
    "argument": op_argument,
    "conjugate": op_conjugate,
    "rect_to_polar": op_rect_to_polar,
    "polar_to_rect": op_polar_to_rect,
    "rotate": op_rotate,
    "de_moivre": op_de_moivre,
    "roots": op_roots,
    "visualize": op_visualize,
}


def main():
    parser = argparse.ArgumentParser(
        description="复数运算与几何解释工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python complex_tools.py --op "rect_to_polar" --a 3 --b 4
  python complex_tools.py --op "rotate" --a 1 --b 0 --angle 90
  python complex_tools.py --op "roots" --a 1 --b 0 --n 3
  python complex_tools.py --op "visualize" --a -2 --b 3
  python complex_tools.py --op "arithmetic" --a "3+4j" --b "1-2j" --func "mul"
""",
    )
    parser.add_argument("--op", "-o", help="操作名称")
    parser.add_argument("--a", type=float, help="实部 或 极径")
    parser.add_argument("--b", type=float, default=0, help="虚部")
    parser.add_argument("--a-str", help="复数字符串 (如 3+4j)")
    parser.add_argument("--b-str", help="复数字符串")
    parser.add_argument("--func", default="add", help="运算: add/sub/mul/div")
    parser.add_argument("--r", type=float, help="极径 (polar)")
    parser.add_argument("--theta", type=float, help="辐角（度）")
    parser.add_argument("--angle", type=float, help="旋转角度（度）")
    parser.add_argument("--n", type=int, default=2, help="幂次/方根次数")
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
        if op == "arithmetic":
            kwargs["a_str"] = args.a_str or input_data.get("a", "0")
            kwargs["b_str"] = args.b_str or input_data.get("b", "0")
            kwargs["func"] = args.func or input_data.get("func", "add")
        elif op in ("modulus", "argument", "conjugate"):
            kwargs["a_str"] = args.a_str or input_data.get("a", "0")
        elif op == "rect_to_polar":
            kwargs["a"] = args.a if args.a is not None else input_data.get("a", 0)
            kwargs["b"] = args.b if args.b is not None else input_data.get("b", 0)
        elif op == "polar_to_rect":
            kwargs["r"] = args.r or input_data.get("r", 1)
            kwargs["theta_deg"] = args.theta or input_data.get("theta", 0)
        elif op == "rotate":
            kwargs["a"] = args.a if args.a is not None else input_data.get("a", 1)
            kwargs["b"] = args.b if args.b is not None else input_data.get("b", 0)
            kwargs["angle_deg"] = args.angle or input_data.get("angle", 90)
        elif op == "de_moivre":
            kwargs["r"] = args.r or input_data.get("r", 1)
            kwargs["theta_deg"] = args.theta or input_data.get("theta", 0)
            kwargs["n"] = args.n or input_data.get("n", 2)
        elif op == "roots":
            kwargs["a"] = args.a if args.a is not None else input_data.get("a", 1)
            kwargs["b"] = args.b if args.b is not None else input_data.get("b", 0)
            kwargs["n"] = args.n or input_data.get("n", 2)
        elif op == "visualize":
            kwargs["a"] = args.a if args.a is not None else input_data.get("a", 0)
            kwargs["b"] = args.b if args.b is not None else input_data.get("b", 0)

        result = OPERATIONS[op](**kwargs)
        output = {"ok": True, "op": op, **result}
        print(json.dumps(output, ensure_ascii=False, indent=None if args.compact else 2, default=str))
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
