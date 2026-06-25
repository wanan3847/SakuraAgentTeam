# 安装指南

> 樱花小队 (SakuraAgentTeam) 支持多种安装方式，选择最适合你的一种。

---

## 目录

1. [一键脚本(推荐)](#1-一键脚本推荐)
2. [pip 安装(CLI)](#2-pip-安装cli)
3. [源码安装](#3-源码安装)
4. [Docker 安装](#4-docker-安装)
5. [VS Code 插件安装](#5-vs-code-插件安装)
6. [桌面应用(开发中)](#6-桌面应用开发中)

---

## 前置要求

| 依赖 | 版本 | 说明 |
|------|------|------|
| Python | ≥ 3.11 | 后端运行时 |
| Node.js | ≥ 20 | 前端运行时 |
| Git | ≥ 2.40 | 克隆代码 |
| LLM API Key | — | OpenAI / Anthropic / DeepSeek 等任一 |

---

## 1. 一键脚本(推荐)

适合绝大多数用户,自动检查依赖、克隆代码、安装前后端依赖、生成 .env。

**macOS / Linux (curl):**

```bash
curl -fsSL https://raw.githubusercontent.com/wanan3847/SakuraAgentTeam/main/scripts/install.sh | bash
```

**macOS / Linux (wget):**

```bash
wget -qO- https://raw.githubusercontent.com/wanan3847/SakuraAgentTeam/main/scripts/install.sh | bash
```

**Windows (PowerShell):**

```powershell
irm https://raw.githubusercontent.com/wanan3847/SakuraAgentTeam/main/scripts/install.ps1 | iex
```

**或先克隆再执行:**

```bash
git clone https://github.com/wanan3847/SakuraAgentTeam.git
cd SakuraAgentTeam
./scripts/install.sh        # macOS / Linux
.\scripts\install.ps1      # Windows PowerShell
```

脚本完成后:
- 后端 Python venv 在 `backend/.venv/`
- 前端 node_modules 在 `frontend/node_modules/`
- `backend/.env` 已生成随机 `SECRET_KEY`,需手动填 `OPENAI_API_KEY`
- 启动:`./deploy.sh dev`

---

## 2. pip 安装(CLI)

仅安装命令行客户端,适合只需要 CLI 的用户:

```bash
pip install sakura-agent-team
```

安装后即可使用 `sakura` 命令行工具:

```bash
sakura version
sakura config set --api-url http://localhost:8000
```

> pip 包只含 CLI 客户端。后端 / 前端服务仍需从源码启动(见下方源码安装)。

---

## 3. 源码安装

适合开发者和需要自定义配置的用户。

### 3.1 克隆仓库

```bash
git clone https://github.com/wanan3847/SakuraAgentTeam.git
cd SakuraAgentTeam
```

### 3.2 手动安装后端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env         # 填入 LLM API Key
```

### 3.3 手动安装前端

```bash
cd frontend
npm install
```

### 3.4 启动

```bash
# 一键启动(推荐)
./deploy.sh dev

# 或分别启动
cd backend && python -m uvicorn app.api.main:app --reload --port 8000
cd frontend && npm run dev
```

浏览器访问 <http://localhost:5173>。

---

## 4. Docker 安装

适合服务器部署和容器化环境。

### 4.1 前置要求

- Docker ≥ 24
- Docker Compose ≥ 2

### 4.2 启动

```bash
git clone https://github.com/wanan3847/SakuraAgentTeam.git
cd SakuraAgentTeam
cp backend/.env.example backend/.env   # 填入 LLM API Key

# 一键启动
./deploy.sh prod
```

或手动:

```bash
docker compose -f infra/docker-compose.yml up -d --build
```

### 4.3 访问

- 前端:<http://localhost:8080>
- 后端 API:<http://localhost:8000/docs>

### 4.4 管理命令

```bash
./deploy.sh stop     # 停止
./deploy.sh logs     # 查看日志
./deploy.sh clean    # 清理数据与镜像
```

---

## 5. VS Code 插件安装

在 VS Code 中直接使用樱花小队。

### 5.1 从 VSIX 安装

```bash
cd vscode-extension
npm install
npm run package    # 生成 sakura-agent-team-0.1.0.vsix
```

在 VS Code 中:

```
扩展面板 → ⋯ → 从 VSIX 安装 → 选择 .vsix 文件
```

或命令行:

```bash
code --install-extension sakura-agent-team-0.1.0.vsix
```

### 5.2 配置

在 VS Code 设置中搜索 `樱花小队`:

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `sakura.serverUrl` | `http://localhost:8000` | 后端 API 地址 |
| `sakura.token` | `""` | JWT 登录 Token |

> 详细使用说明见 [VSCODE_EXTENSION.md](./VSCODE_EXTENSION.md)。

---

## 6. 桌面应用(macOS / Windows / Linux)

桌面应用基于 Electron,UI 壳 + 内嵌后端。**注意:macOS 14+ arm64 的 PyInstaller 6.x 有 silent fail 已知问题,实际跑时应用会用本机 Python 3.10+ 兜底启动后端**;Windows 在 Mac 上交叉编译需要 wine 且 .exe 缺数字签名,推荐用 GitHub Actions 自动构建。

### 6.1 macOS(.dmg,需 Python 3.10+ 兜底)

```bash
# 1. 准备后端 binary(可选 — 失败时应用会自动 fallback 到 Python)
cd backend
pip install build pyinstaller
pyinstaller --onefile --name sakura-backend \
  --collect-all aiosqlite --collect-all sqlalchemy \
  --add-data "app:app" \
  sakura_backend_launcher.py
mkdir -p ../desktop/bin
cp dist/sakura-backend ../desktop/bin/

# 2. 构建前端 + electron
cd ../frontend && npm run build
rm -rf ../desktop/frontend-dist
cp -r dist ../desktop/frontend-dist
cd ../desktop && npm install && npm run build:mac

# 3. 安装
open dist/SakuraAgentTeam-0.2.0-arm64.dmg
# 把 SakuraAgentTeam.app 拖入 Applications

# 4. 启动(应用会自动检测 Python 3.10+ 并启动后端在 18800 端口)
open /Applications/SakuraAgentTeam.app
```

**如果 .app 启动后无反应**:
- 检查 `python3 --version` 是否 ≥ 3.10
- 如没装:`brew install python@3.12`
- 应用启动后会在 18800 端口启后端,UI 加载本地 `app.asar/frontend-dist/index.html`

产出物:
- Apple Silicon: `desktop/dist/SakuraAgentTeam-0.2.0-arm64.dmg` (~582MB)
- Intel: `desktop/dist/SakuraAgentTeam-0.2.0.dmg` (~587MB)

### 6.2 Windows(.exe,推荐用 GitHub Actions)

#### 方案 A — 在 Windows 上自建(原生,推荐)

```powershell
# 在 Windows 10/11 机器上
cd SakuraAgentTeam\backend
pip install build pyinstaller
pyinstaller --onefile --name sakura-backend `
  --collect-all aiosqlite --collect-all sqlalchemy `
  --add-data "app;app" `
  sakura_backend_launcher.py
New-Item -ItemType Directory -Force ..\desktop\bin
Copy-Item dist\sakura-backend.exe ..\desktop\bin\

cd ..\frontend
npm run build
Remove-Item -Recurse -Force ..\desktop\frontend-dist
Copy-Item -Recurse dist ..\desktop\frontend-dist

cd ..\desktop
npm install
npm run build:win

# 产物:dist\SakuraAgentTeam-Setup-0.2.0.exe (nsis 安装器) + 绿色版
```

#### 方案 B — GitHub Actions 自动跨平台(无需 Windows 机器)

仓库已配 `.github/workflows/desktop-build.yml`,push 触发自动在 macOS / Windows / Linux runner 上同时构建 .dmg / .exe / AppImage。tag 触发会自动 attach 到 GitHub Release。

```bash
# 触发方式 1:push 到 main
git push origin main
# → 30 分钟后看 https://github.com/wanan3847/SakuraAgentTeam/actions 的 Artifacts

# 触发方式 2:打 tag
git tag v0.2.1
git push origin v0.2.1
# → 自动创建 https://github.com/wanan3847/SakuraAgentTeam/releases/tag/v0.2.1 含全部产物
```

#### 方案 C — PowerShell 一键脚本(Web 版,0 依赖)

如果只是要跑,不用桌面端外壳,直接用 Web 版:

```powershell
irm https://raw.githubusercontent.com/wanan3847/SakuraAgentTeam/main/scripts/install.ps1 | iex
# 浏览器打开 http://localhost:5173
```

#### ⚠️ 方案 D(不推荐)— 在 Mac 上交叉编译 .exe

```bash
brew install --cask wine-stable
cd desktop && npm install && npm run build:win
# 问题:生成的 .exe 缺数字签名,Windows SmartScreen 会弹警告
```

### 6.3 Linux(AppImage / deb)

```bash
cd desktop && npm install && npm run build:linux
# 产物:dist/SakuraAgentTeam-0.2.0.AppImage + .deb
```

---

## 7. VS Code 插件(.vsix)

```bash
cd vscode-extension
npm install
npx vsce package
# 产物:sakura-agent-team-0.2.0.vsix (~16KB)

# 安装
code --install-extension sakura-agent-team-0.2.0.vsix
# 或 VS Code → 扩展 → ⋯ → 从 VSIX 安装
```

---

## 8. CLI 命令行(wheel 包)

```bash
cd backend
pip install build
python3 -m build --wheel

# 产物:dist/sakura_agent_team-0.2.0-py3-none-any.whl (~252KB)

# 本地装
pip install --user dist/sakura_agent_team-0.2.0-py3-none-any.whl
sakura --version  # 0.2.0
```

包含 11 个子命令:`serve` / `frontend` / `start` / `chat` / `agents` / `teams` / `create-team` / `history` / `login` / `register` / `install`。

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
