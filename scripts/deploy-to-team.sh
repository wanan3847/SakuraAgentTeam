#!/usr/bin/env bash
# ============================================================
# 樱花小队 → team.041126.xyz 部署脚本
# 目标服务器: 47.103.96.182 (公) / 172.24.21.218 (私)
# 域名: team.041126.xyz
# ============================================================
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ===== 配置 =====
SERVER_IP="47.103.96.182"
SERVER_IP_PRIVATE="172.24.21.218"
DOMAIN="team.041126.xyz"
SSH_USER="${SSH_USER:-root}"
SSH_PORT="${SSH_PORT:-22}"
SSH_KEY="${SSH_KEY:-}"  # 如 ~/.ssh/id_rsa,留空则用默认
SSH_PASSWORD="${SSH_PASSWORD:-}"  # 如 Hw149632，使用密码登录时填写
INSTALL_DIR="/opt/SakuraAgentTeam"
REPO_URL="https://github.com/wanan3847/SakuraAgentTeam.git"
NGINX_CONF="/etc/nginx/conf.d/team.041126.xyz.conf"

# 颜色
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

echo -e "${BLUE}🌸 樱花小队 → ${DOMAIN} 部署脚本${NC}"
echo -e "${BLUE}   服务器: ${SERVER_IP} (SSH ${SSH_USER}@${SERVER_IP}:${SSH_PORT})${NC}"
echo -e "${BLUE}   安装目录: ${INSTALL_DIR}${NC}"
echo ""

# ===== SSH 命令封装 =====
SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=10"
if [ -n "$SSH_KEY" ]; then
    SSH_OPTS="$SSH_OPTS -i $SSH_KEY"
fi
run_ssh() {
    local cmd="$1"
    if [ -n "$SSH_PASSWORD" ]; then
        env SSHPASS="$SSH_PASSWORD" sshpass -e ssh $SSH_OPTS -p "$SSH_PORT" "${SSH_USER}@${SERVER_IP}" "$cmd"
    else
        ssh $SSH_OPTS -p "$SSH_PORT" "${SSH_USER}@${SERVER_IP}" "$cmd"
    fi
}

run_scp() {
    local src="$1"
    local dest="$2"
    if [ -n "$SSH_PASSWORD" ]; then
        env SSHPASS="$SSH_PASSWORD" sshpass -e scp $SSH_OPTS -P "$SSH_PORT" "$src" "${SSH_USER}@${SERVER_IP}:$dest"
    else
        scp $SSH_OPTS -P "$SSH_PORT" "$src" "${SSH_USER}@${SERVER_IP}:$dest"
    fi
}

# ===== 1. 检查 SSH 连接 =====
echo -e "${YELLOW}[1/8] 检查 SSH 连接...${NC}"
if run_ssh 'echo ok' 2>/dev/null | grep -q 'ok'; then
    echo -e "${GREEN}  ✓ SSH 连接成功${NC}"
else
    echo -e "${RED}  ✗ SSH 连接失败${NC}"
    echo -e "    请检查:"
    echo -e "    1. 服务器 IP ${SERVER_IP} 是否可达"
    echo -e "    2. SSH 用户 ${SSH_USER} 是否正确"
    if [ -n "$SSH_PASSWORD" ]; then
        echo -e "    3. SSH 密码是否正确"
    else
        echo -e "    3. SSH 密钥是否配置(如需指定: SSH_KEY=~/.ssh/id_rsa $0)"
    fi
    echo -e "    4. 端口 ${SSH_PORT} 是否开放"
    exit 1
fi

# ===== 2. 安装 Docker =====
echo ""
echo -e "${YELLOW}[2/8] 检查 Docker...${NC}"
if run_ssh "command -v docker &>/dev/null && docker --version" 2>/dev/null; then
    echo -e "${GREEN}  ✓ Docker 已安装${NC}"
else
    echo -e "${YELLOW}  Docker 未安装,开始安装...${NC}"
    run_ssh "curl -fsSL https://get.docker.com | sh" 2>&1 | tail -5 | sed 's/^/    /'
    run_ssh "systemctl enable docker && systemctl start docker" 2>&1 | sed 's/^/    /'
    echo -e "${GREEN}  ✓ Docker 安装完成${NC}"
fi

# 检查 docker compose
echo -e "${YELLOW}  检查 docker compose...${NC}"
if run_ssh "docker compose version" 2>/dev/null; then
    echo -e "${GREEN}  ✓ docker compose 可用${NC}"
else
    echo -e "${RED}  ✗ docker compose 不可用,请手动安装${NC}"
    exit 1
fi

# ===== 3. 安装 Nginx =====
echo ""
echo -e "${YELLOW}[3/8] 检查 Nginx...${NC}"
if run_ssh "command -v nginx &>/dev/null && nginx -v" 2>/dev/null; then
    echo -e "${GREEN}  ✓ Nginx 已安装${NC}"
else
    echo -e "${YELLOW}  Nginx 未安装,开始安装...${NC}"
    run_ssh "apt-get update -qq && apt-get install -y -qq nginx" 2>&1 | tail -3 | sed 's/^/    /'
    run_ssh "systemctl enable nginx && systemctl start nginx" 2>&1 | sed 's/^/    /'
    echo -e "${GREEN}  ✓ Nginx 安装完成${NC}"
fi

# ===== 4. 上传 / 更新代码 =====
echo ""
echo -e "${YELLOW}[4/8] 上传 / 更新代码...${NC}"
if run_ssh "test -d ${INSTALL_DIR}/.git" 2>/dev/null; then
    echo -e "${YELLOW}  代码已存在,拉取最新...${NC}"
    run_ssh "cd ${INSTALL_DIR} && git pull origin main" 2>&1 | sed 's/^/    /'
else
    echo -e "${YELLOW}  远端不是 git 工作区，优先尝试 GitHub 克隆...${NC}"
    if run_ssh "mkdir -p $(dirname ${INSTALL_DIR}) && git clone --depth 1 ${REPO_URL} ${INSTALL_DIR}" 2>&1 | sed 's/^/    /'; then
        echo -e "${GREEN}  ✓ 代码已通过 GitHub 克隆${NC}"
    else
        echo -e "${YELLOW}  GitHub 拉取失败或目录已存在，改用本地仓库压缩包上传...${NC}"
        TAR_FILE="/tmp/SakuraAgentTeam.tar.gz"
        COPYFILE_DISABLE=1 tar -czf "$TAR_FILE" \
            --exclude '.git' \
            --exclude '.DS_Store' \
            --exclude '._*' \
            --exclude 'node_modules' \
            --exclude './node_modules' \
            --exclude 'frontend/node_modules' \
            --exclude './frontend/node_modules' \
            --exclude 'backend/.env' \
            --exclude './backend/.env' \
            --exclude 'backend/.venv' \
            --exclude './backend/.venv' \
            --exclude 'backend/build' \
            --exclude './backend/build' \
            --exclude 'backend/dist' \
            --exclude './backend/dist' \
            --exclude 'backend/data' \
            --exclude './backend/data' \
            --exclude 'frontend/dist' \
            --exclude './frontend/dist' \
            --exclude 'backend/htmlcov' \
            --exclude './backend/htmlcov' \
            --exclude '.pytest_cache' \
            --exclude './backend/.pytest_cache' \
            --exclude '.ruff_cache' \
            --exclude './backend/.ruff_cache' \
            -C "$ROOT_DIR" \
            backend frontend infra scripts docs README.md CHANGELOG.md CONTRIBUTING.md LICENSE deploy.sh
        run_scp "$TAR_FILE" /tmp/SakuraAgentTeam.tar.gz
        rm -f "$TAR_FILE"
        run_ssh "mkdir -p ${INSTALL_DIR} && tar -xzf /tmp/SakuraAgentTeam.tar.gz -C ${INSTALL_DIR} && find ${INSTALL_DIR} -name '.DS_Store' -o -name '._*' | xargs -r rm -f && rm -f /tmp/SakuraAgentTeam.tar.gz"
        echo -e "${GREEN}  ✓ 代码已从本地压缩包部署${NC}"
    fi
fi
echo -e "${GREEN}  ✓ 代码就绪${NC}"

# ===== 5. 配置 .env =====
echo ""
echo -e "${YELLOW}[5/8] 配置 .env...${NC}"
run_ssh "test -f ${INSTALL_DIR}/backend/.env" 2>/dev/null && {
    echo -e "${GREEN}  ✓ .env 已存在(跳过)${NC}"
} || {
    echo -e "${YELLOW}  生成 .env...${NC}"
    run_ssh "cp ${INSTALL_DIR}/backend/.env.example ${INSTALL_DIR}/backend/.env"
    SECRET=$(run_ssh "python3 -c 'import secrets; print(secrets.token_hex(32))' 2>/dev/null || openssl rand -hex 32")
    run_ssh "sed -i 's/^SECRET_KEY=.*/SECRET_KEY=${SECRET}/' ${INSTALL_DIR}/backend/.env"
    run_ssh "grep -q '^CORS_ALLOW_ORIGINS=' ${INSTALL_DIR}/backend/.env || echo 'CORS_ALLOW_ORIGINS=http://${DOMAIN},https://${DOMAIN}' >> ${INSTALL_DIR}/backend/.env"
    echo -e "${GREEN}  ✓ .env 已生成${NC}"
    echo -e "${YELLOW}  ⚠ 请编辑 ${INSTALL_DIR}/backend/.env 填入 OPENAI_API_KEY${NC}"
}

# ===== 6. 构建前端并启动后端（PM2） =====
echo ""
echo -e "${YELLOW}[6/8] 构建前端并启动后端...${NC}"
run_ssh "command -v python3.11 >/dev/null || dnf install -y python3.11 python3.11-pip" 2>&1 | tail -8 | sed 's/^/    /'
run_ssh "cd ${INSTALL_DIR}/backend && python3.11 -m venv .venv-linux && . .venv-linux/bin/activate && pip install --timeout 120 --retries 3 -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com fastapi 'uvicorn[standard]' pydantic pydantic-settings python-dotenv openai anthropic litellm httpx aiofiles sqlalchemy aiosqlite gitpython docker structlog typer rich pypdf beautifulsoup4 python-multipart PyJWT 'passlib[bcrypt]' 'bcrypt==4.0.1'" 2>&1 | tail -20 | sed 's/^/    /'
run_ssh "cd ${INSTALL_DIR}/frontend && npm ci && npm run build" 2>&1 | tail -20 | sed 's/^/    /'
run_ssh "pm2 delete sakura-team-backend 2>/dev/null || true; cd ${INSTALL_DIR}/backend && set -a && . ./.env && set +a && pm2 start .venv-linux/bin/uvicorn --name sakura-team-backend --interpreter none -- app.api.main:app --host 127.0.0.1 --port 8000 && pm2 save" 2>&1 | tail -20 | sed 's/^/    /'
echo -e "${GREEN}  ✓ 前后端服务已启动${NC}"

# 等待后端健康检查
echo -e "${YELLOW}  等待后端启动...${NC}"
for i in $(seq 1 30); do
    if run_ssh "curl -sf http://localhost:8000/health" 2>/dev/null | grep -q "healthy"; then
        echo -e "${GREEN}  ✓ 后端健康检查通过${NC}"
        break
    fi
    sleep 2
    [ $i -eq 30 ] && {
        echo -e "${RED}  ✗ 后端启动超时${NC}"
        echo -e "    查看日志: pm2 logs sakura-team-backend"
        exit 1
    }
done

# ===== 7. 配置 Nginx 反代 =====
echo ""
echo -e "${YELLOW}[7/8] 配置 Nginx 反代...${NC}"
run_scp infra/nginx-sakura.conf "${NGINX_CONF}" 2>&1 | sed 's/^/    /'
run_ssh "rm -f /etc/nginx/sites-enabled/sakura /etc/nginx/sites-available/sakura /etc/nginx/sites-enabled/default"
run_ssh "nginx -t" 2>&1 | sed 's/^/    /'
run_ssh "systemctl reload nginx" 2>&1 | sed 's/^/    /'
echo -e "${GREEN}  ✓ Nginx 反代已配置${NC}"

# ===== 8. 验证访问 =====
echo ""
echo -e "${YELLOW}[8/8] 验证访问...${NC}"
run_ssh "curl -sS -I --max-time 10 http://127.0.0.1/ -H 'Host: ${DOMAIN}' | sed -n '1,12p'" 2>&1 | sed 's/^/    /'
echo -e "${GREEN}  ✓ 本机 HTTP 验证完成${NC}"

# ===== 完成 =====
echo ""
echo -e "${BLUE}============================================================${NC}"
echo -e "${GREEN}🌸 部署完成!${NC}"
echo -e "${BLUE}============================================================${NC}"
echo ""
echo -e "访问地址:"
echo -e "  前端:   ${GREEN}http://${DOMAIN}${NC}"
echo -e "  后端:   ${GREEN}http://${DOMAIN}/api/v1/docs${NC}"
echo -e "  健康:   ${GREEN}http://${DOMAIN}/health${NC}"
echo ""
echo -e "服务器信息:"
echo -e "  公网 IP: ${SERVER_IP}"
echo -e "  私网 IP: ${SERVER_IP_PRIVATE}"
echo -e "  SSH:     ${SSH_USER}@${SERVER_IP} -p ${SSH_PORT}"
echo -e "  目录:    ${INSTALL_DIR}"
echo ""
echo -e "常用命令:"
echo -e "  查看日志:   pm2 logs sakura-team-backend"
echo -e "  重启服务:   pm2 restart sakura-team-backend"
echo -e "  更新代码:   SSH_PASSWORD='***' scripts/deploy-to-team.sh"
echo -e "  编辑配置:   run_ssh 'vim ${INSTALL_DIR}/backend/.env'"
echo ""
echo -e "${BLUE}🌸 Just say it. 你的 AI 虚拟团队。${NC}"
