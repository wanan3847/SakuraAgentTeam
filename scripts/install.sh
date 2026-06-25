#!/usr/bin/env bash
# ============================================================
# 樱花小队 (SakuraAgentTeam) 一键安装脚本
# 适用:macOS / Linux / Windows (Git Bash / WSL)
# 用法:curl -fsSL https://raw.githubusercontent.com/wanan3847/SakuraAgentTeam/main/scripts/install.sh | bash
# ============================================================
set -euo pipefail

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置
REPO_URL="https://github.com/wanan3847/SakuraAgentTeam.git"
INSTALL_DIR="${INSTALL_DIR:-$HOME/SakuraAgentTeam}"
BRANCH="main"

echo -e "${BLUE}🌸 樱花小队 (SakuraAgentTeam) 一键安装脚本${NC}"
echo -e "${BLUE}   安装目录: ${INSTALL_DIR}${NC}"
echo ""

# ============================================================
# 1. 检查依赖
# ============================================================
echo -e "${YELLOW}[1/6] 检查依赖...${NC}"

check_command() {
    if ! command -v "$1" &> /dev/null; then
        echo -e "${RED}  ✗ 未找到 $1,请先安装${NC}"
        echo -e "    $2"
        exit 1
    fi
    echo -e "${GREEN}  ✓ $1 ($($1 --version 2>&1 | head -1))${NC}"
}

check_command git "  参考: https://git-scm.com/downloads"
check_command python3 "  参考: https://www.python.org/downloads/"
check_command node "  参考: https://nodejs.org/"

# 检查 Python 版本 >= 3.11
PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "0.0")
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]); then
    echo -e "${RED}  ✗ Python 版本过低 ($PY_VERSION),需要 3.11+${NC}"
    exit 1
fi
echo -e "${GREEN}  ✓ Python $PY_VERSION (>= 3.11)${NC}"

# 检查 Node 版本 >= 18
NODE_VERSION=$(node --version 2>/dev/null | sed 's/v//' | cut -d. -f1)
if [ "$NODE_VERSION" -lt 18 ]; then
    echo -e "${RED}  ✗ Node 版本过低 (v$NODE_VERSION),需要 18+${NC}"
    exit 1
fi
echo -e "${GREEN}  ✓ Node v$NODE_VERSION (>= 18)${NC}"

# ============================================================
# 2. 克隆仓库
# ============================================================
echo ""
echo -e "${YELLOW}[2/6] 克隆仓库...${NC}"

if [ -d "$INSTALL_DIR/.git" ]; then
    echo -e "${YELLOW}  目录已存在,拉取最新代码...${NC}"
    cd "$INSTALL_DIR"
    git pull origin "$BRANCH" 2>&1 | sed 's/^/    /'
else
    git clone --depth 1 -b "$BRANCH" "$REPO_URL" "$INSTALL_DIR" 2>&1 | sed 's/^/    /'
    cd "$INSTALL_DIR"
fi
echo -e "${GREEN}  ✓ 代码已就绪${NC}"

# ============================================================
# 3. 安装后端依赖
# ============================================================
echo ""
echo -e "${YELLOW}[3/6] 安装后端依赖 (Python)...${NC}"

# 创建虚拟环境
if [ ! -d "backend/.venv" ]; then
    python3 -m venv backend/.venv
    echo -e "${GREEN}  ✓ 创建虚拟环境${NC}"
fi

# 激活虚拟环境
source backend/.venv/bin/activate

# 升级 pip
pip install --upgrade pip 2>&1 | tail -1 | sed 's/^/    /'

# 安装依赖
if [ -f "backend/requirements.txt" ]; then
    pip install -r backend/requirements.txt 2>&1 | tail -3 | sed 's/^/    /'
elif [ -f "backend/pyproject.toml" ]; then
    pip install -e backend/ 2>&1 | tail -3 | sed 's/^/    /'
fi
echo -e "${GREEN}  ✓ 后端依赖已安装${NC}"

# ============================================================
# 4. 安装前端依赖
# ============================================================
echo ""
echo -e "${YELLOW}[4/6] 安装前端依赖 (Node)...${NC}"

cd frontend
if [ ! -d "node_modules" ]; then
    npm install 2>&1 | tail -5 | sed 's/^/    /'
else
    npm install 2>&1 | tail -2 | sed 's/^/    /'
fi
echo -e "${GREEN}  ✓ 前端依赖已安装${NC}"
cd ..

# ============================================================
# 5. 配置 .env
# ============================================================
echo ""
echo -e "${YELLOW}[5/6] 配置环境变量...${NC}"

if [ ! -f "backend/.env" ]; then
    cp backend/.env.example backend/.env
    # 生成随机 SECRET_KEY
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    sed -i.bak "s/^SECRET_KEY=.*/SECRET_KEY=${SECRET_KEY}/" backend/.env
    rm -f backend/.env.bak 2>/dev/null || true
    echo -e "${GREEN}  ✓ 已生成 backend/.env (SECRET_KEY 已自动生成)${NC}"
    echo -e "${YELLOW}  ⚠ 请编辑 backend/.env 填入 OPENAI_API_KEY${NC}"
else
    echo -e "${GREEN}  ✓ backend/.env 已存在${NC}"
fi

# ============================================================
# 6. 完成
# ============================================================
echo ""
echo -e "${BLUE}============================================================${NC}"
echo -e "${GREEN}🌸 安装完成!${NC}"
echo -e "${BLUE}============================================================${NC}"
echo ""
echo -e "下一步:"
echo -e "  1. 编辑配置:  ${YELLOW}vim ${INSTALL_DIR}/backend/.env${NC}"
echo -e "  2. 启动开发:  ${YELLOW}cd ${INSTALL_DIR} && ./deploy.sh dev${NC}"
echo -e "  3. 启动生产:  ${YELLOW}cd ${INSTALL_DIR} && ./deploy.sh prod${NC}"
echo ""
echo -e "文档:"
echo -e "  - 安装: https://github.com/wanan3847/SakuraAgentTeam#readme"
echo -e "  - 部署: ${INSTALL_DIR}/docs/DEPLOY.md"
echo -e "  - CLI:  ${INSTALL_DIR}/docs/CLI.md"
echo ""
echo -e "${BLUE}🌸 Just say it. 你的 AI 虚拟团队。${NC}"
