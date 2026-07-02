"""
Flask REST API for backtesting.

Endpoints:
    GET  /api/stocks        List available stock symbols.
    GET  /api/stock-names   Stock code → name mapping (with optional ?codes= filter).
    GET  /api/strategies    List available strategies and their parameters.
    GET  /api/benchmark     Benchmark (e.g. CSI 300) daily NAV.
    POST /api/backtest      Run backtest(s) for one or more strategies.
"""

import os
import sys
import traceback
from pathlib import Path

# 确保 backend 包可导入（无论从哪个目录启动）
_PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(_PROJECT_DIR))

from flask import Flask, request, jsonify  # noqa: E402
from flask_cors import CORS  # noqa: E402

from backend.backtest_engine import (  # noqa: E402
    DEFAULT_BENCHMARK,
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


def _check_port(port: int) -> bool:
    """Return True if *port* is available, False if already in use."""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False


if __name__ == "__main__":
    port = int(os.environ.get("RBACKTEST_PORT", 15000))

    if not _check_port(port):
        print(f"[FATAL] Port {port} is already in use!")
        print("        Set RBACKTEST_PORT env var to use a different port, e.g.:")
        print(f"        RBACKTEST_PORT={port + 1} uv run python rbacktest/backend/app.py")
        sys.exit(1)

    app.run(host="0.0.0.0", port=port, debug=False)
