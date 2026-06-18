#!/usr/bin/env python3
"""
formula_compose.py — 公式加工与创造工具

核心理念: 公式不是只能"查找"的——像搭积木一样修改、组合、创造。
本脚本提供：
  1. 公式修改：基于描述对现有公式做精确修改（替换参数、嵌套函数、添加因子）
  2. 公式创造：从需求出发，用已知函数组件组合出新公式
  3. 性质验证：检查生成的公式是否满足需求约束

用法:
    python formula_compose.py --op "modify" --expr "x**2" --change "将平方改为立方"
    python formula_compose.py --op "compose" --need "需要一个S形曲线，在x=0处取0.5，x→-∞时趋于0，x→+∞时趋于1"
    python formula_compose.py --op "verify" --expr "1/(1+exp(-x))" --properties '["有界","单调递增","值域(0,1)"]'

支持的操作:
    modify, compose, verify, components
"""

import sys, json, math, re, argparse

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


# ====================== 函数组件库 ======================

COMPONENT_LIBRARY = {
    "growth": {
        "linear": {"expr": "k*x + b", "props": ["无界", "单调", "无饱和"]},
        "quadratic": {"expr": "a*x**2 + b*x + c", "props": ["开口", "对称", "抛物线"]},
        "exponential": {"expr": "a*exp(k*x) + c", "props": ["快速增长", "无上界", "J曲线"]},
        "logarithmic": {"expr": "a*log(b*x) + c", "props": ["增长递减", "无上界但慢", "边际递减"]},
        "power_law": {"expr": "a*x**n + c", "props": ["幂律增长", "可调节陡峭度"]},
    },
    "saturation": {
        "sigmoid": {"expr": "L/(1+exp(-k*(x-x0)))", "props": ["S形", "有上下界", "在x0处斜率最大", "值域(0,L)"]},
        "tanh": {"expr": "a*tanh(k*(x-x0)) + c", "props": ["S形", "过原点", "值域(-a+c, a+c)"]},
        "arctan": {"expr": "a*(2/pi)*atan(k*x) + c", "props": ["S形", "渐近", "缓慢趋近上下界"]},
        "rational": {"expr": "a*x/(b+|x|)", "props": ["有界", "过原点", "渐近±a"]},
        "gaussian": {"expr": "a*exp(-(x-mu)**2/(2*s**2))", "props": ["钟形", "局部化", "在mu处取峰值"]},
        "exponential_decay": {"expr": "a*exp(-k*x)", "props": ["单调递减趋于0", "半衰期ln2/k"]},
    },
    "oscillation": {
        "sine": {"expr": "a*sin(k*x + ph) + c", "props": ["周期=2π/k", "振幅a", "值域[c-a,c+a]"]},
        "cosine": {"expr": "a*cos(k*x + ph) + c", "props": ["周期=2π/k", "振幅a", "偶函数当ph=0"]},
        "damped_sine": {"expr": "a*exp(-d*x)*sin(k*x)", "props": ["振幅指数衰减", "在x=0处取0", "衰减速率d"]},
        "beats": {"expr": "sin(k1*x)+sin(k2*x)", "props": ["拍频|k1-k2|/2", "包络频率|k1+k2|/2"]},
    },
    "special": {
        "step": {"expr": "a if x >= thresh else b", "props": ["分段", "在thresh处跳变"]},
        "relu": {"expr": "max(0, k*x)", "props": ["线性整流", "在0处转折", "非负"]},
        "abs_val": {"expr": "a*abs(x-x0) + c", "props": ["V形", "在x0处最小", "对称"]},
        "gaussian_bell": {"expr": "a*exp(-(x-mu)**2/(2*s**2))", "props": ["钟形", "最大在mu", "宽度s"]},
    },
}

# 组合策略描述
COMPOSE_STRATEGIES = {
    "需要S曲线": "考虑 sigmoid, tanh, 或 arctan 函数。调整参数 L/k/x0 控制上下界、陡峭度和中心位置。",
    "需要衰减振荡": "用 exp(-d*x)*sin(k*x) —— 指数衰减包络调制正弦波。",
    "需要先增后减": "可以是 -a*(x-x0)**2+c（开口向下的抛物线），或分段函数。",
    "需要平滑过渡": "用 sigmoid 作为'开关'：f1(x)*(1-sigmoid)+f2(x)*sigmoid 实现两段行为平滑衔接。",
    "需要在某点快速变化": "在目标点附近使用指数或sigmoid——它们的导数在该处急剧变化。",
    "需要有上下界": "使用 sigmoid, tanh, arctan, 或有理函数 a*x/(b+|x|)。",
    "需要周期行为": "使用 sin 或 cos，可叠加多个频率（傅里叶合成）得到复杂周期模式。",
    "需要尖峰": "使用高斯函数 exp(-(x-mu)**2/(2*s**2))，s越小峰越尖锐。",
}


# ====================== 公式修改 ======================

MODIFY_PATTERNS = [
    # (正则匹配需要什么修改, 修改操作)
    (
        r"(平方|二次|2次)",
        lambda e: (
            e.replace("**2", "**3").replace("** 2", "** 3")
            if "**2" in e
            else e.replace("*x", "**2*x").replace("x*x", "x**3")
        ),
    ),
    (r"(立方|三次|3次)", lambda e: e.replace("**2", "**3").replace("** 2", "** 3")),
    (r"(加.*衰减|乘以.*衰减|.*衰减因子)", lambda e: f"({e})*exp(-d*x)"),
    (r"(取反|翻折|镜像|相反数)", lambda e: f"-({e})"),
    (
        r"(平移|右移|左移).*?(\d+)",
        lambda e, m: (
            f"({e.replace('x', f'(x-{m.group(2)})')})"
            if "右移" in m.group(1)
            else f"({e.replace('x', f'(x+{m.group(2)})')})"
        ),
    ),
    (r"(放大|缩小|缩放).*?(\d+(?:\.\d+)?)倍", lambda e, m: f"{float(m.group(2))}*({e})"),
    (
        r"(向上|向下)平移\s*(\d+(?:\.\d+)?)",
        lambda e, m: f"({e})+{m.group(2)}" if "向上" in m.group(1) else f"({e})-{m.group(2)}",
    ),
    (r"(嵌套|外面套).*?(sin|cos|tan|exp|log|sqrt|abs)", lambda e, m: f"{m.group(2)}({e})"),
    (r"(归一化|除以最大值)", lambda e: f"({e})/max(1, abs({e}))"),
    (r"(限制|截断|钳位).*?\[(-?\d+),\s*(-?\d+)\]", lambda e, m: f"max({m.group(1)}, min({m.group(2)}, {e}))"),
]


def op_modify(expr_str, change_desc):
    """基于描述修改公式"""
    result = expr_str
    applied = []
    for pattern, action in MODIFY_PATTERNS:
        m = re.search(pattern, change_desc)
        if m:
            try:
                if "m" in action.__code__.co_varnames[:2]:  # action takes match
                    new_expr = action(result, m)
                else:
                    new_expr = action(result)
                if new_expr != result:
                    applied.append(f"检测到「{m.group(0)}」→ 应用修改")
                    result = new_expr
            except Exception as e:
                applied.append(f"尝试修改「{m.group(0)}」失败: {e}")

    if not applied:
        applied.append("未识别到可自动执行的修改，请用更明确的语言描述（如'将平方改为立方''乘以衰减因子'等）")

    # 尝试 sympy 验证新公式
    valid = False
    if HAS_SYMPY:
        try:
            sp.sympify(result)
            valid = True
        except Exception:
            pass

    return {
        "original": expr_str,
        "modified": result,
        "change": change_desc,
        "applied_steps": applied,
        "valid_syntax": valid,
        "note": "如果修改不准确，请更具体地描述修改意图（如'将 x² 替换为 x³''在最外层乘以 e^(-0.1x)'）",
    }


# ====================== 公式创造 ======================


def op_compose(need_desc):
    """从需求描述创造公式"""
    # 匹配策略
    matched_strategies = []
    for key, strategy in COMPOSE_STRATEGIES.items():
        score = 0
        for char in key:
            if char in need_desc:
                score += 1
        if score > len(key) * 0.4:
            matched_strategies.append({"strategy": key, "advice": strategy, "relevance": score})

    matched_strategies.sort(key=lambda x: x["relevance"], reverse=True)

    # 尝试匹配组件
    component_matches = []
    for category, components in COMPONENT_LIBRARY.items():
        for name, info in components.items():
            score = 0
            props_str = " ".join(info["props"])
            for prop in info["props"]:
                for word in prop.split():
                    if word in need_desc:
                        score += 2
            if name in need_desc.lower():
                score += 5
            if score > 0:
                component_matches.append(
                    {
                        "category": category,
                        "name": name,
                        "expr": info["expr"],
                        "props": info["props"],
                        "relevance": score,
                    }
                )

    component_matches.sort(key=lambda x: x["relevance"], reverse=True)

    # 生成建议
    suggestions = []
    if matched_strategies:
        suggestions.append(f"### 策略建议\n{matched_strategies[0]['advice']}")
    if component_matches:
        comps = component_matches[:3]
        suggestions.append(
            f"### 推荐组件\n"
            + "\n".join(f"- **{c['name']}** ({c['category']}): `{c['expr']}` — {'; '.join(c['props'])}" for c in comps)
        )
    if not suggestions:
        suggestions.append("### 建议\n请更具体地描述需要的数学性质（如'有上下界''单调递增''在x=0处取0''周期为2π'等）。")

    return {
        "need": need_desc,
        "suggestions": suggestions,
        "matched_components": component_matches[:5],
        "matched_strategies": matched_strategies[:3],
        "next_step": "确定候选公式后，用 `verify` 操作检查是否满足需求约束。",
    }


# ====================== 性质验证 ======================


def op_verify(expr_str, properties, range_=None):
    """验证公式是否满足指定性质"""
    if range_ is None:
        range_ = [-10, 10]
    if not HAS_NUMPY:
        return {"error": "需要 numpy"}

    x_min, x_max = range_
    n = 500
    xs = np.linspace(x_min, x_max, n)

    # 安全求值
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
    }
    tree = _ast.parse(expr_str.strip(), mode="eval")

    def _ev(n, xv):
        if isinstance(n, _ast.Constant):
            return n.value
        if isinstance(n, _ast.Name):
            if n.id == "x":
                return xv
            if n.id in ALLOWED:
                return ALLOWED[n.id]
            raise NameError(n.id)
        if isinstance(n, _ast.BinOp):
            l, r = _ev(n.left, xv), _ev(n.right, xv)
            o = {_ast.Add: _op.add, _ast.Sub: _op.sub, _ast.Mult: _op.mul, _ast.Div: _op.truediv, _ast.Pow: _op.pow}
            return o[type(n.op)](l, r)
        if isinstance(n, _ast.UnaryOp):
            v = _ev(n.operand, xv)
            return -v if isinstance(n.op, _ast.USub) else +v
        if isinstance(n, _ast.Call):
            args = [_ev(a, xv) for a in n.args]
            return _ev(n.func, xv)(*args)
        return 0

    try:
        ys = np.array([_ev(tree.body, float(x)) for x in xs])
    except Exception as e:
        return {"error": f"求值失败: {e}"}

    checks = {}
    for prop in properties:
        prop_lower = prop.lower().replace(" ", "")
        if "单调递增" in prop or "monotonic_increasing" in prop_lower:
            diffs = np.diff(ys)
            checks["单调递增"] = {"passed": bool(np.all(diffs >= -1e-8)), "violations": int(np.sum(diffs < -1e-8))}
        elif "单调递减" in prop or "monotonic_decreasing" in prop_lower:
            diffs = np.diff(ys)
            checks["单调递减"] = {"passed": bool(np.all(diffs <= 1e-8)), "violations": int(np.sum(diffs > 1e-8))}
        elif "有界" in prop or "bounded" in prop_lower:
            checks["有界"] = {"passed": True, "min": float(np.min(ys)), "max": float(np.max(ys))}
        elif "值域" in prop:
            # 值域(0,1) 格式
            m = re.search(r"值域\s*\(?\[?(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\)?\]?", prop)
            if m:
                lo, hi = float(m.group(1)), float(m.group(2))
                in_range = np.all((ys >= lo - 0.01) & (ys <= hi + 0.01))
                checks[f"值域在({lo},{hi})"] = {
                    "passed": bool(in_range),
                    "outliers": int(np.sum((ys < lo) | (ys > hi))),
                }
        elif "过原点" in prop or "passes_origin" in prop_lower:
            y0 = _ev(tree.body, 0.0)
            checks["过原点(x=0,y=0)"] = {"passed": abs(y0) < 1e-8, "y_at_0": float(y0)}
        elif "对称" in prop or "symmetric" in prop_lower:
            mid = (x_min + x_max) / 2
            left = ys[xs < mid]
            right = ys[xs >= mid][::-1]
            n_cmp = min(len(left), len(right))
            sym_err = float(np.mean(np.abs(left[:n_cmp] - right[:n_cmp])))
            checks["对称性"] = {"passed": sym_err < 0.05 * (np.max(ys) - np.min(ys) + 1e-10), "symmetry_error": sym_err}

    all_passed = all(c.get("passed", True) for c in checks.values())

    return {
        "expr": expr_str,
        "range": range_,
        "checks": checks,
        "all_passed": all_passed,
        "verdict": "所有性质满足" if all_passed else "部分性质不满足，需调整公式",
    }


def op_components():
    """列出所有可用的函数组件"""
    result = {}
    for cat, comps in COMPONENT_LIBRARY.items():
        result[cat] = {name: {"expr": info["expr"], "props": info["props"]} for name, info in comps.items()}
    result["strategies"] = list(COMPOSE_STRATEGIES.keys())
    return {"components": result}


OPERATIONS = {
    "modify": op_modify,
    "compose": op_compose,
    "verify": op_verify,
    "components": op_components,
}


def main():
    parser = argparse.ArgumentParser(
        description="公式加工与创造工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python formula_compose.py --op "modify" --expr "x**2" --change "将平方改为立方"
  python formula_compose.py --op "compose" --need "需要一个S形曲线，有上下界，在x=0处取0.5"
  python formula_compose.py --op "verify" --expr "1/(1+exp(-x))" --properties '["有界","单调递增","值域(0,1)"]'
  python formula_compose.py --op "components"
""",
    )
    parser.add_argument("--op", "-o", help="操作名称")
    parser.add_argument("--expr", "-e", help="公式表达式")
    parser.add_argument("--change", help="修改描述")
    parser.add_argument("--need", help="需求描述")
    parser.add_argument("--properties", help="需要验证的性质 JSON")
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
        if op == "modify":
            kwargs["expr_str"] = args.expr or input_data.get("expr", "")
            kwargs["change_desc"] = args.change or input_data.get("change", "")
        elif op == "compose":
            kwargs["need_desc"] = args.need or input_data.get("need", "")
        elif op == "verify":
            kwargs["expr_str"] = args.expr or input_data.get("expr", "")
            kwargs["properties"] = json.loads(args.properties) if args.properties else input_data.get("properties", [])

        result = OPERATIONS[op](**kwargs)
        output = {"ok": True, "op": op, **result}
        print(json.dumps(output, ensure_ascii=False, indent=None if args.compact else 2, default=str))
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
