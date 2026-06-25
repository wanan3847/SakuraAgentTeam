# 安装指南

> 樱花小队 (SakuraAgentTeam) 支持多种安装方式，选择最适合你的一种。

---

## 目录

1. [pip 安装](#1-pip-安装)
2. [源码安装](#2-源码安装)
3. [macOS 安装包](#3-macos-安装包)
4. [Windows 安装包](#4-windows-安装包)
5. [Docker 安装](#5-docker-安装)
6. [VS Code 插件安装](#6-vs-code-插件安装)

---

## 前置要求

| 依赖 | 版本 | 说明 |
|------|------|------|
| Python | ≥ 3.11 | 后端运行时 |
| Node.js | ≥ 20 | 前端运行时 |
| Git | ≥ 2.40 | 克隆代码 |
| LLM API Key | — | OpenAI / Anthropic / DeepSeek 等任一 |

---

## 1. pip 安装

最简单的方式，一行命令搞定：

```bash
pip install sakura-agent-team
```

安装后即可使用 `sakura` 命令行工具：

```bash
sakura version
sakura config set --api-url http://localhost:8000
```

> pip 包目前包含 CLI 客户端。后端服务仍需从源码启动（见下方源码安装）。

---

## 2. 源码安装

适合开发者和需要自定义配置的用户。

### 2.1 克隆仓库

```bash
git clone https://github.com/wanan3847/SakuraAgentTeam.git
cd SakuraAgentTeam
```

### 2.2 一键脚本（推荐）

**macOS / Linux：**

```bash
./scripts/install.sh
```

**Windows (PowerShell)：**

```powershell
.\scripts\install.ps1
```

脚本会自动创建虚拟环境、安装前后端依赖。

### 2.3 手动安装

**后端：**

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env         # 填入 LLM API Key
```

**前端：**

```bash
cd frontend
npm install
```

### 2.4 启动

```bash
# 一键启动（推荐）
./deploy.sh dev

# 或分别启动
cd backend && python -m uvicorn app.api.main:app --reload --port 8000
cd frontend && npm run dev
```

浏览器访问 <http://localhost:5173>。

---

## 3. macOS 安装包

下载 macOS 安装包（.dmg）：

1. 前往 [GitHub Releases](https://github.com/wanan3847/SakuraAgentTeam/releases)。
2. 下载 `SakuraAgentTeam-x.x.x.dmg`。
3. 双击打开，拖入「应用程序」文件夹。
4. 首次打开时右键 → 「打开」（绕过 Gatekeeper）。

> macOS 安装包内置后端服务，无需额外安装 Python。

---

## 4. Windows 安装包

下载 Windows 安装包（.exe）：

1. 前往 [GitHub Releases](https://github.com/wanan3847/SakuraAgentTeam/releases)。
2. 下载 `SakuraAgentTeam-Setup-x.x.x.exe`。
3. 双击运行安装程序。
4. 安装完成后从开始菜单启动。

> Windows 安装包内置后端服务，无需额外安装 Python。

---

## 5. Docker 安装

适合服务器部署和容器化环境。

### 5.1 前置要求

- Docker ≥ 24
- Docker Compose ≥ 2

### 5.2 启动

```bash
git clone https://github.com/wanan3847/SakuraAgentTeam.git
cd SakuraAgentTeam
cp backend/.env.example backend/.env   # 填入 LLM API Key

# 一键启动
./deploy.sh prod
```

或手动：

```bash
docker compose -f infra/docker-compose.yml up -d --build
```

### 5.3 访问

- 前端：<http://localhost:8080>
- 后端 API：<http://localhost:8000/docs>

### 5.4 管理命令

```bash
./deploy.sh stop     # 停止
./deploy.sh logs     # 查看日志
./deploy.sh clean    # 清理数据与镜像
```

---

## 6. VS Code 插件安装

在 VS Code 中直接使用樱花小队。

### 6.1 从 VSIX 安装

```bash
cd vscode-extension
npm install
npm run package    # 生成 sakura-agent-team-0.1.0.vsix
```

在 VS Code 中：

```
扩展面板 → ⋯ → 从 VSIX 安装 → 选择 .vsix 文件
```

或命令行：

```bash
code --install-extension sakura-agent-team-0.1.0.vsix
```

### 6.2 配置

在 VS Code 设置中搜索 `樱花小队`：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `sakura.serverUrl` | `http://localhost:8000` | 后端 API 地址 |
| `sakura.token` | `""` | JWT 登录 Token |

> 详细使用说明见 [VSCODE_EXTENSION.md](./VSCODE_EXTENSION.md)。

---

## 配置 LLM API Key

无论哪种安装方式，都需要至少一个 LLM API Key 才能运行真实协作。

编辑 `backend/.env`：

```bash
# OpenAI
OPENAI_API_KEY=sk-xxx

# Anthropic
ANTHROPIC_API_KEY=sk-ant-xxx

# DeepSeek（中转站示例）
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-chat

# 通义千问
DASHSCOPE_API_KEY=sk-xxx

# 本地 Ollama
OPENAI_API_KEY=ollama
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_MODEL=llama3
```

> 免费获取 Token 教程：启动后访问 <http://localhost:5173/tutorial>
> 支持 100+ LLM 供应商，详见 [README.md](../README.md#100-llm-供应商)。

---

## 验证安装

```bash
# 检查后端
curl http://localhost:8000/health

# 检查前端
curl http://localhost:5173

# CLI 诊断
sakura doctor
```

---

## 常见问题

### Q: 启动后端报 `ModuleNotFoundError`？

A: 确认已激活虚拟环境并安装依赖：

```bash
cd backend
source .venv/bin/activate
pip install -r requirements.txt
```

### Q: 前端启动报 `node_modules` 找不到？

A: 重新安装前端依赖：

```bash
cd frontend && npm install
```

### Q: 不想配 LLM Key 能用吗？

A: 可以。不填 Key 时后端走 mock 模式，所有 Agent 返回离线模拟响应，方便体验流程。

### Q: Docker 启动失败？

A: 确认 Docker Desktop 已启动：

```bash
docker info    # 能正常输出说明 Docker 在运行
```
