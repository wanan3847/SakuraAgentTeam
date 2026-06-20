#!/usr/bin/env bash
# SakuraAgentTeam 一键部署脚本
# 用法：./deploy.sh [dev|prod|stop|logs]
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

MODE="${1:-dev}"

# ---------- 颜色输出 ----------
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()   { echo -e "${RED}[ERROR]${NC} $*"; }

# ---------- 检查依赖 ----------
check_deps() {
  if ! command -v docker >/dev/null 2>&1; then
    err "docker 未安装，请先安装 Docker Desktop / docker-ce"
    exit 1
  fi
  if ! docker info >/dev/null 2>&1; then
    err "docker daemon 未运行，请启动 Docker"
    exit 1
  fi
}

# ---------- 加载环境变量 ----------
load_env() {
  if [ -f "backend/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    . backend/.env
    set +a
  else
    warn "backend/.env 不存在，使用 backend/.env.example 模板"
    if [ -f "backend/.env.example" ]; then
      cp backend/.env.example backend/.env
      set -a
      # shellcheck disable=SC1091
      . backend/.env
      set +a
    fi
  fi
}

case "$MODE" in
  dev)
    info "启动开发模式（本地 uvicorn + vite）"
    check_deps
    load_env

    # ---------- 后端 ----------
    # 策略：macOS 上 system Python 通常已装核心依赖（fastapi/openai/anthropic/pytest/structlog）
    # 直接用最快，避免 venv 重新下几百 MB 依赖。
    # 如果关键包缺失，提示用户用 uv 装（比 pip 快 100x）。
    if python3 -c "import fastapi, uvicorn, pydantic_settings, openai, anthropic, structlog" 2>/dev/null; then
      info "使用 system Python（已装核心依赖）"
      PYTHON=python3
    elif [ -d "backend/.venv" ] && backend/.venv/bin/python -c "import fastapi, uvicorn, pydantic_settings, openai, anthropic, structlog" 2>/dev/null; then
      info "使用 backend/.venv 虚拟环境"
      # shellcheck disable=SC1091
      source backend/.venv/bin/activate
      PYTHON=python3
    else
      info "创建后端虚拟环境（需要联网）"
      python3 -m venv backend/.venv
      # shellcheck disable=SC1091
      source backend/.venv/bin/activate
      if command -v uv >/dev/null 2>&1; then
        info "使用 uv 安装依赖（比 pip 快 100x）"
        uv pip install -q -r backend/requirements.txt
      else
        info "使用 pip 安装依赖（首次会下几百 MB）"
        pip3 install -q -r backend/requirements.txt
      fi
      PYTHON=python3
    fi

    info "启动后端 http://localhost:8000"
    cd backend
    nohup "$PYTHON" -m uvicorn app.api.main:app --reload --port 8000 \
      > "$ROOT_DIR/logs/backend.log" 2>&1 &
    BACKEND_PID=$!
    cd "$ROOT_DIR"
    echo "$BACKEND_PID" > "$ROOT_DIR/.backend.pid"
    info "后端 PID: $BACKEND_PID（停止：./deploy.sh stop）"

    # 前端
    if [ ! -d "frontend/node_modules" ]; then
      info "安装前端依赖"
      cd frontend && npm install && cd ..
    fi
    info "启动前端 http://localhost:5173"
    cd frontend
    nohup npm run dev -- --port 5173 \
      > "$ROOT_DIR/logs/frontend.log" 2>&1 &
    FRONTEND_PID=$!
    cd "$ROOT_DIR"
    echo "$FRONTEND_PID" > "$ROOT_DIR/.frontend.pid"
    info "前端 PID: $FRONTEND_PID"

    mkdir -p logs
    info "全部启动完成。后端日志：tail -f logs/backend.log"
    ;;

  prod)
    info "启动生产模式（docker-compose）"
    check_deps
    load_env
    docker compose -f infra/docker-compose.yml up -d --build
    info "服务已启动："
    info "  前端: http://localhost:8080"
    info "  后端: http://localhost:8000/docs"
    ;;

  stop)
    info "停止所有服务"
    [ -f "$ROOT_DIR/.backend.pid" ] && kill "$(cat "$ROOT_DIR/.backend.pid")" 2>/dev/null || true
    [ -f "$ROOT_DIR/.frontend.pid" ] && kill "$(cat "$ROOT_DIR/.frontend.pid")" 2>/dev/null || true
    docker compose -f infra/docker-compose.yml down 2>/dev/null || true
    rm -f "$ROOT_DIR/.backend.pid" "$ROOT_DIR/.frontend.pid"
    info "已停止"
    ;;

  logs)
    info "实时日志（Ctrl+C 退出）"
    tail -f logs/backend.log logs/frontend.log 2>/dev/null || true
    ;;

  clean)
    info "清理临时数据"
    rm -rf backend/data/projects/* backend/data/experience_db/* logs/*
    info "已清理"
    ;;

  *)
    echo "用法：$0 {dev|prod|stop|logs|clean}"
    echo ""
    echo "  dev   - 本地开发模式（uvicorn + vite）"
    echo "  prod  - Docker Compose 部署"
    echo "  stop  - 停止所有服务"
    echo "  logs  - 实时日志"
    echo "  clean - 清理生成数据"
    exit 1
    ;;
esac
