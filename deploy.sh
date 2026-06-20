#!/usr/bin/env bash
# SakuraAgentTeam 一键部署
#
# 用法: ./deploy.sh {dev|prod|sandbox|stop|logs|clean}
# - dev      本地开发（uvicorn --reload + vite dev）
# - prod     Docker 容器（后端 + 前端，持续运行）
# - sandbox  构建 Agent 沙箱镜像
# - stop     停止所有
# - logs     查看 Docker 日志
# - clean    清理数据/镜像

set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"
COMPOSE_FILE="infra/docker-compose.yml"

# ---- colors ----
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { printf "${GREEN}[deploy]${NC} %s\n" "$*"; }
warn()  { printf "${YELLOW}[warn]${NC} %s\n" "$*"; }
error() { printf "${RED}[error]${NC} %s\n" "$*"; exit 1; }

# ---- preflight ----
check_docker() {
  command -v docker >/dev/null 2>&1 || error "docker 未安装：https://docs.docker.com/get-docker/"
  docker info >/dev/null 2>&1 || error "docker daemon 未运行，启动 Docker Desktop 即可"
}

check_deps() {
  command -v python3 >/dev/null 2>&1 || error "python3 未安装"
  command -v node    >/dev/null 2>&1 || error "node 未安装"
}

load_env() {
  if [ ! -f "backend/.env" ]; then
    if [ -f "backend/.env.example" ]; then
      cp backend/.env.example backend/.env
      warn "backend/.env 不存在，已从 .env.example 复制（请填入真实 LLM Key）"
    fi
  fi
}

# ---- dev 模式 ----
cmd_dev() {
  info "启动开发模式（本地 uvicorn + vite）"
  check_deps
  load_env
  mkdir -p logs

  # 后端：system Python 优先 / venv fallback / uv 装
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
  info "后端 PID: $BACKEND_PID"

  if [ ! -d "frontend/node_modules" ]; then
    info "安装前端依赖"
    (cd frontend && npm install)
  fi
  info "启动前端 http://localhost:5173"
  (cd frontend && nohup npm run dev > "$ROOT_DIR/logs/frontend.log" 2>&1 &)
  sleep 3
  info "✅ 已启动"
  info "   前端：http://localhost:5173"
  info "   后端 API：http://localhost:8000/docs"
  info "   停止：./deploy.sh stop"
}

# ---- prod 模式（Docker 持续运行） ----
cmd_prod() {
  check_docker
  load_env
  info "启动生产模式（Docker Compose）— 持续运行，浏览器开 http://localhost:8080"
  docker compose -f "$COMPOSE_FILE" up -d --build
  sleep 5
  info "后端 health: $(curl -sS http://localhost:8000/health 2>/dev/null || echo 启动中...)"
  echo
  info "✅ 已启动（容器持续运行，重启电脑后用 ./deploy.sh prod 重新拉起）"
  info "   前端：http://localhost:8080"
  info "   后端 API：http://localhost:8000/docs"
  info "   停止：./deploy.sh stop"
  info "   日志：./deploy.sh logs"
}

# ---- sandbox ----
cmd_sandbox() {
  check_docker
  info "构建 Agent 沙箱镜像（agent 跑代码用）"
  docker build -f infra/docker/sandbox.Dockerfile -t sakura-sandbox:latest .
  info "✅ 镜像构建完成：sakura-sandbox:latest"
}

# ---- stop ----
cmd_stop() {
  if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    docker compose -f "$COMPOSE_FILE" down 2>/dev/null || true
  fi
  if [ -f .backend.pid ]; then
    kill "$(cat .backend.pid)" 2>/dev/null || true
    rm -f .backend.pid
  fi
  if [ -f .frontend.pid ]; then
    kill "$(cat .frontend.pid)" 2>/dev/null || true
    rm -f .frontend.pid
  fi
  pkill -f "uvicorn app.api" 2>/dev/null || true
  pkill -f "vite" 2>/dev/null || true
  info "✅ 已停止"
}

# ---- logs ----
cmd_logs() {
  check_docker
  docker compose -f "$COMPOSE_FILE" logs -f --tail=100
}

# ---- clean ----
cmd_clean() {
  check_docker
  warn "清理数据目录、构建产物、停止容器"
  docker compose -f "$COMPOSE_FILE" down -v 2>/dev/null || true
  rm -rf backend/data/* frontend/dist .backend.pid .frontend.pid
  info "✅ 清理完成"
}

# ---- dispatch ----
case "${1:-dev}" in
  dev)     cmd_dev ;;
  prod)    cmd_prod ;;
  sandbox) cmd_sandbox ;;
  stop)    cmd_stop ;;
  logs)    cmd_logs ;;
  clean)   cmd_clean ;;
  *)
    cat <<EOF
用法: $0 {dev|prod|sandbox|stop|logs|clean}

  dev      本地开发（uvicorn --reload + vite dev）
  prod     Docker 容器（后端 + 前端，持续运行）★ 推荐
  sandbox  构建 Agent 沙箱镜像
  stop     停止所有
  logs     查看 Docker 日志
  clean    清理数据/镜像
EOF
    exit 1
    ;;
esac
