"""
Flask REST API for backtesting.

Endpoints:
    GET  /api/stocks        List available stock symbols.
    GET  /api/stock-names   Stock code → name mapping (with optional ?codes= filter).
    GET  /api/strategies    List available strategies and their parameters.
    GET  /api/benchmark     Benchmark (e.g. CSI 300) daily NAV.
    POST /api/backtest      Run backtest(s) for one or more strategies.
    POST /api/agent/chat    Agent 对话（SSE 流式）
"""

import csv
import io
import json as _json
import os
import sys
import traceback
import uuid
from pathlib import Path

# 确保 backend 包可导入（无论从哪个目录启动）
_PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(_PROJECT_DIR))

from flask import Flask, Response, request, jsonify  # noqa: E402
from flask_cors import CORS  # noqa: E402

from backend.backtest_engine import (  # noqa: E402
    DEFAULT_BENCHMARK,
    RISK_FREE_RATE,
    get_stock_name,
    get_stock_names,
    list_available_stocks,
    load_benchmark,
    run_backtest,
)
from backend.strategy import list_strategies_metadata  # noqa: E402

app = Flask(__name__)
CORS(app)


def _check_data_dir() -> None:
    """Verify data/ directory exists and contains required files.

    Prints warnings if data is missing but does not abort startup —
    the API will return empty stock lists when no data is present.
    """
    data_dir = Path(__file__).resolve().parent.parent / "data"
    daily_dir = data_dir / "daily"
    contract_file = data_dir / "contract.json"

    if not data_dir.exists():
        print(f"[WARNING] Data directory not found: {data_dir}")
        print("          Please create it and copy daily/*.parquet + contract.json")
        return

    if not daily_dir.exists() or not any(daily_dir.glob("*.parquet")):
        parquet_count = len(list(daily_dir.glob("*.parquet"))) if daily_dir.exists() else 0
        print(f"[WARNING] No daily parquet files found in {daily_dir} ({parquet_count} found)")
        print("          The data/ directory has these subdirectories:")
        for d in sorted(data_dir.iterdir()):
            if d.is_dir():
                count = len(list(d.iterdir()))
                print(f"            {d.name}/  ({count} files)")
        return

    if not contract_file.exists():
        print(f"[WARNING] contract.json not found: {contract_file}")
        print("          VNPY AlphaLab will use default contract settings.")

    stocks = list_available_stocks()
    strats = list_strategies_metadata()
    print(
        f"[OK] Data directory ready: {len(stocks)} stocks, {len(strats)} strategies, contract.json {'found' if contract_file.exists() else 'missing'}"
    )


_check_data_dir()


@app.route("/api/stocks", methods=["GET"])
def get_stocks():
    """Return all available stock symbols as JSON."""
    return jsonify({"stocks": list_available_stocks()})


@app.route("/api/config", methods=["GET"])
def get_config():
    """返回当前费率配置（来自 contract.json 抽样 + rbacktest.toml）。"""
    contract_path = Path(__file__).resolve().parent.parent / "data" / "contract.json"
    commission = {"long_rate": 0.0005, "short_rate": 0.0015, "min_commission": 5.0, "stamp_tax": 0.0005}
    if contract_path.exists():
        try:
            contracts = _json.loads(contract_path.read_text(encoding="utf-8"))
            sample = next(iter(contracts.values()), {})
            commission = {
                "long_rate": sample.get("long_rate", 0.0005),
                "short_rate": sample.get("short_rate", 0.0015),
                "min_commission": 5.0,
                "stamp_tax": 0.0005,
                "pricetick": sample.get("pricetick", 0.01),
            }
        except Exception:
            pass
    return jsonify(
        {
            "benchmark": DEFAULT_BENCHMARK,
            "risk_free_rate": RISK_FREE_RATE,
            "commission": commission,
        }
    )


@app.route("/api/stock-names", methods=["GET"])
def get_stock_names_api():
    """返回代码→名称映射。可选 ?codes=600519.SSE,000858.SZSE 只返回指定代码。"""
    codes_param = request.args.get("codes", "")
    if codes_param:
        wanted = [c.strip() for c in codes_param.split(",") if c.strip()]
        names = {c: get_stock_name(c) for c in wanted}
    else:
        names = get_stock_names()
    return jsonify({"names": names, "count": len(names)})


@app.route("/api/strategies", methods=["GET"])
def get_strategies():
    """Return all available strategy definitions as JSON."""
    return jsonify({"strategies": list_strategies_metadata()})


@app.route("/api/optimize", methods=["POST"])
def run_optimize():
    """参数网格搜索：对单个策略在参数网格上跑回测，返回所有组合的指标矩阵。

    Request body:
        { vt_symbols, start, end, capital, strategy,
          param_grid: {param_name: [value1, value2, ...]} }
    Returns:
        { task_id, strategy, param_grid, results: [{params, metrics}] }
    """
    try:
        params = request.get_json(force=True)
        strategy_name = params["strategy"]
        param_grid = params["param_grid"]
        vt_symbols = params["vt_symbols"]
        start = params["start"]
        end = params["end"]
        capital = int(params.get("capital", 1_000_000))

        from itertools import product

        keys = list(param_grid.keys())
        values = list(param_grid.values())
        combinations = list(product(*values))

        grid_results = []
        for combo in combinations:
            strat_params = dict(zip(keys, combo))
            result = run_backtest(
                {
                    "vt_symbols": vt_symbols,
                    "start": start,
                    "end": end,
                    "capital": capital,
                    "strategies": [strategy_name],
                    "strategy_params": {strategy_name: strat_params},
                }
            )
            stats = result["results"][strategy_name]["statistics"]
            grid_results.append(
                {
                    "params": strat_params,
                    "total_return": stats.get("total_return", 0),
                    "annual_return": stats.get("annual_return", 0),
                    "sharpe_ratio": stats.get("sharpe_ratio", 0),
                    "max_ddpercent": stats.get("max_ddpercent", 0),
                    "sortino_ratio": stats.get("sortino_ratio", 0),
                    "calmar_ratio": stats.get("calmar_ratio", 0),
                    "win_rate": stats.get("win_rate", 0),
                    "profit_factor": stats.get("profit_factor", 0),
                    "total_trade_count": stats.get("total_trade_count", 0),
                }
            )

        return jsonify(
            {
                "task_id": str(uuid.uuid4()),
                "strategy": strategy_name,
                "param_grid": param_grid,
                "combinations": len(combinations),
                "results": grid_results,
            }
        )
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/benchmark", methods=["GET"])
def get_benchmark():
    """返回基准（如沪深300 000300.SSE）的日线净值序列。

    Query params:
        code  (default "000300.SSE")  基准代码
        start (default "2020-01-01") 起始日期
        end   (default "2026-12-31") 结束日期
    """
    code = request.args.get("code", DEFAULT_BENCHMARK)
    start = request.args.get("start", "2020-01-01")
    end = request.args.get("end", "2026-12-31")
    data = load_benchmark(code, start, end)
    if data is None:
        return jsonify({"error": f"基准 {code} 数据不可用"}), 404
    return jsonify(data)


@app.route("/api/backtest", methods=["POST"])
def run_backtest_api():
    """Accept backtest parameters, run the backtest, return results.

    Request body: JSON with vt_symbols, start, end, capital, strategies,
                  and strategy-specific parameters.

    Returns: JSON with task_id and per-strategy results (statistics + daily records).
    """
    try:
        params = request.get_json(force=True)
        result = run_backtest(params)
        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/export", methods=["POST"])
def export_results():
    """导出回测结果为 CSV。"""
    try:
        body = request.get_json(force=True)
        results = body.get("results", {})

        output = io.StringIO()
        writer = csv.writer(output)
        metric_keys = [
            "strategy",
            "total_return",
            "annual_return",
            "sharpe_ratio",
            "sortino_ratio",
            "calmar_ratio",
            "max_ddpercent",
            "win_rate",
            "profit_factor",
            "avg_win",
            "avg_loss",
            "max_consecutive_wins",
            "max_consecutive_losses",
            "total_trade_count",
            "total_days",
            "total_commission",
            "end_balance",
        ]
        writer.writerow(metric_keys)
        for sn, r in results.items():
            s = r["statistics"]
            row = [sn] + [s.get(k, "") for k in metric_keys[1:]]
            writer.writerow(row)

        csv_content = output.getvalue()
        output.close()

        return Response(
            csv_content,
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=backtest_results.csv"},
        )
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


def _check_port(port: int) -> bool:
    """Return True if *port* is available, False if already in use."""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False


# ---------------------------------------------------------------------------
# Agent 回测结果缓存（避免「查看图表」重复跑回测）
# ---------------------------------------------------------------------------


@app.route("/api/agent/result/<cache_id>", methods=["GET"])
def agent_cached_result(cache_id: str):
    """获取 Agent 工具缓存的全量回测结果。取后即删。"""
    from backend.agent.tools import get_cached_result

    r = get_cached_result(cache_id)
    if r is None:
        return jsonify({"error": "缓存已过期或不存在，请重新让 Agent 分析"}), 404
    return jsonify(r)


# ---------------------------------------------------------------------------
# Agent 对话（SSE 流式）
# ---------------------------------------------------------------------------


@app.route("/api/agent/chat", methods=["POST"])
def agent_chat():
    """Agent 对话端点 —— 返回 SSE 流式事件。"""
    import json

    from backend.agent import run_agent
    from backend.log import logger

    # 鉴权：如果设置了 RBACKTEST_API_KEY 环境变量，要求请求头匹配
    expected_key = os.environ.get("RBACKTEST_API_KEY", "")
    if expected_key:
        req_key = request.headers.get("X-Api-Key", "")
        if req_key != expected_key:
            logger.warning("Agent 鉴权失败: X-Api-Key 不匹配")
            return jsonify({"error": "未授权", "hint": "请在请求头中设置 X-Api-Key"}), 401

    # 必须在进入生成器之前提取 request 数据（生成器 yield 后请求上下文会被销毁）
    try:
        body = request.get_json(force=True)
    except Exception as e:
        logger.error(f"Agent 请求 JSON 解析失败: {e}")
        body = None

    results = body.get("results") if body else None
    params = body.get("params") if body else None
    question = body.get("question", "") if body else ""
    session_id = body.get("session_id") if body else None

    def generate():
        """所有逻辑放生成器内部，确保异常都转为 SSE 事件而非 500。"""
        if body is None:
            yield f"data: {json.dumps({'type': 'error', 'content': '请求体 JSON 解析失败'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return

        try:
            logger.info(f"Agent 会话开始: has_results={bool(results)} has_params={bool(params)}")

            for event in run_agent(results=results, params=params, user_question=question, session_id=session_id):
                yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"

            yield "data: [DONE]\n\n"
            logger.info("Agent 会话完成")
        except Exception as e:
            logger.error(f"Agent SSE 致命异常: {e}", exc_info=True)
            traceback.print_exc()
            err = json.dumps({"type": "error", "content": f"系统错误: {e}"}, ensure_ascii=False)
            yield f"data: {err}\n\n"
            yield "data: [DONE]\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    port = int(os.environ.get("RBACKTEST_PORT", 15000))

    if not _check_port(port):
        print(f"[FATAL] Port {port} is already in use!")
        print("        Set RBACKTEST_PORT env var to use a different port, e.g.:")
        print(f"        RBACKTEST_PORT={port + 1} uv run python rbacktest/backend/app.py")
        sys.exit(1)

    app.run(host="0.0.0.0", port=port, debug=False)
