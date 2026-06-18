#!/usr/bin/env python3
"""
verify.py — 交叉验证框架

核心理念: 大模型在数学计算上不可靠，需要多种方法交叉验证。
本脚本是"验证调度器"——调度多个计算方法，比较结果，生成验证报告。

用法:
    echo '{"name":"验证","methods":[...]}' | python verify.py
    python verify.py --file verify_plan.json

问题定义 JSON:
{
  "name": "技能伤害公式验证",
  "methods": [
    {"name":"手工计算","tool":"python eval_expr.py","input":{"expr":"...","vars":{...}},"expected":1600,"tolerance":0.01},
    {"name":"sympy验证","tool":"python calc_sym.py","input":{"expr":"...","op":"eval"},"expected":1600,"tolerance":0.0}
  ],
  "consensus": "all"
}
"""

import sys, json, math, subprocess, os, argparse, time


def run_method(method, timeout_sec=30):
    """运行单个验证方法"""
    name = method.get("name", "unknown")
    tool_cmd = method.get("tool", "")
    inp = method.get("input", {})
    inp_json = json.dumps(inp)

    try:
        # 解析命令
        cmd_parts = tool_cmd.strip().split()
        cmd_parts = [p for p in cmd_parts if p]

        # 传递 JSON 到 stdin
        r = subprocess.run(
            cmd_parts + ["--compact"],
            input=inp_json,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        stdout = r.stdout.strip()
        stderr = r.stderr.strip()

        if r.returncode != 0:
            return {
                "method": name,
                "status": "error",
                "error": stderr or f"Exit code {r.returncode}",
                "raw_output": stdout[:500],
            }

        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            data = {"raw": stdout}

        result_value = data.get("result") if "result" in data else data

        return {
            "method": name,
            "status": "ok",
            "result": result_value,
            "raw": data,
        }
    except subprocess.TimeoutExpired:
        return {"method": name, "status": "timeout", "error": f"超时 ({timeout_sec}s)"}
    except FileNotFoundError:
        return {"method": name, "status": "error", "error": f"命令未找到: {cmd_parts[0] if cmd_parts else tool_cmd}"}
    except Exception as e:
        return {"method": name, "status": "error", "error": str(e)}


def compare_results(results, expected, tolerance=0.0):
    """比较结果与期望值"""
    for r in results:
        if r["status"] != "ok":
            r["match"] = None
            r["error_val"] = None
            continue

        actual = r.get("result")
        if expected is None:
            r["match"] = True
            r["error_val"] = 0
            continue

        try:
            actual_f = float(actual)
            expected_f = float(expected)
            error = abs(actual_f - expected_f)
            r["error_val"] = error
            r["match"] = error <= tolerance or math.isclose(actual_f, expected_f, rel_tol=max(tolerance, 1e-10))
        except (TypeError, ValueError):
            r["match"] = str(actual) == str(expected)
            r["error_val"] = None

    return results


def compute_consensus(results, consensus_mode="all"):
    """计算一致性"""
    ok_count = sum(1 for r in results if r.get("match") is True)
    total = len(results)
    errored = sum(1 for r in results if r.get("match") is None)

    if consensus_mode == "all":
        passed = ok_count == total and total > 0
    elif consensus_mode == "majority":
        passed = ok_count > total / 2
    elif consensus_mode == "any":
        passed = ok_count >= 1
    else:
        passed = ok_count == total

    return {
        "passed": passed,
        "consensus_mode": consensus_mode,
        "ok_count": ok_count,
        "total": total,
        "errored": errored,
        "summary": f"{ok_count}/{total} methods passed (consensus: {consensus_mode})",
    }


def main():
    parser = argparse.ArgumentParser(
        description="交叉验证框架 — 多方法验算",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  echo '{"name":"test","methods":[...]}' | python verify.py
  python verify.py --file verify_plan.json
    """,
    )
    parser.add_argument("json_input", nargs="?", help="JSON 输入")
    parser.add_argument("--file", "-f", help="验证计划 JSON 文件")
    parser.add_argument("--timeout", type=int, default=30, help="每个方法超时(秒)")
    parser.add_argument("--compact", "-c", action="store_true", help="紧凑输出")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")

    args = parser.parse_args()

    # 读取输入
    plan = {}
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            plan = json.load(f)
    elif args.json_input:
        plan = json.loads(args.json_input)
    elif not sys.stdin.isatty():
        raw = sys.stdin.read().strip()
        if raw:
            plan = json.loads(raw)

    if not plan or "methods" not in plan:
        print(json.dumps({"ok": False, "error": "需要 methods 列表"}, ensure_ascii=False))
        sys.exit(1)

    name = plan.get("name", "未命名验证")
    methods = plan.get("methods", [])
    consensus_mode = plan.get("consensus", "all")
    tolerance = plan.get("tolerance", 0.0)

    if args.verbose:
        print(f"验证: {name}", file=sys.stderr)
        print(f"方法数: {len(methods)}, 共识模式: {consensus_mode}", file=sys.stderr)

    # 运行所有方法
    results = []
    for i, method in enumerate(methods):
        if args.verbose:
            print(f"  [{i + 1}/{len(methods)}] {method.get('name', 'unknown')}...", file=sys.stderr)
        r = run_method(method, timeout_sec=args.timeout)
        results.append(r)

    # 比较结果
    expected = plan.get("expected")
    results = compare_results(results, expected, tolerance)

    # 一致性
    consensus = compute_consensus(results, consensus_mode)

    # 异常检测
    discrepancies = [r for r in results if r.get("match") is False]

    report = {
        "ok": consensus["passed"],
        "name": name,
        "consensus": consensus,
        "results": results,
        "discrepancies": discrepancies,
        "expected": expected,
        "tolerance": tolerance,
    }

    print(json.dumps(report, ensure_ascii=False, indent=None if args.compact else 2, default=str))

    if not consensus["passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
