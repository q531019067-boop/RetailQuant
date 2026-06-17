#!/usr/bin/env python3
"""
formula_explain.py — 公式拆解与分层讲解路径生成

核心理念: 复杂公式让人看不懂，不是因为它"难"，而是缺乏由浅入深的分层引导。
本脚本分析公式结构，识别难点，生成"教学式讲解路径"。

用法:
    python formula_explain.py --op "analyze" --expr "exp(-x**2/(2*sigma**2))/(sigma*sqrt(2*pi))"
    python formula_explain.py --op "decompose" --expr "sin(a)*cos(b) + cos(a)*sin(b)"
    python formula_explain.py --op "explain" --expr "P(A|B) = P(B|A)P(A)/P(B)"

支持的操作:
    analyze, decompose, explain, suggest
"""
import sys, json, math, re, argparse

try:
    import sympy as sp
    HAS_SYMPY = True
except ImportError:
    HAS_SYMPY = False

# 尝试加载 formula_desc 知识库
try:
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "formula_desc",
        __file__.replace('formula_explain.py', 'formula_desc.py'))
    fd_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fd_mod)
    HAS_KB = True
except Exception:
    HAS_KB = False


# ====================== 复杂度分析 ======================

COMPLEXITY_PATTERNS = [
    ("嵌套分式", r'\\frac\{[^}]*\\frac', "分式中嵌套分式，容易搞混分子分母——建议先展开内层分式"),
    ("多重求和/积分", r'(\\sum|\\int).*(\\sum|\\int)', "多个Σ或∫嵌套，暗示多维累加——建议从内层向外层理解"),
    ("分段函数", r'\\begin\{cases\}', "分段定义需要逐段分析，注意边界点的衔接"),
    ("高阶导数", r"f\^\{\([3-9]|\\prime{3,}", "高阶导数符号密集——建议用莱布尼茨记号d^nf/dx^n更直观"),
    ("隐式定义", r'(?<!=)=(?!=).*(?<!=)=(?!=)', "多个等号表示联立条件/定义链——逐一拆解"),
    ("含绝对值", r'\\left\|.*\\right\||\|.*\|', "绝对值破坏了光滑性——需要分正负情况讨论"),
    ("含无穷", r'\\infty|\\lim|\\to\\s*\\infty', "涉及无穷——需要说明趋近方向和收敛性"),
    ("三角函数嵌套", r'(sin|cos|tan)\s*\([^)]*(sin|cos|tan)', "三角函数的嵌套组合——可用三角恒等式降幂化简"),
    ("指数和对数共存", r'(exp|e\^).*\\ln|\\ln.*(exp|e\^)', "指数和对数互逆——可利用e^{ln x}=x简化"),
]


def op_analyze(expr_str):
    """分析公式的复杂度和难点"""
    analysis = {
        "expr": expr_str,
        "length": len(expr_str),
        "difficulty_hints": [],
    }

    # 符号分析
    if HAS_SYMPY:
        try:
            expr = sp.sympify(expr_str)
            analysis["free_variables"] = [str(v) for v in expr.free_symbols]
            analysis["variable_count"] = len(expr.free_symbols)
            # 嵌套深度
            depth = _count_nesting(expr)
            analysis["nesting_depth"] = depth
            # 操作计数
            analysis["operation_counts"] = _count_operations(expr)
            # 类型
            if expr.is_polynomial():
                analysis["expression_type"] = f"多项式（次数{sp.degree(expr)}）"
            elif expr.is_rational_function():
                analysis["expression_type"] = "有理函数（分式）"
            elif expr.has(sp.sin, sp.cos, sp.tan):
                analysis["expression_type"] = "三角函数表达式"
            elif expr.has(sp.exp):
                analysis["expression_type"] = "含指数函数"
            elif expr.has(sp.log):
                analysis["expression_type"] = "含对数函数"
            else:
                analysis["expression_type"] = "一般表达式"
        except Exception:
            analysis["parse_error"] = "sympy 解析失败，使用文本分析"

    # 文本模式检测
    for pattern_name, pattern, hint in COMPLEXITY_PATTERNS:
        if re.search(pattern, expr_str):
            analysis["difficulty_hints"].append({
                "pattern": pattern_name,
                "explanation": hint,
            })

    # 整体评估
    hints_count = len(analysis["difficulty_hints"])
    if hints_count == 0:
        analysis["overall"] = "该公式结构简单，可直接从定义出发讲解。"
    elif hints_count <= 2:
        analysis["overall"] = "该公式有少量难点，建议逐层拆解后分别讲解。"
    elif hints_count <= 4:
        analysis["overall"] = "该公式有一定复杂度，建议从最简单特例入手，逐步增加复杂度。"
    else:
        analysis["overall"] = "该公式较复杂，建议：①先讲动机（为什么需要这个公式）②拆解为3-5个子部分分别讲③用具体数值代入演示④最后合成完整形式。"

    return analysis


def _count_nesting(expr):
    """计算表达式树的最大嵌套深度"""
    if not expr.args:
        return 1
    return 1 + max(_count_nesting(a) for a in expr.args) if expr.args else 1


def _count_operations(expr):
    """统计各类操作的数量"""
    ops = {"add": 0, "mul": 0, "pow": 0, "div": 0, "func": 0}
    if expr.is_Add: ops["add"] += 1
    if expr.is_Mul: ops["mul"] += 1
    if expr.is_Pow: ops["pow"] += 1
    if isinstance(expr, sp.Pow) and expr.exp.is_negative:
        ops["div"] += 1
    for a in expr.args:
        sub = _count_operations(a)
        for k in ops: ops[k] += sub[k]
    return ops


# ====================== 公式拆解 ======================

def op_decompose(expr_str):
    """将公式拆解为子表达式树"""
    if not HAS_SYMPY:
        return {"error": "需要 sympy"}
    try:
        expr = sp.sympify(expr_str)
        tree = _build_decomp_tree(expr, "公式整体")
        return {"expr": expr_str, "decomposition": tree, "latex": sp.latex(expr)}
    except Exception as e:
        return {"error": str(e)}


def _build_decomp_tree(expr, label, depth=0):
    """递归构建拆解树"""
    node = {"label": label, "sub_expr": str(expr), "depth": depth}
    if not expr.args:
        return node
    # 根据操作类型分类
    children = []
    if expr.is_Add:
        children = [{"label": f"第{i+1}项", "sub_expr": str(a)} for i, a in enumerate(expr.args)]
    elif expr.is_Mul:
        children = [{"label": f"第{i+1}个因子", "sub_expr": str(a)} for i, a in enumerate(expr.args)]
    elif expr.is_Pow:
        children = [
            {"label": "底数", "sub_expr": str(expr.base)},
            {"label": "指数", "sub_expr": str(expr.exp)},
        ]
    elif hasattr(expr, 'func'):
        children = [{"label": f"参数{i+1}", "sub_expr": str(a)} for i, a in enumerate(expr.args)]
    else:
        children = [{"label": f"子表达式", "sub_expr": str(a)} for a in expr.args]

    for child in children:
        try:
            child_expr = sp.sympify(child["sub_expr"])
            child["detail"] = _build_decomp_tree(child_expr, child["label"], depth + 1)
        except Exception:
            pass
    node["children"] = children
    return node


# ====================== 讲解路径生成 ======================

def op_suggest(expr_str):
    """基于公式复杂度，建议讲解方法"""
    analysis = op_analyze(expr_str)
    suggestions = []

    # 基础建议
    suggestions.append({
        "step": 1,
        "title": "建立动机",
        "action": "先解释'为什么要用这个公式'——它解决了什么问题？不用它时会怎样？",
        "example": "例如讲解贝叶斯公式前，先提问'已知检测阳性，真正患病的概率是多少？'让读者感到需要这个公式。",
    })

    # 基于变量数
    n_vars = analysis.get("variable_count", 1)
    if n_vars > 2:
        suggestions.append({
            "step": 2,
            "title": "降维讲解",
            "action": f"公式有{n_vars}个变量，先从1-2个变量的最简单情况讲起，再推广。",
            "example": "先固定其他变量为常数，只展示一个变量的变化效果。",
        })

    # 基于嵌套深度
    depth = analysis.get("nesting_depth", 1)
    if depth > 3:
        suggestions.append({
            "step": 3,
            "title": "分层拆解",
            "action": f"公式嵌套深度为{depth}，建议分{depth}层逐层讲解。每层用一个独立的小节。",
            "example": "第1层：最内层子表达式 → 第2层：中间结构 → 第3层：整体形式。",
        })

    # 基于难点
    for hint in analysis.get("difficulty_hints", []):
        suggestions.append({
            "step": len(suggestions) + 1,
            "title": f"攻克难点：{hint['pattern']}",
            "action": hint["explanation"],
        })

    # 收尾
    suggestions.append({
        "step": len(suggestions) + 1,
        "title": "举例验证",
        "action": "代入2-3组具体数值，手算验证公式的正确性。数值不要取0或1（太特殊），取普通数字让读者感受到'这真的能用'。",
        "example": "例如取 x=2, y=3，一步步代入公式计算，展示中间结果。",
    })
    suggestions.append({
        "step": len(suggestions) + 1,
        "title": "画图直观化",
        "action": "用 plot_tools.py 生成曲线图/散点图，让读者一眼看到公式的几何意义。",
        "tool": "plot_tools.py --op curve --expr ...",
    })
    suggestions.append({
        "step": len(suggestions) + 1,
        "title": "预判跟进问题",
        "action": "推测读者看完后可能产生的疑问，预先给出答案或引导方向。常见疑问：'这个公式的适用范围是什么？''如果条件不满足会怎样？''有没有更简单的近似？'",
    })

    return {
        "expr": expr_str,
        "analysis": analysis,
        "teaching_path": suggestions,
        "estimated_time": f"约{len(suggestions)*3}-{len(suggestions)*5}分钟讲解",
    }


def op_explain(expr_str, audience="general"):
    """生成完整的分层讲解计划（整合分析和建议）"""
    analysis = op_analyze(expr_str)
    decomposition = op_decompose(expr_str) if HAS_SYMPY else {"note": "需要 sympy"}
    path = op_suggest(expr_str)

    # 尝试从知识库获取已知解释
    kb_info = None
    if HAS_KB:
        try:
            # 尝试反向搜索
            result = fd_mod.op_search(expr_str)
            if result.get('found', 0) > 0:
                kb_info = {
                    "matched_entry": result['results'][0]['name'],
                    "formula": result['results'][0].get('formula', ''),
                    "geometric": result['results'][0].get('geometric', ''),
                }
        except Exception:
            pass

    # 生成讲解摘要
    summary_parts = []
    if analysis.get("expression_type"):
        summary_parts.append(f"这是一个{analysis['expression_type']}。")
    if analysis.get("variable_count", 0) > 0:
        summary_parts.append(f"涉及{analysis['variable_count']}个变量：{', '.join(analysis.get('free_variables', []))}。")
    summary_parts.append(analysis.get("overall", ""))

    return {
        "expr": expr_str,
        "audience": audience,
        "summary": "".join(summary_parts),
        "complexity_analysis": analysis,
        "decomposition": decomposition,
        "teaching_path": path.get("teaching_path", []),
        "knowledge_base_match": kb_info,
        "estimated_time": path.get("estimated_time", ""),
    }


OPERATIONS = {
    'analyze': op_analyze,
    'decompose': op_decompose,
    'explain': op_explain,
    'suggest': op_suggest,
}


def main():
    parser = argparse.ArgumentParser(
        description="公式拆解与分层讲解路径生成",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python formula_explain.py --op "analyze" --expr "exp(-x**2/(2*sigma**2))/(sigma*sqrt(2*pi))"
  python formula_explain.py --op "decompose" --expr "sin(a+b)"
  python formula_explain.py --op "explain" --expr "P(A|B) = P(B|A)P(A)/P(B)"
  python formula_explain.py --op "suggest" --expr "integrate(sin(x)*exp(-x), (x,0,oo))"
""")
    parser.add_argument('--op', '-o', help='操作名称')
    parser.add_argument('--expr', '-e', help='公式表达式')
    parser.add_argument('--audience', default='general', help='目标读者水平')
    parser.add_argument('--compact', '-c', action='store_true', help='紧凑输出')
    parser.add_argument('json_input', nargs='?', help='JSON 输入')

    args = parser.parse_args()
    input_data = {}
    if args.json_input: input_data = json.loads(args.json_input)
    elif not sys.stdin.isatty():
        raw = sys.stdin.read().strip()
        if raw: input_data = json.loads(raw)

    op = args.op or input_data.get('op', '')
    expr = args.expr or input_data.get('expr', '')

    if not op or op not in OPERATIONS:
        print(json.dumps({"ok": False, "error": f"不支持: {op}, 可用: {list(OPERATIONS.keys())}"}, ensure_ascii=False))
        sys.exit(1)
    if not expr:
        print(json.dumps({"ok": False, "error": "需要 --expr"}, ensure_ascii=False))
        sys.exit(1)

    try:
        kwargs = {'expr_str': expr}
        if op == 'explain':
            kwargs['audience'] = args.audience or input_data.get('audience', 'general')
        result = OPERATIONS[op](**kwargs)
        output = {"ok": True, "op": op, **result}
        print(json.dumps(output, ensure_ascii=False, indent=None if args.compact else 2, default=str))
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
