# SakuraAgentTeam

> 多智能体可协同的全栈 Agent 开发系统 · 从自然语言需求到可运行应用

[![Backend Tests](https://img.shields.io/badge/backend-54%2F54%20passing-brightgreen)](./backend/tests)
[![Frontend Build](https://img.shields.io/badge/frontend-vite%20build%20%7C%200%20errors-blue)](./frontend)
[![Coverage](https://img.shields.io/badge/coverage-70%25-yellow)](./docs/coverage.md)
[![License](https://img.shields.io/badge/license-MIT-green)](#)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org)
[![Node 20+](https://img.shields.io/badge/node-20%2B-green)](https://nodejs.org)

## ✨ 特性

- 🤖 **7 个角色 Agent**：需求 / 设计 / 前端 / 后端 / 测试 / 审查 / 部署
- 🔀 **动态工作流**：根据项目状态（greenfield / brownfield / incremental）智能选择执行链
- 🧠 **经验库**：ChromaDB 语义检索 + 关键词回退，自动积累错误解决方案
- 🗂️ **Git 产物仓库**：每个 Session 一个 git 仓库，每个 Agent 完成后自动 commit
- 🐳 **Docker 沙箱**：参考 OpenHands Runtime，代码执行安全隔离
- 🌐 **多 LLM 支持**：OpenAI / Anthropic（用户自带 Key，支持 Mock 离线模式）
- ⚡ **实时流**：SSE 事件总线，前端实时看到 Agent 进度和日志
- 🎨 **现代工作台**：React + Vite + TypeScript + Tailwind，6 个页面
- 🖥️ **CLI 客户端**：`sakura` 命令行，CI / 脚本友好
- 🔌 **多源头输入**：GitHub Issue / PR · 飞书/钉钉/Slack · 文件上传 · URL 抓取

## 🚀 5 分钟跑通

```bash
# 1. 克隆
git clone https://github.com/wanan3847/SakuraAgentTeam.git
cd SakuraAgentTeam

# 2a. Docker 一键起（推荐 — 持续运行，重启电脑后 ./deploy.sh prod 重新拉起）
./deploy.sh prod
# 浏览器：http://localhost:8080

# 2b. 本地开发（uvicorn --reload + vite dev，代码热重载）
./deploy.sh dev
# 浏览器：http://localhost:5173
```

**两种模式共用**：配置（`backend/.env`）、数据（git 仓库 / 经验库）、LLM Key 都一致。

停止服务：

```bash
./deploy.sh stop    # 停 Docker 或 dev 模式都通用
```

完整命令：`./deploy.sh {dev|prod|sandbox|stop|logs|clean}`

## 🖥️ CLI 客户端

不打开浏览器也能用：

```bash
cd backend
python3 -m cli config set --api-url http://localhost:8000
python3 -m cli task "做个 todo app"          # 提交任务 + 流式跟踪
python3 -m cli sessions                     # 列出所有会话
python3 -m cli status <session_id>          # 查看详情
python3 -m cli artifacts <session_id>       # 看产物
python3 -m cli logs <session_id>            # 流式日志
python3 -m cli cancel <session_id>           # 取消
python3 -m cli doctor                       # 诊断连接
```

配置存 `~/.sakura/config.toml`，环境变量 `SAKURA_API_URL` / `SAKURA_API_TOKEN` 覆盖。

## 🔌 多源头输入

通过 webhook 把需求从任何工具推过来：

| 端点 | 用途 | 签名 |
|---|---|---|
| `POST /api/v1/connectors/github/issues` | GitHub Issue 触发 | `GITHUB_WEBHOOK_SECRET` |
| `POST /api/v1/connectors/github/pr` | GitHub PR / 评论触发 | `GITHUB_WEBHOOK_SECRET` |
| `POST /api/v1/connectors/im` | 飞书/钉钉/Slack/企微通用 | `IM_WEBHOOK_TOKEN` |
| `POST /api/v1/connectors/upload` | 文件上传（MD/PDF/PNG/JPG）| — |
| `POST /api/v1/connectors/url` | URL 网页抓取 | — |

示例（飞书机器人）：

```bash
curl -X POST http://localhost:8000/api/v1/connectors/im \
  -H "Content-Type: application/json" \
  -d '{"source":"feishu","text":"做个登录页","sender":"u1","chat_id":"oc_xxx"}'
```

## 📁 项目结构

```
SakuraAgentTeam/
├── backend/                  # FastAPI 后端
│   ├── app/
│   │   ├── agents/          # 7 个 Agent 实现
│   │   ├── foundation/      # LLM / Tool / Git / Experience
│   │   ├── orchestration/   # Session / Engine / Workflow
│   │   ├── api/             # FastAPI 路由（routes.py + connectors.py）
│   │   └── core/            # config / logging / sandbox
│   ├── cli/                 # sakura CLI 客户端
│   ├── tests/               # 54 个 pytest 测试
│   ├── scripts/             # debug_agent.py / llm_connect_check.py
│   ├── data/                # 运行时数据（被 .gitignore 排除）
│   └── requirements.txt
├── frontend/                 # React + Vite + TS
│   └── src/
│       ├── pages/           # 6 个页面
│       ├── components/      # CodeBlock / Layout
│       └── services/api.ts  # 后端 API 封装
├── docs/                     # 架构 / 使用 / 演示 / 调研
│   ├── architecture.md       # 架构总览（M0-M4 全景）
│   ├── usage.md              # 使用说明 / API 速查
│   ├── demo.md               # 端到端演示命令
│   ├── coverage.md           # 测试覆盖率报告
│   └── references.md         # 开源项目调研背景
├── scripts/                  # verify_progress.py（E2E 验证）
├── deploy.sh                 # 一键启动 / 停止 / 部署
├── CHANGELOG.md              # 变更日志
└── CONTRIBUTING.md           # 贡献指南
```

## 🧪 测试

```bash
# 后端（26 个测试，含完整 E2E workflow + deployment agent）
cd backend && python3 -m pytest tests/ -v

# 前端类型检查 + 构建
cd frontend && npm run build

# 端到端验证（启动 dev server 后另开终端）
python3 scripts/verify_progress.py
```

覆盖率：[docs/coverage.md](./docs/coverage.md)（总 70%）

## 🤖 LLM 配置

默认使用 **Mock Provider**（不调用真实 API）。要启用真模型：

```bash
# 1. 编辑 backend/.env
echo "OPENAI_API_KEY=sk-..." >> backend/.env

# 2. 验证接入（不消耗 token）
cd backend && python3 scripts/llm_connect_check.py
# 退出码 0 = 就绪，1 = 未配置，2 = 加载失败
```

支持：OpenAI / Anthropic。详细：[docs/usage.md § 6](./docs/usage.md#6-llm-provider-配置)

## 📚 文档

| 文档 | 内容 |
|------|------|
| [docs/architecture.md](./docs/architecture.md) | 架构总览 · 任务拆分 · 开源参考 |
| [docs/usage.md](./docs/usage.md) | 使用说明 · API 速查 · 调试技巧 |
| [docs/demo.md](./docs/demo.md) | 端到端演示命令清单 |
| [docs/coverage.md](./docs/coverage.md) | 测试覆盖率报告（70%）|
| [docs/references.md](./docs/references.md) | OpenHands / Claude Code / CrewAI 调研 |
| [CHANGELOG.md](./CHANGELOG.md) | 版本变更日志 |
| [CONTRIBUTING.md](./CONTRIBUTING.md) | 贡献指南 · PR 流程 |

## 🗺️ 路线图

✅ M0 基础设施 · M1 单 Agent · M2 多 Agent 编排 · M3 可用性工程化 · M4 进一步增强
⏭️ M5 OpenTelemetry 监控（依赖实际部署量，暂不实现）

详细：[docs/architecture.md § 7-10](./docs/architecture.md)

## 📄 许可证

MIT
