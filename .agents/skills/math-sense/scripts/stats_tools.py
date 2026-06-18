#!/usr/bin/env python3
"""
stats_tools.py — 统计与概率工具

用法:
    echo '{"op":"describe","data":[1,2,3,4,5,6,7,8,9,10]}' | python stats_tools.py
    python stats_tools.py --op "cdf_build" --items '[{"value":1,"weight":10},{"value":2,"weight":30},{"value":3,"weight":60}]'
    python stats_tools.py --op "monte_carlo" --samples 10000 --expr "x + y" --dist_x "normal(0,1)" --dist_y "uniform(0,1)"

支持的操作:
    describe, histogram, cdf_build, cdf_sample, monte_carlo, bootstrap,
    ks_test, chi2_test, correlation
"""

import sys, json, math, random, argparse

try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    import scipy.stats as stats

    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


def op_describe(data):
    """描述统计"""
    if HAS_NUMPY:
        arr = np.array(data, dtype=float)
        q1 = float(np.percentile(arr, 25))
        q3 = float(np.percentile(arr, 75))
        return {
            "count": len(arr),
            "mean": float(np.mean(arr)),
            "median": float(np.median(arr)),
            "std": float(np.std(arr, ddof=1)) if len(arr) > 1 else 0,
            "var": float(np.var(arr, ddof=1)) if len(arr) > 1 else 0,
            "min": float(np.min(arr)),
            "max": float(np.max(arr)),
            "q1": q1,
            "q3": q3,
            "iqr": q3 - q1,
            "skewness": float(stats.skew(arr)) if HAS_SCIPY else 0,
            "kurtosis": float(stats.kurtosis(arr)) if HAS_SCIPY else 0,
        }
    else:
        n = len(data)
        mean = sum(data) / n
        var = sum((x - mean) ** 2 for x in data) / (n - 1) if n > 1 else 0
        return {"count": n, "mean": mean, "std": math.sqrt(var), "var": var, "min": min(data), "max": max(data)}


def op_histogram(data, bins=10):
    """直方图"""
    if HAS_NUMPY:
        counts, edges = np.histogram(data, bins=bins)
        return {"bins": edges.tolist(), "counts": counts.tolist(), "total": len(data)}
    else:
        mn, mx = min(data), max(data)
        w = (mx - mn) / bins if bins > 0 else 1
        counts = [0] * bins
        for x in data:
            idx = min(int((x - mn) / w), bins - 1) if w > 0 else 0
            counts[idx] += 1
        edges = [mn + i * w for i in range(bins + 1)]
        return {"bins": edges, "counts": counts, "total": len(data)}


def op_cdf_build(items):
    """从加权物品构建累积分布函数。items: [{"value":..., "weight":...}]"""
    weights = [item["weight"] for item in items]
    total = sum(weights)
    cum = 0
    cdf = []
    for item in items:
        cum += item["weight"]
        cdf.append(
            {"value": item["value"], "weight": item["weight"], "prob": item["weight"] / total, "cum_prob": cum / total}
        )
    return {"cdf": cdf, "total_weight": total}


def op_cdf_sample(cdf, n_samples=1, seed=None):
    """从 CDF 采样"""
    if seed is not None:
        random.seed(seed)
    results = {}
    for _ in range(n_samples):
        r = random.random()
        for item in cdf:
            if r <= item["cum_prob"]:
                v = str(item["value"])
                results[v] = results.get(v, 0) + 1
                break
    return {"samples": results, "n": n_samples, "probs": {k: v / n_samples for k, v in results.items()}}


def op_monte_carlo(expr, distributions, n_samples=10000, seed=None):
    """蒙特卡洛模拟。
    distributions: [{"var":"x","dist":"normal","params":[0,1]}, {"var":"y","dist":"uniform","params":[0,1]}]
    expr: 结果表达式，用分布的变量计算
    """
    if seed is not None:
        random.seed(seed)
        if HAS_NUMPY:
            np.random.seed(seed)

    results = []
    for _ in range(n_samples):
        vars_dict = {}
        for d in distributions:
            var = d["var"]
            dist = d.get("dist", "uniform")
            params = d.get("params", [0, 1])
            if HAS_NUMPY:
                if dist == "normal":
                    vars_dict[var] = np.random.normal(params[0], params[1]) if len(params) >= 2 else 0
                elif dist == "uniform":
                    vars_dict[var] = np.random.uniform(params[0], params[1]) if len(params) >= 2 else 0
                elif dist == "exponential":
                    vars_dict[var] = np.random.exponential(params[0]) if len(params) >= 1 else 0
                elif dist == "poisson":
                    vars_dict[var] = np.random.poisson(params[0]) if len(params) >= 1 else 0
            else:
                if dist == "uniform":
                    vars_dict[var] = random.uniform(params[0], params[1]) if len(params) >= 2 else 0
                elif dist == "normal":
                    vars_dict[var] = random.gauss(params[0], params[1]) if len(params) >= 2 else 0

        # 求值
        import ast as _ast
        import operator as _op

        ALLOWED = {
            "sin": math.sin,
            "cos": math.cos,
            "exp": math.exp,
            "log": math.log,
            "sqrt": math.sqrt,
            "abs": abs,
            "max": max,
            "min": min,
            "pi": math.pi,
            "e": math.e,
        }
        try:
            tree = _ast.parse(expr.strip(), mode="eval")

            def ev(node):
                if isinstance(node, _ast.Constant):
                    return node.value
                if isinstance(node, _ast.Name):
                    if node.id in vars_dict:
                        return vars_dict[node.id]
                    if node.id in ALLOWED:
                        return ALLOWED[node.id]
                    raise NameError(node.id)
                if isinstance(node, _ast.BinOp):
                    l, r = ev(node.left), ev(node.right)
                    ops = {
                        _ast.Add: _op.add,
                        _ast.Sub: _op.sub,
                        _ast.Mult: _op.mul,
                        _ast.Div: _op.truediv,
                        _ast.Pow: _op.pow,
                    }
                    return ops[type(node.op)](l, r)
                if isinstance(node, _ast.UnaryOp):
                    v = ev(node.operand)
                    return -v if isinstance(node.op, _ast.USub) else +v
                if isinstance(node, _ast.Call):
                    fn = ev(node.func)
                    args = [ev(a) for a in node.args]
                    return fn(*args)
                return 0

            results.append(ev(tree.body))
        except Exception:
            pass

    if not results:
        return {"error": "所有采样求值失败"}

    arr = np.array(results) if HAS_NUMPY else results
    mean = float(np.mean(arr)) if HAS_NUMPY else sum(results) / len(results)
    std = float(np.std(arr)) if HAS_NUMPY else math.sqrt(sum((x - mean) ** 2 for x in results) / len(results))
    sorted_r = sorted(results)
    ci_95_low = sorted_r[int(len(sorted_r) * 0.025)]
    ci_95_high = sorted_r[int(len(sorted_r) * 0.975)]

    return {
        "n": n_samples,
        "mean": mean,
        "std": std,
        "ci_95": [ci_95_low, ci_95_high],
        "min": min(results),
        "max": max(results),
    }


def op_correlation(x, y, method="pearson"):
    """相关系数"""
    if HAS_SCIPY:
        if method == "pearson":
            r, p = stats.pearsonr(x, y)
            return {"correlation": float(r), "p_value": float(p), "method": "pearson"}
        elif method == "spearman":
            r, p = stats.spearmanr(x, y)
            return {"correlation": float(r), "p_value": float(p), "method": "spearman"}
    if HAS_NUMPY:
        r = np.corrcoef(x, y)[0, 1]
        return {"correlation": float(r), "method": "pearson"}
    return {"error": "需要 numpy 或 scipy"}


def op_prd(nominal_pct, n_trials=1000, seed=None, constant=None):
    """伪随机分布PRD——Dota2人性化随机。初始概率低，未触发递增，触发后重置。"""
    import random as _r

    if seed is not None:
        _r.seed(seed)
    nominal_p = nominal_pct / 100.0
    if constant is None:
        constant = _find_prd_C(nominal_p)
    else:
        constant = constant / 100.0
    triggers, streaks, current_p, streak = 0, [], constant, 0
    for _ in range(n_trials):
        streak += 1
        if _r.random() < current_p:
            triggers += 1
            streaks.append(streak)
            streak = 0
            current_p = constant
        else:
            current_p = min(current_p + constant, 1.0)
    avg_s = sum(streaks) / len(streaks) if streaks else 0
    prd_var = sum((s - avg_s) ** 2 for s in streaks) / len(streaks) if streaks else 0
    true_var = (1 - nominal_p) / (nominal_p * nominal_p) if nominal_p > 0 else 0
    return {
        "nominal_pct": nominal_pct,
        "C_pct": round(constant * 100, 4),
        "actual_pct": round(triggers / n_trials * 100, 2),
        "avg_streak": round(avg_s, 2),
        "prd_var": round(prd_var, 2),
        "true_var": round(true_var, 2),
        "variance_reduction": f"PRD低{round((1 - prd_var / true_var) * 100) if true_var > 0 else 0}%——更均匀",
        "mechanism": f"C={constant * 100:.2f}%/次,期望间隔~{1 / nominal_p:.1f}次",
    }


def _find_prd_C(P_target, max_iter=200):
    C = P_target * 0.5
    for _ in range(max_iter):
        ep = _prd_expected(C, 300000)
        if abs(ep - P_target) < 0.0002:
            break
        C += (P_target - ep) * 0.15
    return max(C, 0.0001)


def _prd_expected(C, n):
    import random as _r

    _r.seed(0)
    trig, p = 0, C
    for _ in range(n):
        if _r.random() < p:
            trig += 1
            p = C
        else:
            p = min(p + C, 1.0)
    return trig / n


def op_pity(base_rate, pity_count, boost_after=0, boost_amount=0, n_trials=100000, seed=None):
    """保底机制模拟。X次未出则必出(soft pity)/概率递增(hard pity的PRD变体)。
    base_rate: 基础概率(如2表示2%); pity_count: 保底次数(如90); boost_after: 从第几次开始概率递增; boost_amount: 每次递增多少"""
    import random as _r

    if seed is not None:
        _r.seed(seed)
    bp = base_rate / 100.0
    total, pity_hits, max_streak = 0, 0, 0
    streak = 0
    current_p = bp
    for _ in range(n_trials):
        streak += 1
        if streak >= boost_after > 0:
            current_p = min(1.0, bp + (streak - boost_after + 1) * boost_amount / 100.0)
        if streak >= pity_count:
            total += 1
            pity_hits += 1
            streak = 0
            current_p = bp
        elif _r.random() < current_p:
            total += 1
            streak = 0
            current_p = bp
        max_streak = max(max_streak, streak)
    actual_rate = total / n_trials * 100
    expected_cost = n_trials / total if total > 0 else float("inf")
    return {
        "base_rate_pct": base_rate,
        "pity_count": pity_count,
        "actual_rate_pct": round(actual_rate, 2),
        "expected_draws": round(expected_cost, 1),
        "pity_triggered_pct": round(pity_hits / total * 100 if total > 0 else 0, 1),
        "max_streak": max_streak,
        "mechanism": f"基础{base_rate}%,{pity_count}抽保底,递增从第{boost_after}抽起+{boost_amount}%/次",
    }


def op_sensitivity(expr, vars_dict, perturb=0.1):
    """敏感性分析：对每个变量做微小扰动(+perturb%)，计算输出变化率。按影响力排序。"""
    import ast as _ast, math as _m, operator as _op

    ALLOWED = {
        "sin": _m.sin,
        "cos": _m.cos,
        "tan": _m.tan,
        "exp": _m.exp,
        "log": _m.log,
        "sqrt": _m.sqrt,
        "abs": abs,
        "pow": pow,
        "pi": _m.pi,
        "e": _m.e,
        "max": max,
        "min": min,
    }
    tree = _ast.parse(expr.strip(), mode="eval")

    def _ev(n, vd):
        if isinstance(n, _ast.Constant):
            return n.value
        if isinstance(n, _ast.Name):
            if n.id in vd:
                return vd[n.id]
            if n.id in ALLOWED:
                return ALLOWED[n.id]
            raise NameError(n.id)
        if isinstance(n, _ast.BinOp):
            l, r = _ev(n.left, vd), _ev(n.right, vd)
            o = {_ast.Add: _op.add, _ast.Sub: _op.sub, _ast.Mult: _op.mul, _ast.Div: _op.truediv, _ast.Pow: _op.pow}
            return o[type(n.op)](l, r)
        if isinstance(n, _ast.UnaryOp):
            v = _ev(n.operand, vd)
            return -v if isinstance(n.op, _ast.USub) else +v
        if isinstance(n, _ast.Call):
            fn = _ev(n.func, vd)
            return fn(*[_ev(a, vd) for a in n.args])
        return 0

    base = _ev(tree.body, vars_dict)
    results = []
    for var, val in vars_dict.items():
        vd_up = dict(vars_dict)
        vd_up[var] = val * (1 + perturb)
        vd_down = dict(vars_dict)
        vd_down[var] = val * (1 - perturb)
        up = _ev(tree.body, vd_up)
        down = _ev(tree.body, vd_down)
        elasticity = (up - down) / (2 * val * perturb) * val / base if base > 0 else 0
        results.append(
            {
                "var": var,
                "base_val": val,
                "abs_change_per_pct": round((up - down) / (2 * perturb), 4),
                "elasticity": round(elasticity, 4),
                "direction": "increase" if up > down else "decrease",
            }
        )
    results.sort(key=lambda x: abs(x["elasticity"]), reverse=True)
    return {
        "base_result": base,
        "perturbation_pct": perturb * 100,
        "ranked": results,
        "top_influence": results[0]["var"] if results else "N/A",
    }


def op_prd_inverse(target_interval, max_iter=200):
    """反向PRD：给定期望触发间隔(如5次一暴)，反算名义概率和C常数。"""
    P_target = 1.0 / target_interval
    C = _find_prd_C(P_target, max_iter)
    return {
        "target_interval": target_interval,
        "nominal_rate_pct": round(P_target * 100, 2),
        "C_constant_pct": round(C * 100, 4),
        "note": f"期望每{target_interval}次触发1次→名义概率{P_target * 100:.1f}%,C={C * 100:.4f}%",
    }


OPERATIONS = {
    "describe": op_describe,
    "histogram": op_histogram,
    "cdf_build": op_cdf_build,
    "cdf_sample": op_cdf_sample,
    "monte_carlo": op_monte_carlo,
    "correlation": op_correlation,
}


def main():
    parser = argparse.ArgumentParser(
        description="统计与概率工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  echo '{"op":"describe","data":[1,2,3,4,5]}' | python stats_tools.py
  python stats_tools.py --op "cdf_build" --items '[{"value":1,"weight":10},{"value":2,"weight":30}]'
  python stats_tools.py --op "monte_carlo" --samples 10000 --expr "x+y" --dists '[{"var":"x","dist":"uniform","params":[0,1]},{"var":"y","dist":"normal","params":[0,1]}]'
        """,
    )
    parser.add_argument("json_input", nargs="?", help="JSON 输入")
    parser.add_argument("--op", "-o", help="操作名称")
    parser.add_argument("--data", help="数据 JSON")
    parser.add_argument("--items", help="加权物品 JSON")
    parser.add_argument("--samples", type=int, default=10000, help="采样数")
    parser.add_argument("--expr", "-e", help="表达式")
    parser.add_argument("--dists", help="分布定义 JSON")
    parser.add_argument("--seed", type=int, help="随机种子")
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
        if op in ("describe", "histogram"):
            kwargs["data"] = json.loads(args.data) if args.data else input_data.get("data", [])
        elif op == "cdf_build":
            kwargs["items"] = json.loads(args.items) if args.items else input_data.get("items", [])
        elif op == "cdf_sample":
            kwargs["cdf"] = input_data.get("cdf", [])
            kwargs["n_samples"] = args.samples or input_data.get("n_samples", 1)
            kwargs["seed"] = args.seed or input_data.get("seed")
        elif op == "monte_carlo":
            kwargs["expr"] = args.expr or input_data.get("expr", "")
            kwargs["distributions"] = json.loads(args.dists) if args.dists else input_data.get("distributions", [])
            kwargs["n_samples"] = args.samples or input_data.get("n_samples", 10000)
            kwargs["seed"] = args.seed or input_data.get("seed")
        elif op == "correlation":
            kwargs["x"] = input_data.get("x", [])
            kwargs["y"] = input_data.get("y", [])
            kwargs["method"] = input_data.get("method", "pearson")

        result = OPERATIONS[op](**kwargs)
        output = {"ok": True, "op": op, **result}
        print(json.dumps(output, ensure_ascii=False, indent=None if args.compact else 2, default=str))
    except Exception as e:
        output = {"ok": False, "error": str(e), "op": op}
        print(json.dumps(output, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
