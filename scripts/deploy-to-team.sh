#!/usr/bin/env bash
# ============================================================
# 樱花小队 → team.041126.xyz 部署脚本
# 目标服务器: 47.103.96.182 (公) / 172.24.21.218 (私)
# 域名: team.041126.xyz
# ============================================================
set -euo pipefail

# ===== 配置 =====
SERVER_IP="47.103.96.182"
SERVER_IP_PRIVATE="172.24.21.218"
DOMAIN="team.041126.xyz"
SSH_USER="${SSH_USER:-root}"
SSH_PORT="${SSH_PORT:-22}"
SSH_KEY="${SSH_KEY:-}"  # 如 ~/.ssh/id_rsa,留空则用默认
INSTALL_DIR="/opt/SakuraAgentTeam"
REPO_URL="https://github.com/wanan3847/SakuraAgentTeam.git"

# 颜色
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

echo -e "${BLUE}🌸 樱花小队 → ${DOMAIN} 部署脚本${NC}"
echo -e "${BLUE}   服务器: ${SERVER_IP} (SSH ${SSH_USER}@${SERVER_IP}:${SSH_PORT})${NC}"
echo -e "${BLUE}   安装目录: ${INSTALL_DIR}${NC}"
echo ""

# ===== SSH 命令封装 =====
SSH_OPTS="-o StrictHostKeyChecking=accept-new -o ConnectTimeout=10"
if [ -n "$SSH_KEY" ]; then
    SSH_OPTS="$SSH_OPTS -i $SSH_KEY"
fi
SSH_CMD="ssh $SSH_OPTS -p $SSH_PORT ${SSH_USER}@${SERVER_IP}"
SCP_CMD="scp $SSH_OPTS -P $SSH_PORT"

# ===== 1. 检查 SSH 连接 =====
echo -e "${YELLOW}[1/8] 检查 SSH 连接...${NC}"
if $SSH_CMD "echo ok" 2>/dev/null | grep -q "ok"; then
    echo -e "${GREEN}  ✓ SSH 连接成功${NC}"
else
    echo -e "${RED}  ✗ SSH 连接失败${NC}"
    echo -e "    请检查:"
    echo -e "    1. 服务器 IP ${SERVER_IP} 是否可达"
    echo -e "    2. SSH 用户 ${SSH_USER} 是否正确"
    echo -e "    3. SSH 密钥是否配置(如需指定: SSH_KEY=~/.ssh/id_rsa $0)"
    echo -e "    4. 端口 ${SSH_PORT} 是否开放"
    exit 1
fi

# ===== 2. 安装 Docker =====
echo ""
echo -e "${YELLOW}[2/8] 检查 Docker...${NC}"
if $SSH_CMD "command -v docker &>/dev/null && docker --version" 2>/dev/null; then
    echo -e "${GREEN}  ✓ Docker 已安装${NC}"
else
    echo -e "${YELLOW}  Docker 未安装,开始安装...${NC}"
    $SSH_CMD "curl -fsSL https://get.docker.com | sh" 2>&1 | tail -5 | sed 's/^/    /'
    $SSH_CMD "systemctl enable docker && systemctl start docker" 2>&1 | sed 's/^/    /'
    echo -e "${GREEN}  ✓ Docker 安装完成${NC}"
fi

# 检查 docker compose
echo -e "${YELLOW}  检查 docker compose...${NC}"
if $SSH_CMD "docker compose version" 2>/dev/null; then
    echo -e "${GREEN}  ✓ docker compose 可用${NC}"
else
    echo -e "${RED}  ✗ docker compose 不可用,请手动安装${NC}"
    exit 1
fi

# ===== 3. 安装 Nginx =====
echo ""
echo -e "${YELLOW}[3/8] 检查 Nginx...${NC}"
if $SSH_CMD "command -v nginx &>/dev/null && nginx -v" 2>/dev/null; then
    echo -e "${GREEN}  ✓ Nginx 已安装${NC}"
else
    echo -e "${YELLOW}  Nginx 未安装,开始安装...${NC}"
    $SSH_CMD "apt-get update -qq && apt-get install -y -qq nginx" 2>&1 | tail -3 | sed 's/^/    /'
    $SSH_CMD "systemctl enable nginx && systemctl start nginx" 2>&1 | sed 's/^/    /'
    echo -e "${GREEN}  ✓ Nginx 安装完成${NC}"
fi

# ===== 4. 克隆 / 更新代码 =====
echo ""
echo -e "${YELLOW}[4/8] 克隆 / 更新代码...${NC}"
if $SSH_CMD "test -d ${INSTALL_DIR}/.git" 2>/dev/null; then
    echo -e "${YELLOW}  代码已存在,拉取最新...${NC}"
    $SSH_CMD "cd ${INSTALL_DIR} && git pull origin main" 2>&1 | sed 's/^/    /'
else
    echo -e "${YELLOW}  首次部署,克隆仓库...${NC}"
    $SSH_CMD "mkdir -p $(dirname ${INSTALL_DIR}) && git clone --depth 1 ${REPO_URL} ${INSTALL_DIR}" 2>&1 | sed 's/^/    /'
fi
echo -e "${GREEN}  ✓ 代码就绪${NC}"

# ===== 5. 配置 .env =====
echo ""
echo -e "${YELLOW}[5/8] 配置 .env...${NC}"
$SSH_CMD "test -f ${INSTALL_DIR}/backend/.env" 2>/dev/null && {
    echo -e "${GREEN}  ✓ .env 已存在(跳过)${NC}"
} || {
    echo -e "${YELLOW}  生成 .env...${NC}"
    $SSH_CMD "cp ${INSTALL_DIR}/backend/.env.example ${INSTALL_DIR}/backend/.env"
    SECRET=$($SSH_CMD "python3 -c 'import secrets; print(secrets.token_hex(32))' 2>/dev/null || openssl rand -hex 32")
    $SSH_CMD "sed -i 's/^SECRET_KEY=.*/SECRET_KEY=${SECRET}/' ${INSTALL_DIR}/backend/.env"
    echo -e "${GREEN}  ✓ .env 已生成${NC}"
    echo -e "${YELLOW}  ⚠ 请编辑 ${INSTALL_DIR}/backend/.env 填入 OPENAI_API_KEY${NC}"
}

# ===== 6. 启动 Docker =====
echo ""
echo -e "${YELLOW}[6/8] 启动 Docker 服务...${NC}"
$SSH_CMD "cd ${INSTALL_DIR} && docker compose -f infra/docker-compose.yml up -d --build" 2>&1 | tail -10 | sed 's/^/    /'
echo -e "${GREEN}  ✓ Docker 服务已启动${NC}"

# 等待后端健康检查
echo -e "${YELLOW}  等待后端启动...${NC}"
for i in $(seq 1 30); do
    if $SSH_CMD "curl -sf http://localhost:8000/health" 2>/dev/null | grep -q "healthy"; then
        echo -e "${GREEN}  ✓ 后端健康检查通过${NC}"
        break
    fi
    sleep 2
    [ $i -eq 30 ] && {
        echo -e "${RED}  ✗ 后端启动超时${NC}"
        echo -e "    查看日志: $SSH_CMD 'docker compose -f ${INSTALL_DIR}/infra/docker-compose.yml logs backend'"
        exit 1
    }
done

# ===== 7. 配置 Nginx 反代 =====
echo ""
echo -e "${YELLOW}[7/8] 配置 Nginx 反代...${NC}"
# 上传 nginx 配置
$SCP_CMD infra/nginx-sakura.conf ${SSH_USER}@${SERVER_IP}:/etc/nginx/sites-available/sakura 2>&1 | sed 's/^/    /'
# 替换域名
$SSH_CMD "sed -i 's/sakura.yourdomain.com/${DOMAIN}/g' /etc/nginx/sites-available/sakura"
$SSH_CMD "ln -sf /etc/nginx/sites-available/sakura /etc/nginx/sites-enabled/sakura"
$SSH_CMD "rm -f /etc/nginx/sites-enabled/default"
$SSH_CMD "nginx -t" 2>&1 | sed 's/^/    /'
$SSH_CMD "systemctl reload nginx" 2>&1 | sed 's/^/    /'
echo -e "${GREEN}  ✓ Nginx 反代已配置${NC}"

# ===== 8. 申请 HTTPS 证书 =====
echo ""
echo -e "${YELLOW}[8/8] 申请 HTTPS 证书...${NC}"
if $SSH_CMD "command -v certbot &>/dev/null" 2>/dev/null; then
    echo -e "${GREEN}  ✓ certbot 已安装${NC}"
else
    echo -e "${YELLOW}  安装 certbot...${NC}"
    $SSH_CMD "apt-get install -y -qq certbot python3-certbot-nginx" 2>&1 | tail -3 | sed 's/^/    /'
fi

echo -e "${YELLOW}  申请证书(可能需要确认)...${NC}"
$SSH_CMD "certbot --nginx -d ${DOMAIN} --non-interactive --agree-tos -m admin@${DOMAIN} --redirect || echo 'certbot failed, please run manually: certbot --nginx -d ${DOMAIN}'" 2>&1 | tail -10 | sed 's/^/    /'
echo -e "${GREEN}  ✓ HTTPS 证书已申请${NC}"

# ===== 完成 =====
echo ""
echo -e "${BLUE}============================================================${NC}"
echo -e "${GREEN}🌸 部署完成!${NC}"
echo -e "${BLUE}============================================================${NC}"
echo ""
echo -e "访问地址:"
echo -e "  前端:   ${GREEN}https://${DOMAIN}${NC}"
echo -e "  后端:   ${GREEN}https://${DOMAIN}/api/v1/docs${NC}"
echo -e "  健康:   ${GREEN}https://${DOMAIN}/api/v1/health${NC}"
echo ""
echo -e "服务器信息:"
echo -e "  公网 IP: ${SERVER_IP}"
echo -e "  私网 IP: ${SERVER_IP_PRIVATE}"
echo -e "  SSH:     ${SSH_USER}@${SERVER_IP} -p ${SSH_PORT}"
echo -e "  目录:    ${INSTALL_DIR}"
echo ""
echo -e "常用命令:"
echo -e "  查看日志:   $SSH_CMD 'cd ${INSTALL_DIR} && docker compose -f infra/docker-compose.yml logs -f'"
echo -e "  重启服务:   $SSH_CMD 'cd ${INSTALL_DIR} && docker compose -f infra/docker-compose.yml restart'"
echo -e "  更新代码:   $SSH_CMD 'cd ${INSTALL_DIR} && git pull && docker compose -f infra/docker-compose.yml up -d --build'"
echo -e "  编辑配置:   $SSH_CMD 'vim ${INSTALL_DIR}/backend/.env'"
echo ""
echo -e "${BLUE}🌸 Just say it. 你的 AI 虚拟团队。${NC}"
