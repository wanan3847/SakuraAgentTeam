#!/usr/bin/env bash
# 🌸 樱花小队 — 一键启动脚本（macOS/Linux）
# 同时启动后端和前端，Ctrl+C 停止所有服务

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

echo "🌸 樱花小队 — 启动中..."
echo "  后端: http://localhost:$BACKEND_PORT"
echo "  前端: http://localhost:$FRONTEND_PORT"
echo ""

# 启动后端
cd "$BACKEND_DIR"
python3 -m uvicorn app.api.main:app --host 0.0.0.0 --port "$BACKEND_PORT" &
BACKEND_PID=$!

# 启动前端
cd "$FRONTEND_DIR"
npm run dev -- --port "$FRONTEND_PORT" &
FRONTEND_PID=$!

# 捕获退出信号，杀掉所有子进程
cleanup() {
    echo ""
    echo "🛑 正在停止服务..."
    kill "$BACKEND_PID" 2>/dev/null || true
    kill "$FRONTEND_PID" 2>/dev/null || true
    wait 2>/dev/null
    echo "👋 已停止"
}
trap cleanup EXIT INT TERM

echo "✅ 服务已启动"
echo "   后端 API: http://localhost:$BACKEND_PORT/docs"
echo "   前端页面: http://localhost:$FRONTEND_PORT"
echo "   按 Ctrl+C 停止所有服务"
echo ""

wait
