#!/usr/bin/env python3
"""
eval_table.py — 批量表格求值器

用法:
    python eval_table.py --csv data.csv --expr "damage = atk * (1 + crit)" --format json
    python eval_table.py --json rows.json --expr "col3 = col1 + col2" --where "col1 > 0"
    echo '{"rows":[...], "columns":["x","y"]}' | python eval_table.py --expr "z = x + y"
    python eval_table.py --csv data.csv --agg "total = sum(price)" --agg "avg = mean(price)"

输入:
    CSV 文件、JSON 数组、或 stdin JSON {'rows': [...], 'columns': [...]}

输出:
    CSV 或 JSON 表格（带新计算列）

设计:
    - 通过 subprocess 调用 eval_expr.py 做实际求值
    - 列名自动映射为变量名
    - 支持内置降级求值（若 eval_expr.py 不可用）
"""
import sys, json, csv, io, os, subprocess, argparse


# ====================== 内置求值（降级） ======================

def _find_eval_expr():
    """查找 eval_expr.py"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(script_dir, 'eval_expr.py')
    if os.path.exists(path):
        return path
    return None


def _eval_via_subprocess(expr, vars_dict):
    """通过 eval_expr.py 求值"""
    eval_path = _find_eval_expr()
    if eval_path:
        inp = json.dumps({"expr": expr, "vars": vars_dict})
        try:
            r = subprocess.run(
                [sys.executable, eval_path, '--compact'],
                input=inp, capture_output=True, text=True, timeout=15,
                cwd=os.path.dirname(eval_path)
            )
            if r.returncode == 0:
                data = json.loads(r.stdout)
                return data.get('result')
            else:
                raise ValueError(r.stderr.strip() or "eval_expr 返回非零")
        except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
            raise ValueError(f"eval_expr 调用失败: {e}")
    else:
        # 降级：内置安全求值
        return _eval_builtin(expr, vars_dict)


def _eval_builtin(expr, vars_dict):
    """内置安全求值（不含 eval_expr.py 时的降级方案）"""
    import ast, math, operator

    ALLOWED = {
        'sin': math.sin, 'cos': math.cos, 'tan': math.tan,
        'asin': math.asin, 'acos': math.acos, 'atan': math.atan, 'atan2': math.atan2,
        'sqrt': math.sqrt, 'log': math.log, 'log10': math.log10, 'log2': math.log2,
        'exp': math.exp, 'pow': pow, 'abs': abs, 'max': max, 'min': min,
        'round': round, 'int': int, 'float': float, 'sum': sum, 'len': len,
        'pi': math.pi, 'e': math.e, 'inf': math.inf,
    }

    class _Eval:
        def __init__(self, vars_dict):
            self.vars = vars_dict

        def _eval(self, node):
            if isinstance(node, ast.Constant):
                return node.value
            if isinstance(node, ast.Name):
                if node.id in self.vars:
                    return self.vars[node.id]
                if node.id in ALLOWED:
                    return ALLOWED[node.id]
                raise NameError(f"变量未定义: {node.id}")
            if isinstance(node, ast.BinOp):
                l, r = self._eval(node.left), self._eval(node.right)
                ops = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
                       ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod}
                return ops[type(node.op)](l, r)
            if isinstance(node, ast.UnaryOp):
                v = self._eval(node.operand)
                return -v if isinstance(node.op, ast.USub) else +v
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in ALLOWED:
                    args = [self._eval(a) for a in node.args]
                    return ALLOWED[node.func.id](*args)
            raise ValueError("不支持的表达式")

        def eval(self, s):
            tree = ast.parse(s.strip(), mode='eval')
            return self._eval(tree.body)

    return _Eval(vars_dict).eval(expr)


# ====================== 聚合函数 ======================

def _compute_agg(rows, agg_expr):
    """计算聚合。格式: 'name = func(col)' 或 'name = expression'"""
    if '=' not in agg_expr:
        raise ValueError(f"聚合格式: 'name = func(col)', 得到: {agg_expr}")
    name, func_expr = agg_expr.split('=', 1)
    name = name.strip()
    func_expr = func_expr.strip()

    # 支持内置聚合函数
    import re, statistics
    # sum(col), mean(col), min(col), max(col), count(col), median(col), std(col)
    m = re.match(r'(sum|mean|min|max|count|median|std|var)\((\w+)\)', func_expr)
    if m:
        func, col = m.group(1), m.group(2)
        values = [row.get(col, 0) for row in rows]
        if func == 'sum':
            return name, sum(values)
        elif func == 'mean':
            return name, sum(values) / len(values) if values else 0
        elif func == 'min':
            return name, min(values) if values else 0
        elif func == 'max':
            return name, max(values) if values else 0
        elif func == 'count':
            return name, len(values)
        elif func == 'median':
            return name, statistics.median(values) if values else 0
        elif func == 'std':
            return name, statistics.stdev(values) if len(values) > 1 else 0
        elif func == 'var':
            return name, statistics.variance(values) if len(values) > 1 else 0

    raise ValueError(f"不支持的聚合: {func_expr}")


# ====================== CSV 工具 ======================

def read_csv(path_or_text):
    """读取 CSV 文件或文本"""
    if os.path.exists(path_or_text):
        with open(path_or_text, 'r', encoding='utf-8-sig') as f:
            text = f.read()
    else:
        text = path_or_text
    reader = csv.DictReader(io.StringIO(text))
    return list(reader)


def write_csv(rows, file=None):
    """写入 CSV"""
    if not rows:
        return ""
    cols = list(rows[0].keys())
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=cols)
    writer.writeheader()
    writer.writerows(rows)
    result = out.getvalue()
    if file:
        with open(file, 'w', encoding='utf-8') as f:
            f.write(result)
    return result


# ====================== 主入口 ======================

def main():
    parser = argparse.ArgumentParser(
        description="批量表格求值器 — 对每行执行表达式计算",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python eval_table.py --csv data.csv --expr "damage = atk * (1 + crit_rate * crit_mult)"
  python eval_table.py --json rows.json --expr "z = x + y" --where "x > 0"
  echo '{"rows":[{"x":1},{"x":2}]}' | python eval_table.py --expr "y = x * 2"
  python eval_table.py --csv data.csv --agg "total = sum(price)"
        """
    )
    parser.add_argument('--csv', help='CSV 文件路径')
    parser.add_argument('--json', help='JSON 文件路径（数组或 {rows:[...]}）')
    parser.add_argument('--expr', '-e', action='append', default=[],
                        help='计算表达式（格式: new_col = expression），可多次使用')
    parser.add_argument('--agg', action='append', default=[],
                        help='聚合表达式（格式: name = func(col)）')
    parser.add_argument('--where', '-w', help='过滤条件表达式')
    parser.add_argument('--sort', '-s', help='排序字段（-col 表示降序）')
    parser.add_argument('--head', '-n', type=int, default=0, help='仅输出前 N 行')
    parser.add_argument('--format', '-f', choices=['json', 'csv'], default='json',
                        help='输出格式 (默认 json)')
    parser.add_argument('--output', '-o', help='输出文件路径')
    parser.add_argument('--compact', '-c', action='store_true', help='紧凑输出')

    args = parser.parse_args()

    # 读取输入
    rows = []
    if args.csv:
        rows = read_csv(args.csv)
    elif args.json:
        with open(args.json, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list):
            rows = data
        elif isinstance(data, dict):
            rows = data.get('rows', data.get('data', []))
    elif not sys.stdin.isatty():
        raw = sys.stdin.read().strip()
        if raw:
            data = json.loads(raw)
            if isinstance(data, list):
                rows = data
            elif isinstance(data, dict):
                rows = data.get('rows', data.get('data', []))

    if not rows:
        print(json.dumps({"ok": False, "error": "无输入数据"}, ensure_ascii=False))
        sys.exit(1)

    # 确保所有行是 dict
    rows = [{k: v for k, v in (row.items() if isinstance(row, dict) else enumerate(row))}
            for row in rows]

    # 过滤
    if args.where:
        filtered = []
        for row in rows:
            try:
                if _eval_via_subprocess(args.where, row):
                    filtered.append(row)
            except Exception:
                pass
        rows = filtered

    # 计算新列
    for expr_str in args.expr:
        if '=' not in expr_str:
            print(json.dumps({"ok": False, "error": f"表达式格式错误（需要 'col = expr'）: {expr_str}"},
                             ensure_ascii=False), file=sys.stderr)
            continue
        new_col, formula = expr_str.split('=', 1)
        new_col = new_col.strip()
        formula = formula.strip()
        for row in rows:
            try:
                row[new_col] = _eval_via_subprocess(formula, row)
            except Exception as e:
                row[new_col] = None
                print(f"警告: 行求值失败 [{formula}]: {e}", file=sys.stderr)

    # 聚合
    agg_results = {}
    for agg_expr in args.agg:
        try:
            name, val = _compute_agg(rows, agg_expr)
            agg_results[name] = val
        except Exception as e:
            print(f"警告: 聚合失败 [{agg_expr}]: {e}", file=sys.stderr)

    # 排序
    if args.sort:
        col = args.sort
        reverse = False
        if col.startswith('-'):
            col = col[1:]
            reverse = True
        try:
            rows.sort(key=lambda r: r.get(col, 0) or 0, reverse=reverse)
        except Exception:
            pass

    # 截断
    if args.head > 0:
        rows = rows[:args.head]

    # 输出
    output = {"ok": True, "count": len(rows), "rows": rows}
    if agg_results:
        output["aggregates"] = agg_results

    out_str = json.dumps(output, ensure_ascii=False, indent=None if args.compact else 2)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            if args.format == 'csv':
                f.write(write_csv(rows))
            else:
                f.write(out_str)
    else:
        if args.format == 'csv':
            print(write_csv(rows))
        else:
            print(out_str)


if __name__ == '__main__':
    main()
