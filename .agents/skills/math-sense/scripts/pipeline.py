#!/usr/bin/env python3
"""
pipeline.py — Unix 管道组合器

核心理念: 把多个数学工具像 Unix 管道一样串联。每个阶段的输出是下一阶段的输入。

用法:
    echo '{"pipeline":[...]}' | python pipeline.py
    python pipeline.py --file pipeline_plan.json
    python pipeline.py --chain "python eval_expr.py | python eval_table.py"

管道定义 JSON:
{
  "pipeline": [
    {"stage":"step1","tool":"python eval_expr.py","args":{"expr":"x*2","vars":{"x":3}},"output_key":"v1"},
    {"stage":"step2","tool":"python eval_expr.py","args":{"expr":"$prev.v1.result + y","vars":{"y":5}}}
  ],
  "inputs": {}
}
"""

import sys, json, subprocess, os, argparse, re, copy


def resolve_refs(obj, context):
    """解析 $prev.key 和 $inputs.key 引用"""
    if isinstance(obj, str):
        # 替换 $prev.key
        def repl(m):
            path = m.group(1)
            parts = path.split(".")
            val = context.get("_prev", context)
            for p in parts:
                if isinstance(val, dict):
                    val = val.get(p)
                else:
                    return str(val) if val is not None else m.group(0)
            return json.dumps(val) if not isinstance(val, str) else val

        obj = re.sub(r"\$prev\.([\w\.\[\]]+)", repl, obj)
        obj = re.sub(
            r"\$(\w+)",
            lambda m: (
                json.dumps(context.get("_inputs", {}).get(m.group(1), m.group(0)))
                if not isinstance(context.get("_inputs", {}).get(m.group(1)), str)
                else context.get("_inputs", {}).get(m.group(1), m.group(0))
            ),
            obj,
        )
        return obj
    elif isinstance(obj, dict):
        return {k: resolve_refs(v, context) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [resolve_refs(v, context) for v in obj]
    return obj


def run_stage(stage, context):
    """运行单个管道阶段"""
    name = stage.get("stage", "unnamed")
    tool_cmd = stage.get("tool", "")
    args = stage.get("args", {})
    output_key = stage.get("output_key")

    # 解析变量引用
    resolved_args = resolve_refs(args, context)

    # 准备输入 JSON
    inp_json = json.dumps(resolved_args)

    # 执行工具
    cmd_parts = tool_cmd.strip().split()
    try:
        r = subprocess.run(
            cmd_parts + ["--compact"],
            input=inp_json,
            capture_output=True,
            text=True,
            timeout=60,
        )
        stdout = r.stdout.strip()
        stderr = r.stderr.strip()

        if r.returncode != 0:
            return {"stage": name, "ok": False, "error": stderr or f"exit {r.returncode}"}

        try:
            output = json.loads(stdout)
        except json.JSONDecodeError:
            output = {"raw": stdout}

        result = {"stage": name, "ok": True, "output": output}
        if output_key:
            result["key"] = output_key
        return result
    except subprocess.TimeoutExpired:
        return {"stage": name, "ok": False, "error": "timeout"}
    except Exception as e:
        return {"stage": name, "ok": False, "error": str(e)}


def run_pipeline(plan):
    """运行完整管道"""
    pipeline = plan.get("pipeline", [])
    inputs = plan.get("inputs", {})
    stop_on_error = plan.get("stop_on_error", True)

    context = {"_inputs": inputs}
    results = []
    final_output = None

    for stage in pipeline:
        st_result = run_stage(stage, context)

        if st_result["ok"] and "output" in st_result:
            final_output = st_result["output"]
            context["_prev"] = final_output

            # 如果有 output_key，存到 context
            key = st_result.get("key")
            if key:
                context[key] = final_output

        results.append(st_result)

        if not st_result["ok"] and stop_on_error:
            break

    return {
        "ok": all(r["ok"] for r in results),
        "stages": results,
        "final_output": final_output,
        "total": len(pipeline),
        "completed": sum(1 for r in results if r["ok"]),
    }


def run_simple_chain(chain_str):
    """简单链模式: tool1 | tool2 | tool3"""
    stages = chain_str.split("|")
    pipeline = []
    for i, s in enumerate(stages):
        s = s.strip()
        # 解析: python tool.py --args
        parts = s.split(maxsplit=1)
        if len(parts) == 2:
            tool = parts[0]
            args_str = parts[1]
            # 简单处理
            pipeline.append(
                {
                    "stage": f"step{i + 1}",
                    "tool": s,
                    "args": {},
                }
            )
        else:
            pipeline.append(
                {
                    "stage": f"step{i + 1}",
                    "tool": s,
                }
            )
    return run_pipeline({"pipeline": pipeline})


def main():
    parser = argparse.ArgumentParser(
        description="Unix 管道组合器 — 串联数学工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  echo '{"pipeline":[...]}' | python pipeline.py
  python pipeline.py --file pipeline_plan.json
  python pipeline.py --chain "python stats_tools.py --op describe | python eval_expr.py"
    """,
    )
    parser.add_argument("json_input", nargs="?", help="JSON 输入")
    parser.add_argument("--file", "-f", help="管道定义 JSON 文件")
    parser.add_argument("--chain", help='简单链: "tool1 | tool2 | tool3"')
    parser.add_argument("--dry-run", action="store_true", help="仅打印不执行")
    parser.add_argument("--stop-on-error", action="store_true", default=True, help="遇错中止")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    parser.add_argument("--compact", "-c", action="store_true", help="紧凑输出")

    args = parser.parse_args()

    plan = {}
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            plan = json.load(f)
    elif args.chain:
        if args.dry_run:
            print(f"管道: {args.chain}")
            return
        result = run_simple_chain(args.chain)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        sys.exit(0 if result["ok"] else 1)
    elif args.json_input:
        plan = json.loads(args.json_input)
    elif not sys.stdin.isatty():
        raw = sys.stdin.read().strip()
        if raw:
            plan = json.loads(raw)

    if not plan:
        print(json.dumps({"ok": False, "error": "无输入"}, ensure_ascii=False))
        sys.exit(1)

    plan["stop_on_error"] = args.stop_on_error if not args.stop_on_error else plan.get("stop_on_error", True)

    if args.dry_run:
        for stage in plan.get("pipeline", []):
            print(f"DRY-RUN: [{stage.get('stage')}] {stage.get('tool')} <- {stage.get('args')}")
        return

    if args.verbose:
        print(f"管道阶段数: {len(plan.get('pipeline', []))}", file=sys.stderr)

    result = run_pipeline(plan)
    print(json.dumps(result, ensure_ascii=False, indent=None if args.compact else 2, default=str))
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
