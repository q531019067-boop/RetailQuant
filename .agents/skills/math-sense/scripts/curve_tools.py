#!/usr/bin/env python3
"""
curve_tools.py — 曲线工具集（含叙事描述引擎）

用法:
    python curve_tools.py --op "sample" --expr "sin(x)" --range "[0,6.28]" --n 100
    python curve_tools.py --op "narrate" --expr "x**3 - 3*x" --range "[-2,2]"
    python curve_tools.py --op "multi_scale" --expr "exp(-x**2)*sin(5*x)" --range "[0,3]"
    python curve_tools.py --op "sample_adaptive" --expr "sin(1/x)" --range "[0.01,1]" --n 200

支持的操作:
    sample, sample_adaptive, fit_poly, fit_exp, fit_log, fit_linear, fit_auto,
    interp_linear, interp_cubic, bezier_eval,
    describe, narrate, multi_scale
"""

import sys, json, math, argparse, re

try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    from scipy import interpolate, optimize

    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


def _to_points(data):
    if isinstance(data, str):
        data = json.loads(data)
    return [(p[0], p[1]) for p in data]


def _eval_simple(expr_str, vars_dict):
    """安全表达式求值（降级方案）"""
    import ast as _ast
    import math as _math
    import operator as _op

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

    def _eval(node):
        if isinstance(node, _ast.Constant):
            return node.value
        if isinstance(node, _ast.Name):
            if node.id in vars_dict:
                return vars_dict[node.id]
            if node.id in ALLOWED:
                return ALLOWED[node.id]
            raise NameError(node.id)
        if isinstance(node, _ast.BinOp):
            l, r = _eval(node.left), _eval(node.right)
            ops = {_ast.Add: _op.add, _ast.Sub: _op.sub, _ast.Mult: _op.mul, _ast.Div: _op.truediv, _ast.Pow: _op.pow}
            return ops[type(node.op)](l, r)
        if isinstance(node, _ast.UnaryOp):
            v = _eval(node.operand)
            return -v if isinstance(node.op, _ast.USub) else +v
        if isinstance(node, _ast.Call):
            fn = _eval(node.func)
            return fn(*[_eval(a) for a in node.args])
        raise ValueError(type(node).__name__)

    return _eval(tree.body)


# ====================== 采样 ======================


def op_sample(expr, var, range_, n):
    x_min, x_max = range_
    xs, ys = [], []
    for i in range(n):
        x = x_min + (x_max - x_min) * i / (n - 1) if n > 1 else x_min
        try:
            y = _eval_simple(expr, {var: x})
        except Exception as e:
            return {"error": f"在 x={x} 求值失败: {e}"}
        xs.append(x)
        ys.append(y)
    return {
        "points": [[xs[i], ys[i]] for i in range(n)],
        "n": n,
        "range": [x_min, x_max],
        "y_min": min(ys),
        "y_max": max(ys),
    }


def op_sample_adaptive(expr, var, range_, n_base=50, max_n=500):
    """自适应采样：在曲率大的地方加密采样点"""
    if not HAS_NUMPY:
        return op_sample(expr, var, range_, n_base)
    x_min, x_max = range_
    # 第一遍：均匀粗采样
    coarse_n = n_base
    coarse = op_sample(expr, var, range_, coarse_n)
    if "error" in coarse:
        return coarse
    points = coarse["points"]
    # 计算每个点的曲率估计（二阶差分）
    xs = np.array([p[0] for p in points])
    ys = np.array([p[1] for p in points])
    if len(xs) < 3:
        return coarse
    d2 = np.abs(np.gradient(np.gradient(ys, xs), xs))
    d2 = np.nan_to_num(d2, 0)
    # 归一化曲率为采样密度权重
    if d2.max() > 0:
        weights = d2 / d2.sum()
    else:
        weights = np.ones(len(xs)) / len(xs)
    # 第二遍：按权重加密
    remain = max_n - coarse_n
    if remain <= 0:
        return coarse
    extra_counts = np.round(weights * remain).astype(int)
    extra_counts = np.clip(extra_counts, 0, None)
    # 修正总数
    while extra_counts.sum() < remain:
        idx = np.argmax(weights)
        extra_counts[idx] += 1
    while extra_counts.sum() > remain:
        idx = np.argmax(extra_counts)
        if extra_counts[idx] > 0:
            extra_counts[idx] -= 1
    # 在每个区间插入额外点
    all_xs, all_ys = [], []
    for i in range(len(xs) - 1):
        all_xs.append(float(xs[i]))
        all_ys.append(float(ys[i]))
        n_extra = int(extra_counts[i])
        for j in range(1, n_extra + 1):
            t = j / (n_extra + 1)
            x_new = float(xs[i]) + t * (float(xs[i + 1]) - float(xs[i]))
            try:
                y_new = _eval_simple(expr, {var: x_new})
                all_xs.append(x_new)
                all_ys.append(y_new)
            except Exception:
                pass
    all_xs.append(float(xs[-1]))
    all_ys.append(float(ys[-1]))
    all_points = [[all_xs[i], all_ys[i]] for i in range(len(all_xs))]
    return {
        "points": all_points,
        "n": len(all_points),
        "range": [x_min, x_max],
        "y_min": float(min(all_ys)),
        "y_max": float(max(all_ys)),
        "adaptive": True,
        "base_n": coarse_n,
        "extra_n": int(extra_counts.sum()),
    }


# ====================== 拟合 ======================


def op_fit_poly(points, degree):
    if not HAS_NUMPY:
        return {"error": "需要 numpy"}
    pts = _to_points(points)
    xs = np.array([p[0] for p in pts])
    ys = np.array([p[1] for p in pts])
    coeffs = np.polyfit(xs, ys, degree)
    pred = np.polyval(coeffs, xs)
    ss_res = np.sum((ys - pred) ** 2)
    ss_tot = np.sum((ys - np.mean(ys)) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
    return {
        "coefficients": coeffs.tolist(),
        "polynomial": " + ".join(f"{c:.6g}*x^{len(coeffs) - 1 - i}" for i, c in enumerate(coeffs)),
        "r_squared": float(r2),
        "degree": degree,
        "residual_std": float(np.sqrt(ss_res / len(xs))) if len(xs) > degree + 1 else 0,
    }


def op_fit_linear(points):
    return op_fit_poly(points, 1)


def op_fit_exp(points):
    if not HAS_SCIPY:
        return {"error": "需要 scipy"}
    pts = _to_points(points)
    xs = np.array([p[0] for p in pts])
    ys = np.array([p[1] for p in pts])
    valid = ys > 0
    if not np.all(valid):
        return {"error": "指数拟合需要 y > 0"}
    log_ys = np.log(ys)
    coeffs = np.polyfit(xs, log_ys, 1)
    a, b = float(np.exp(coeffs[1])), float(coeffs[0])
    pred = a * np.exp(b * xs)
    ss_res = np.sum((ys - pred) ** 2)
    ss_tot = np.sum((ys - np.mean(ys)) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
    return {"formula": f"{a:.6g}*exp({b:.6g}*x)", "a": a, "b": b, "r_squared": float(r2)}


def op_fit_log(points):
    if not HAS_NUMPY:
        return {"error": "需要 numpy"}
    pts = _to_points(points)
    xs = np.array([p[0] for p in pts])
    ys = np.array([p[1] for p in pts])
    valid = xs > 0
    if not np.all(valid):
        return {"error": "对数拟合需要 x > 0"}
    log_xs = np.log(xs)
    coeffs = np.polyfit(log_xs, ys, 1)
    a, b = float(coeffs[0]), float(coeffs[1])
    pred = a * log_xs + b
    ss_res = np.sum((ys - pred) ** 2)
    ss_tot = np.sum((ys - np.mean(ys)) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
    return {"formula": f"{a:.6g}*ln(x)+{b:.6g}", "a": a, "b": b, "r_squared": float(r2)}


def op_fit_auto(points):
    pts = _to_points(points)
    models = {}
    for model_name, func in [
        ("linear", op_fit_linear),
        ("poly2", lambda p: op_fit_poly(p, 2)),
        ("poly3", lambda p: op_fit_poly(p, 3)),
        ("exp", op_fit_exp),
        ("log", op_fit_log),
    ]:
        try:
            models[model_name] = func(pts)
        except Exception:
            pass
    ranked = sorted([(k, v.get("r_squared", -999)) for k, v in models.items()], key=lambda x: x[1], reverse=True)
    return {"models": models, "ranked": [{"model": m, "r_squared": r} for m, r in ranked]}


# ====================== 插值 ======================


def op_interp_linear(points, x_query):
    pts = _to_points(points)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return (
        {"interpolated": float(np.interp(x_query, xs, ys)), "at_x": x_query} if HAS_NUMPY else {"error": "需要 numpy"}
    )


def op_interp_cubic(points, x_query=None, n_out=100):
    if not HAS_SCIPY:
        return {"error": "需要 scipy"}
    pts = _to_points(points)
    xs = np.array([p[0] for p in pts])
    ys = np.array([p[1] for p in pts])
    cs = interpolate.CubicSpline(xs, ys)
    if x_query is not None:
        return {"interpolated": float(cs(x_query)), "at_x": x_query}
    x_new = np.linspace(xs[0], xs[-1], n_out)
    y_new = cs(x_new)
    return {"points": [[float(x_new[i]), float(y_new[i])] for i in range(n_out)], "n": n_out}


# ====================== 贝塞尔 ======================


def op_bezier_eval(controls, n=50, t=None):
    pts = _to_points(controls)
    if t is not None:
        p = pts[:]
        for k in range(1, len(p)):
            for i in range(len(p) - k):
                p[i] = ((1 - t) * p[i][0] + t * p[i + 1][0], (1 - t) * p[i][1] + t * p[i + 1][1])
        return {"point": list(p[0]), "t": t}
    result = []
    for i in range(n):
        ti = i / (n - 1) if n > 1 else 0.5
        p = pts[:]
        for k in range(1, len(p)):
            for j in range(len(p) - k):
                p[j] = ((1 - ti) * p[j][0] + ti * p[j + 1][0], (1 - ti) * p[j][1] + ti * p[j + 1][1])
        result.append([p[0][0], p[0][1]])
    return {"points": result, "n": n, "degree": len(pts) - 1, "controls": pts}


# ====================== 结构化描述 ======================


def _describe_structured(xs, ys):
    """从采样点提取结构化特征"""
    n = len(xs)
    desc = {}
    # 值域
    desc["domain"] = [float(xs[0]), float(xs[-1])]
    desc["range"] = [float(np.min(ys)), float(np.max(ys))]
    # 单调性分段
    diffs = np.diff(ys)
    signs = np.sign(diffs)
    # 找单调区间
    segments = []
    seg_start = 0
    current_sign = signs[0] if len(signs) > 0 else 0
    for i in range(1, len(signs)):
        if signs[i] != current_sign and abs(signs[i]) > 0:
            segments.append(
                {
                    "x_range": [float(xs[seg_start]), float(xs[i])],
                    "type": "递增" if current_sign > 0 else ("递减" if current_sign < 0 else "平坦"),
                    "delta_y": float(ys[i] - ys[seg_start]),
                }
            )
            seg_start = i
            current_sign = signs[i]
    segments.append(
        {
            "x_range": [float(xs[seg_start]), float(xs[-1])],
            "type": "递增" if current_sign > 0 else ("递减" if current_sign < 0 else "平坦"),
            "delta_y": float(ys[-1] - ys[seg_start]),
        }
    )
    desc["monotone_segments"] = segments
    # 全局单调性
    if np.all(diffs >= -1e-10):
        desc["monotonicity"] = "全局单调递增"
    elif np.all(diffs <= 1e-10):
        desc["monotonicity"] = "全局单调递减"
    else:
        desc["monotonicity"] = (
            f"非单调（{sum(1 for s in segments if '增' in s['type'])}个递增段，{sum(1 for s in segments if '减' in s['type'])}个递减段）"
        )
    # 极值
    imax, imin = int(np.argmax(ys)), int(np.argmin(ys))
    desc["global_max"] = {"x": float(xs[imax]), "y": float(ys[imax]), "type": "全局最大值"}
    desc["global_min"] = {"x": float(xs[imin]), "y": float(ys[imin]), "type": "全局最小值"}
    # 局部极值
    local_extrema = []
    for i in range(1, n - 1):
        if ys[i] > ys[i - 1] and ys[i] > ys[i + 1]:
            local_extrema.append({"x": float(xs[i]), "y": float(ys[i]), "type": "局部极大值"})
        elif ys[i] < ys[i - 1] and ys[i] < ys[i + 1]:
            local_extrema.append({"x": float(xs[i]), "y": float(ys[i]), "type": "局部极小值"})
    desc["local_extrema"] = local_extrema[:10]
    # 拐点（二阶差分变号）
    if n > 4:
        d2 = np.diff(ys, 2)
        sign_d2 = np.sign(d2)
        inflection_idxs = np.where(np.diff(sign_d2) != 0)[0]
        desc["inflection_points"] = [{"x": float(xs[i + 1]), "y": float(ys[i + 1])} for i in inflection_idxs[:8]]
    # 凹凸性
    if n > 4:
        d2_total = np.sum(d2)
        if d2_total > 1e-8:
            desc["concavity"] = "整体凹向上（下凸）"
        elif d2_total < -1e-8:
            desc["concavity"] = "整体凹向下（上凸）"
        else:
            desc["concavity"] = "凹凸交替"
    # 对称性
    mid_x = (xs[0] + xs[-1]) / 2
    left = ys[xs < mid_x]
    right = ys[xs >= mid_x]
    if len(left) > 0 and len(right) > 0:
        r_rev = right[::-1][: len(left)]
        if len(r_rev) > 2:
            sym_err = float(np.mean(np.abs(left[: len(r_rev)] - r_rev)))
            desc["symmetry"] = {
                "error": sym_err,
                "likely_symmetric": sym_err < 0.05 * (desc["range"][1] - desc["range"][0] + 1e-10),
            }
    # 统计
    desc["mean"] = float(np.mean(ys))
    desc["std"] = float(np.std(ys))
    # 零交叉
    zero_cross = np.where(np.diff(np.signbit(ys)))[0]
    desc["zero_crossings"] = [float(xs[i]) for i in zero_cross[:10]]
    return desc


# ====================== 叙事引擎 ======================


def _narrative_global(xs, ys, desc):
    """全局叙事"""
    parts = []
    a, b = desc["domain"]
    ymin, ymax = desc["range"]
    # 开头
    parts.append(f"在考察区间 [{a:.4g}, {b:.4g}] 上，该函数{desc.get('monotonicity', '')}。")
    parts.append(f"其值域为 [{ymin:.4g}, {ymax:.4g}]，均值为 {desc['mean']:.4g}，标准差为 {desc['std']:.4g}。")
    # 极值
    gmax = desc["global_max"]
    gmin = desc["global_min"]
    parts.append(
        f"于 x={gmax['x']:.4g} 处取得全局最大值 {gmax['y']:.4g}，于 x={gmin['x']:.4g} 处取得全局最小值 {gmin['y']:.4g}。"
    )
    # 凹凸
    if "concavity" in desc:
        parts.append(f"函数{desc['concavity']}。")
    # 对称
    sym = desc.get("symmetry", {})
    if sym.get("likely_symmetric"):
        parts.append(f"该函数在定义域中点附近呈现近似对称性（对称误差 {sym['error']:.4g}）。")
    return "".join(parts)


def _narrative_segments(desc):
    """分段叙事"""
    segments = desc.get("monotone_segments", [])
    if len(segments) <= 1:
        return ""
    parts = [f"将定义域按单调性划分为 {len(segments)} 个区段："]
    for i, seg in enumerate(segments):
        a, b = seg["x_range"]
        parts.append(f"第{i + 1}段 [{a:.4g}, {b:.4g}] 呈{seg['type']}，变化量 Δy={seg['delta_y']:+.4g}；")
    return " ".join(parts)


def _narrative_singularities(desc):
    """特异点叙事"""
    parts = []
    extrema = desc.get("local_extrema", [])
    if extrema:
        parts.append(f"存在 {len(extrema)} 个局部极值点：")
        for e in extrema[:5]:
            parts.append(f"在 x={e['x']:.4g} 处为{e['type']}（y={e['y']:.4g}），")
    inflections = desc.get("inflection_points", [])
    if inflections:
        parts.append(f"检测到 {len(inflections)} 个疑似拐点（二阶差分变号处）：")
        for ip in inflections[:4]:
            parts.append(f"x={ip['x']:.4g}，")
    zeros = desc.get("zero_crossings", [])
    if zeros:
        parts.append(f"函数在定义域内 {len(zeros)} 次穿越零线：")
        for z in zeros[:5]:
            parts.append(f"x≈{z:.4g}，")
    if not extrema and not inflections and not zeros:
        parts.append("未检测到显著的特异点（极值、拐点或零交叉）。")
    return "".join(parts)


def _narrative_induction(xs, ys, desc, n_samples):
    """离散归纳：从采样点推断连续行为"""
    parts = []
    parts.append(f"基于 {n_samples} 个采样点（间距 Δx≈{(xs[-1] - xs[0]) / (n_samples - 1):.4g}）进行离散归纳：")
    # 趋势推断
    segments = desc.get("monotone_segments", [])
    if len(segments) == 1:
        parts.append(f"在采样精度内，函数行为一致（{segments[0]['type']}），推测在连续定义域上保持此单调性。")
    else:
        parts.append(
            f"函数在采样区间内经历 {len(segments)} 次单调性转变，推测连续函数至少存在 {len(segments) - 1} 个临界点。"
        )
    # 平滑性推断
    if "inflection_points" in desc and desc["inflection_points"]:
        parts.append(f"二阶差分的符号变化暗示连续函数的曲率在 {len(desc['inflection_points'])} 处发生改变。")
    # 极值推断
    local = desc.get("local_extrema", [])
    if local:
        parts.append(
            f"局部极值点的分布模式暗示函数可能存在 {len(local)} 个驻点（导数为零点），其位置可通过牛顿法或二分法精确求解。"
        )
    return "".join(parts)


def op_narrate(expr_or_points, var="x", range_=None, n_samples=200, mode="full"):
    """生成自然语言叙事描述"""
    # 获取采样点
    if isinstance(expr_or_points, str) and not expr_or_points.startswith("[["):
        if not range_:
            range_ = [-10, 10]
        sample_r = op_sample_adaptive(expr_or_points, var, range_, n_base=min(80, n_samples // 2), max_n=n_samples)
        if "error" in sample_r:
            return sample_r
        points = sample_r["points"]
    else:
        points = _to_points(expr_or_points)
    if not HAS_NUMPY:
        return {"error": "叙事功能需要 numpy"}
    xs = np.array([p[0] for p in points])
    ys = np.array([p[1] for p in points])
    n = len(xs)
    # 结构化分析
    desc = _describe_structured(xs, ys)
    # 生成叙事
    narratives = {}
    narratives["global"] = _narrative_global(xs, ys, desc)
    narratives["segments"] = _narrative_segments(desc)
    narratives["singularities"] = _narrative_singularities(desc)
    narratives["induction"] = _narrative_induction(xs, ys, desc, n)
    full_text = "\n\n".join(narratives.values())
    return {
        "narratives": narratives if mode != "compact" else None,
        "full_text": full_text,
        "structured": desc,
        "n_samples": n,
        "range": [float(xs[0]), float(xs[-1])],
    }


# ====================== 多尺度分析 ======================


def op_multi_scale(expr, var, range_, scales=None):
    """多尺度分析：在不同采样密度下归纳"""
    if scales is None:
        scales = [
            {"name": "粗尺度", "n": 30, "desc": "捕捉全局趋势，忽略细节波动"},
            {"name": "中尺度", "n": 100, "desc": "平衡全局与局部特征"},
            {"name": "细尺度", "n": 300, "desc": "捕捉局部细节和特异点"},
        ]
    results = []
    for scale in scales:
        sample_r = op_sample(expr, var, range_, scale["n"])
        if "error" in sample_r:
            continue
        xs = np.array([p[0] for p in sample_r["points"]])
        ys = np.array([p[1] for p in sample_r["points"]])
        desc = _describe_structured(xs, ys)
        results.append(
            {
                "scale": scale["name"],
                "n": scale["n"],
                "purpose": scale.get("desc", ""),
                "domain": desc["domain"],
                "range": desc["range"],
                "monotonicity": desc.get("monotonicity", ""),
                "local_extrema_count": len(desc.get("local_extrema", [])),
                "inflection_count": len(desc.get("inflection_points", [])),
                "zero_crossings_count": len(desc.get("zero_crossings", [])),
                "mean": desc["mean"],
                "std": desc["std"],
            }
        )
    # 跨尺度对比
    if len(results) >= 2:
        comparison = {
            "stability": "各尺度下均值与值域高度一致"
            if all(abs(r["mean"] - results[0]["mean"]) < 0.1 * abs(results[0]["mean"]) + 1e-6 for r in results[1:])
            else "不同尺度下统计量存在差异，函数可能具有多尺度特征",
            "emerging_features": [],
        }
        # 检查随尺度增加新出现的特征
        for i in range(1, len(results)):
            if results[i]["local_extrema_count"] > results[0]["local_extrema_count"]:
                comparison["emerging_features"].append(
                    f"{results[i]['scale']}下发现 {results[i]['local_extrema_count'] - results[0]['local_extrema_count']} 个新极值点"
                )
            if results[i]["inflection_count"] > results[0]["inflection_count"]:
                comparison["emerging_features"].append(
                    f"{results[i]['scale']}下发现 {results[i]['inflection_count'] - results[0]['inflection_count']} 个新拐点"
                )
    else:
        comparison = {}
    return {"scales": results, "comparison": comparison, "expr": expr, "range": range_}


# ====================== 描述 ======================


def op_describe(points_or_expr, var="x", range_=None, mode="structured"):
    """曲线描述（支持多种输出模式）"""
    if isinstance(points_or_expr, str) and not points_or_expr.startswith("[["):
        if not range_:
            range_ = [-10, 10]
        sample_r = op_sample(points_or_expr, var, range_, 200)
        if "error" in sample_r:
            return sample_r
        points = sample_r["points"]
    else:
        points = _to_points(points_or_expr)
    if not HAS_NUMPY:
        return {"error": "需要 numpy"}
    xs = np.array([p[0] for p in points])
    ys = np.array([p[1] for p in points])
    desc = _describe_structured(xs, ys)
    result = {"ok": True, "sample_count": len(xs)}
    if mode == "structured":
        result["description"] = desc
    elif mode == "narrative":
        narr = op_narrate(points, var, range_, len(xs))
        result["narrative"] = narr.get("full_text", "")
        result["structured"] = desc
    elif mode == "both":
        narr = op_narrate(points, var, range_, len(xs))
        result["narrative"] = narr.get("full_text", "")
        result["description"] = desc
    return result


OPERATIONS = {
    "sample": op_sample,
    "sample_adaptive": op_sample_adaptive,
    "fit_poly": op_fit_poly,
    "fit_linear": op_fit_linear,
    "fit_exp": op_fit_exp,
    "fit_log": op_fit_log,
    "fit_auto": op_fit_auto,
    "interp_linear": op_interp_linear,
    "interp_cubic": op_interp_cubic,
    "bezier_eval": op_bezier_eval,
    "describe": op_describe,
    "narrate": op_narrate,
    "multi_scale": op_multi_scale,
}


def main():
    parser = argparse.ArgumentParser(
        description="曲线工具集 — 采样/拟合/插值/贝塞尔/叙事描述",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python curve_tools.py --op "sample" --expr "sin(x)" --range "[0,6.28]" --n 100
  python curve_tools.py --op "narrate" --expr "x**3-3*x" --range "[-2,2]"
  python curve_tools.py --op "multi_scale" --expr "exp(-x**2)*sin(5*x)" --range "[0,3]"
  python curve_tools.py --op "describe" --expr "sin(x)" --mode "narrative"
        """,
    )
    parser.add_argument("json_input", nargs="?", help="JSON 输入")
    parser.add_argument("--op", "-o", help="操作名称")
    parser.add_argument("--expr", "-e", help="函数表达式")
    parser.add_argument("--var", default="x", help="变量名")
    parser.add_argument("--range", help="采样范围 [min,max]")
    parser.add_argument("--n", type=int, default=100, help="采样点数")
    parser.add_argument("--mode", default="structured", help="描述模式: structured/narrative/both")
    parser.add_argument("--points", help="采样点 JSON")
    parser.add_argument("--degree", type=int, default=2, help="多项式阶数")
    parser.add_argument("--controls", help="贝塞尔控制点")
    parser.add_argument("--t", type=float, help="贝塞尔参数 t")
    parser.add_argument("--x-query", type=float, help="插值查询点")
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
        if op in ("sample", "sample_adaptive"):
            kwargs["expr"] = args.expr or input_data.get("expr", "")
            kwargs["var"] = args.var or input_data.get("var", "x")
            rng_str = args.range or input_data.get("range", [-10, 10])
            kwargs["range_"] = json.loads(rng_str) if isinstance(rng_str, str) else rng_str
            kwargs["n" if op == "sample" else "n_base"] = args.n or input_data.get("n", 100)
        elif op.startswith("fit"):
            kwargs["points"] = args.points or input_data.get("points", [])
            if op == "fit_poly":
                kwargs["degree"] = args.degree or input_data.get("degree", 2)
        elif op.startswith("interp"):
            kwargs["points"] = args.points or input_data.get("points", [])
            if args.x_query is not None:
                kwargs["x_query"] = args.x_query
            elif "x_query" in input_data:
                kwargs["x_query"] = input_data["x_query"]
        elif op == "bezier_eval":
            kwargs["controls"] = args.controls or input_data.get("controls", [])
            kwargs["n"] = args.n or input_data.get("n", 50)
            if args.t is not None:
                kwargs["t"] = args.t
            elif "t" in input_data:
                kwargs["t"] = input_data["t"]
        elif op in ("describe", "narrate", "multi_scale"):
            expr = args.expr or input_data.get("expr")
            points = args.points or input_data.get("points")
            if points:
                kwargs["points_or_expr"] = points
            elif expr:
                kwargs["points_or_expr"] = expr
            kwargs["var"] = args.var or input_data.get("var", "x")
            if op in ("describe", "narrate"):
                kwargs["mode"] = args.mode or input_data.get("mode", "structured")
            if op == "narrate":
                kwargs["n_samples"] = args.n or input_data.get("n", 200)

        result = OPERATIONS[op](**kwargs)
        output = {"ok": True, "op": op, **result}
        out_str = json.dumps(output, ensure_ascii=False, indent=None if args.compact else 2, default=str)
        if len(out_str) > 100000:
            for key in ["points", "narratives"]:
                if key in output:
                    output[key] = f"[truncated]"
            out_str = json.dumps(output, ensure_ascii=False, indent=None if args.compact else 2, default=str)
        print(out_str)
    except Exception as e:
        output = {"ok": False, "error": str(e), "op": op}
        print(json.dumps(output, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
