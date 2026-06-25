# 部署指南 — Production Deployment

> 把樱花小队部署到一台 Linux 服务器上，对外提供 HTTPS 域名访问。
> 适合 2-4 核 / 4GB+ RAM 的 VPS（带宽 2Mbps+）。

---

## 0. 目录

1. [前置准备](#1-前置准备)
2. [5 分钟 Docker 部署](#2-5-分钟-docker-部署)
3. [域名 + HTTPS（Nginx + Let's Encrypt）](#3-域名--httpsnginx--lets-encrypt)
4. [环境变量与密钥管理](#4-环境变量与密钥管理)
5. [数据持久化与备份](#5-数据持久化与备份)
6. [升级与回滚](#6-升级与回滚)
7. [监控与日志](#7-监控与日志)
8. [常见问题](#8-常见问题)

---

## 1. 前置准备

| 资源 | 最低 | 推荐 |
|------|------|------|
| CPU  | 2 核 | 4 核 |
| RAM  | 2 GB | 4 GB+ |
| 磁盘 | 10 GB | 40 GB SSD |
| OS   | Ubuntu 22.04 / Debian 12 / CentOS 9 | Ubuntu 24.04 LTS |
| 公网 | 1 Mbps | 5 Mbps+ |
| 域名 | 可选（仅 IP 也行） | 强烈建议，方便上 HTTPS |

安装 Docker：

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER    # 免 sudo
newgrp docker
docker --version                 # 验证
```

> 服务器在国内时，建议配置 Docker Hub 镜像加速（`/etc/docker/daemon.json` 加 `registry-mirrors`）。

---

## 2. 5 分钟 Docker 部署

```bash
# 1) 克隆代码
git clone https://github.com/wanan3847/SakuraAgentTeam.git
cd SakuraAgentTeam

# 2) 准备后端 .env（至少填一个 LLM Key）
cp backend/.env.example backend/.env
vim backend/.env                # 填入 OPENAI_API_KEY 等

# 3) 启动
./deploy.sh prod
```

启动后：

- 前端：<http://your-server-ip:8080>
- 后端：<http://your-server-ip:8000/docs>
- 健康检查：`curl http://localhost:8000/health`

> 默认用项目自带的 `infra/docker-compose.yml`，`backend` + `frontend` 两个服务，`restart: unless-stopped` 自动拉起。

---

## 3. 域名 + HTTPS（Nginx + Let's Encrypt）

### 3.1 反向代理（前置 Nginx）

让 80 / 443 端口收 HTTP(S)，转发到 Docker 的 8080：

```nginx
# /etc/nginx/sites-available/sakura
server {
    listen 80;
    server_name sakura.yourdomain.com;

    client_max_body_size 20M;

    # 上传 SSE 长连接要关 buffering
    proxy_buffering off;
    proxy_read_timeout  300s;
    proxy_send_timeout  300s;

    location / {
        proxy_pass         http://127.0.0.1:8080;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/sakura /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 3.2 申请 HTTPS 证书

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d sakura.yourdomain.com
```

Certbot 会自动加 `listen 443 ssl` + 续期 cron。验证：

```bash
curl -I https://sakura.yourdomain.com
```

### 3.3 强制 HTTPS + HSTS（可选）

在 certbot 生成的 server 块顶部加：

```nginx
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
```

---

## 4. 环境变量与密钥管理

### 4.1 关键环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `OPENAI_API_KEY` | 否（但强烈建议） | OpenAI / 兼容供应商 key |
| `ANTHROPIC_API_KEY` | 否 | Anthropic Claude key |
| `DEFAULT_LLM_PROVIDER` | 否 | `openai` / `anthropic` / `litellm` |
| `DEFAULT_LLM_MODEL`   | 否 | `gpt-4o` / `claude-3-5-sonnet-...` |
| `OPENAI_BASE_URL`     | 否 | 中转站 / DeepSeek 改这里 |
| `LOG_LEVEL`           | 否 | `INFO` / `WARNING` / `ERROR` |
| `CORS_ALLOW_ORIGINS`  | 否 | 生产请改成你的域名，避免 `*` |
| `SECRET_KEY`          | **是** | JWT 签名密钥，`openssl rand -hex 32` 生成 |

> **注意**：所有"用户的 LLM Key"保存在 SQLite 数据库（`backend_data` volume）里，**不**走 `.env`。`.env` 只放系统级共享 key + JWT 签名密钥。

### 4.2 密钥生成

```bash
openssl rand -hex 32    # 写进 backend/.env 的 SECRET_KEY
```

### 4.3 不要提交到 Git

`.gitignore` 已排除 `backend/.env`。CI / 部署机建议用：

- Docker Swarm secrets
- Kubernetes Secret + envFrom
- 阿里云 / AWS Secrets Manager

---

## 5. 数据持久化与备份

### 5.1 关键数据卷

`infra/docker-compose.yml` 声明了：

```yaml
volumes:
  backend_data:
    name: sakura_backend_data
```

包含：

- `data/sakura.db`（SQLite：用户、LLM 配置、提交、历史）
- `data/projects/`（Agent 协作产物）
- `data/experience_db/`（ChromaDB 经验库）
- `data/sessions/`（运行时 session）

### 5.2 备份脚本

```bash
#!/bin/bash
# /opt/backup-sakura.sh
set -e
TS=$(date +%Y%m%d-%H%M%S)
docker run --rm \
  -v sakura_backend_data:/data:ro \
  -v /opt/backups:/backup \
  alpine tar czf /backup/sakura-$TS.tar.gz -C /data .
find /opt/backups -name "sakura-*.tar.gz" -mtime +14 -delete
```

```bash
chmod +x /opt/backup-sakura.sh
# 每天凌晨 3 点跑
echo "0 3 * * * root /opt/backup-sakura.sh" | sudo tee /etc/cron.d/sakura-backup
```

### 5.3 恢复

```bash
docker compose -f infra/docker-compose.yml down
docker run --rm \
  -v sakura_backend_data:/data \
  -v /opt/backups:/backup \
  alpine sh -c "tar xzf /backup/sakura-20260624-030000.tar.gz -C /data"
docker compose -f infra/docker-compose.yml up -d
```

---

## 6. 升级与回滚

### 6.1 升级

```bash
cd /opt/SakuraAgentTeam   # 你的部署目录
git pull origin main
docker compose -f infra/docker-compose.yml up -d --build
```

镜像无破坏性更新时，**数据卷不会丢**；破坏性 schema 变更请先看 CHANGELOG。

### 6.2 回滚

```bash
git log --oneline -10
git checkout <commit-sha>
docker compose -f infra/docker-compose.yml up -d --build
```

数据库 schema 回滚后用上面的"恢复"流程回退数据。

---

## 7. 监控与日志

### 7.1 看日志

```bash
./deploy.sh logs                                  # 实时跟踪
docker compose -f infra/docker-compose.yml logs --tail=200 backend
```

### 7.2 健康检查

```bash
# 后端
curl -fsS http://localhost:8000/health
# 输出示例：{"status":"healthy","app_name":"SakuraAgentTeam","version":"0.1.0"}

# 前端（容器内）
docker exec sakura-frontend wget -qO- http://localhost/ >/dev/null && echo OK
```

### 7.3 加监控（推荐）

- **UptimeRobot / 阿里云云监控**：每分钟 `GET /health`，挂了发邮件 / 钉钉。
- **Prometheus + Grafana**：用 `nginx-prometheus-exporter` 看 HTTP 指标；后端可加 `prometheus-fastapi-instrumentator`。
- **Sentry**：把 `backend/app/core/logging.py` 的 logger 接到 Sentry DSN，前端 `index.html` 引入 `@sentry/browser`。

---

## 8. 常见问题

### Q: 端口被占用？

```bash
sudo lsof -i:8080
sudo lsof -i:8000
# 改 docker-compose.yml 的 ports，或 kill 占用进程
```

### Q: Docker 内存不够？

`backend` 容器默认无限制。如果服务器只有 1-2GB RAM：

```yaml
# docker-compose.yml
services:
  backend:
    deploy:
      resources:
        limits:
          memory: 1G
```

### Q: 502 Bad Gateway？

后端还没起来。检查：

```bash
docker compose -f infra/docker-compose.yml ps
docker compose -f infra/docker-compose.yml logs backend
```

### Q: SSE 一直断？

Nginx 默认 60s 断开长连接。已在 `nginx.conf` 设 `proxy_read_timeout 300s`，反代层要同样设置：

```nginx
proxy_read_timeout  300s;
proxy_send_timeout  300s;
```

### Q: 国内服务器拉 Docker Hub 镜像慢？

`/etc/docker/daemon.json`：

```json
{
  "registry-mirrors": [
    "https://docker.mirrors.ustc.edu.cn",
    "https://hub-mirror.c.163.com"
  ]
}
```

```bash
sudo systemctl restart docker
```

### Q: 想用非 80 端口？

`infra/docker-compose.yml` 把前端 `ports: ["8080:80"]` 改成 `"9000:80"`，再把前置 Nginx `proxy_pass` 改成 `http://127.0.0.1:9000`。

---

## 9. 性能参考

| 指标 | 单机 2C4G 实测 |
|------|-----------------|
| 并发 SSE 连接 | 50+ |
| 单次多 Agent 协作（5 个 Agent，群聊） | 30-90s 取决于 LLM 延迟 |
| 启动到 health=OK | < 25s（含 npm install 一次） |
| 镜像总大小 | backend ~1.2 GB / frontend ~50 MB |
| 内存常驻 | backend ~600 MB / frontend nginx ~10 MB |

> 实际容量取决于：用户的 LLM Key 速率限制、协作复杂度、是否使用 ChromaDB 经验库。

---

## 10. 安全清单

部署到公网前，请确认：

- [ ] `SECRET_KEY` 已改成 `openssl rand -hex 32` 生成的值
- [ ] CORS 限制为你的域名（`main.py` 改 `allow_origins`）
- [ ] `.env` 不在 git 仓库中（已默认排除）
- [ ] 数据库卷定期备份（cron）
- [ ] HTTPS 已启用（Let's Encrypt 自动续期）
- [ ] SSH 改密钥登录，关闭密码登录
- [ ] 防火墙只开 22 / 80 / 443：`sudo ufw allow 22,80,443/tcp`
- [ ] 监控 / 告警已配（UptimeRobot / 阿里云）
- [ ] `docker compose logs` 定期巡检，看有无异常堆栈

---

## 11. 一键脚本（复制即用）

```bash
#!/bin/bash
# install-sakura.sh — 在全新 Ubuntu 22.04+ 服务器上跑
set -e
apt-get update && apt-get install -y curl git nginx certbot python3-certbot-nginx
curl -fsSL https://get.docker.com | sh
usermod -aG docker $SUDO_USER

cd /opt
git clone https://github.com/wanan3847/SakuraAgentTeam.git
cd SakuraAgentTeam
cp backend/.env.example backend/.env
SECRET=$(openssl rand -hex 32)
sed -i "s/^SECRET_KEY=.*/SECRET_KEY=$SECRET/" backend/.env

./deploy.sh prod

# 配 Nginx
cat > /etc/nginx/sites-available/sakura <<'EOF'
server {
    listen 80;
    server_name _;
    client_max_body_size 20M;
    proxy_buffering off;
    proxy_read_timeout  300s;
    proxy_send_timeout  300s;
    location / {
        proxy_pass         http://127.0.0.1:8080;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
    }
}
EOF
ln -sf /etc/nginx/sites-available/sakura /etc/nginx/sites-enabled/sakura
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

echo "✅ 安装完成 → http://$(curl -s ifconfig.me):80"
echo "下一步：sudo certbot --nginx -d your.domain"
```

---

## 12. 反馈

部署过程踩坑？欢迎提 Issue：<https://github.com/wanan3847/SakuraAgentTeam/issues/new?labels=deployment>

页脚 / 教学中心页有"报告 Bug"按钮，一键打开 GitHub Issue（自动附 URL / UA / 时间）。
