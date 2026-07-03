#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MIRROR="https://pypi.tuna.tsinghua.edu.cn/simple"
BACKEND_PORT="${RBACKTEST_PORT:-15000}"
FRONTEND_PORT="${RBACKTEST_FRONTEND_PORT:-5173}"

# ---- colour helpers ----
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()  { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# ---- port check helper ----
port_in_use() {
    lsof -i ":$1" -sTCP:LISTEN >/dev/null 2>&1
}

# ---- check prerequisites ----
command -v uv  >/dev/null 2>&1 || err "uv not found — install it first: https://docs.astral.sh/uv/"
command -v npm >/dev/null 2>&1 || err "npm not found — install Node.js first"

# ---- data check ----
if [ ! -d "$SCRIPT_DIR/data/daily" ] || [ -z "$(ls -A "$SCRIPT_DIR/data/daily" 2>/dev/null)" ]; then
    warn "data/daily/ is empty or missing"
    warn "Please add daily parquet files and contract.json to data/ before running backtests."
    warn "The server will start but return an empty stock list."
fi

# ---- port availability check ----
if port_in_use "$BACKEND_PORT"; then
    err "Port $BACKEND_PORT is already in use! Set RBACKTEST_PORT env var to override."
fi

# ---- backend setup ----
echo ""
echo "========== Backend =========="
cd "$SCRIPT_DIR/backend"

if [ ! -d ".venv" ]; then
    log "Creating Python virtual environment ..."
    uv venv
fi

log "Installing / updating Python dependencies ..."
uv pip install flask flask-cors polars pytest openai -q --index-url "$MIRROR" 2>&1 | tail -1
uv pip install vnpy -q --index-url "$MIRROR" 2>&1 | tail -1
uv pip install alphalens-reloaded scipy scikit-learn pyarrow -q --index-url "$MIRROR" 2>&1 | tail -1

log "Starting backend (Flask on :$BACKEND_PORT) ..."
RBACKTEST_PORT="$BACKEND_PORT" .venv/bin/python app.py &
BACKEND_PID=$!

# ---- frontend setup ----
echo ""
echo "========== Frontend ========="
cd "$SCRIPT_DIR/frontend"

if [ ! -d "node_modules" ]; then
    log "Installing Node dependencies ..."
    npm install --silent
fi

if port_in_use "$FRONTEND_PORT"; then
    warn "Port $FRONTEND_PORT is in use — Vite will auto-select the next available port"
fi

log "Starting frontend (Vite on :$FRONTEND_PORT) ..."
npm run dev -- --host --port "$FRONTEND_PORT" &
FRONTEND_PID=$!

# ---- ready ----
echo ""
echo "=============================================="
echo "  Backend  → http://localhost:$BACKEND_PORT"
echo "  Frontend → http://localhost:$FRONTEND_PORT"
echo "  Press Ctrl+C to stop all services"
echo "=============================================="
echo ""

cleanup() {
    echo ""
    log "Shutting down ..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    exit 0
}

trap cleanup INT TERM
wait
