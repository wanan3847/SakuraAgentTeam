# SakuraAgentTeam

> 多智能体可协同的全栈 Agent 开发系统 · 从自然语言需求到可运行应用

[![Backend Tests](https://img.shields.io/badge/backend-24%2F24%20passing-brightgreen)](./backend/tests)
[![Frontend Build](https://img.shields.io/badge/frontend-1534%20modules%20%7C%200%20errors-blue)](./frontend)
[![License](https://img.shields.io/badge/license-MIT-green)](#)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org)
[![Node 20+](https://img.shields.io/badge/node-20%2B-green)](https://nodejs.org)

## ✨ 特性

- 🤖 **7 个角色 Agent**：需求 / 设计 / 前端 / 后端 / 测试 / 审查 / 部署
- 🔀 **动态工作流**：根据项目状态（greenfield / brownfield / incremental）智能选择执行链
- 🧠 **经验库**：ChromaDB 向量检索 + 关键词回退，自动积累错误解决方案
- 🗂️ **Git 产物仓库**：每个 Session 一个 git 仓库，每个 Agent 完成后自动 commit
- 🐳 **Docker 沙箱**：参考 OpenHands Runtime，代码执行安全隔离
- 🌐 **多 LLM 支持**：OpenAI / Anthropic / 本地模型（用户自带 Key）
- ⚡ **实时流**：SSE 事件总线，前端实时看到 Agent 进度和日志
- 🎨 **现代工作台**：React + Vite + TypeScript + Tailwind，6 个页面（任务/会话/产物/历史/经验/项目）

## 🚀 5 分钟跑通

```bash
# 1. 克隆
git clone https://github.com/yangyazhou/SakuraAgentTeam.git
cd SakuraAgentTeam

# 2. 一键启动（自动创建 venv + 安装依赖 + 启动前后端）
./deploy.sh dev

# 3. 打开浏览器
# 前端：http://localhost:5173
# 后端：http://localhost:8000/docs
```

停止服务：

```bash
./deploy.sh stop
```

## 📁 项目结构

```
SakuraAgentTeam/
├── backend/                  # FastAPI 后端
│   ├── app/
│   │   ├── agents/          # 7 个 Agent 实现
│   │   ├── foundation/      # LLM / Tool / Git / Experience
│   │   ├── orchestration/   # Session / EventBus / Workflow
│   │   ├── api/             # FastAPI 路由
│   │   └── core/            # 配置 / 日志 / 沙箱
│   ├── tests/               # 24 个测试
│   └── data/                # 运行时数据（被 .gitignore）
├── frontend/                 # React + Vite + TS
│   └── src/
│       ├── pages/           # 6 个页面
│       ├── components/      # CodeBlock / Layout
│       └── services/api.ts  # 后端 API 封装
├── infra/                    # Docker 部署
│   ├── docker/sandbox.Dockerfile
│   └── docker-compose.yml
├── docs/                     # 架构 + 使用文档
│   ├── architecture.md
│   └── usage.md
├── scripts/                  # 端到端验证脚本
└── deploy.sh                 # 一键启动/停止/部署
```

## 🧪 测试

```bash
# 后端（24 个测试，含完整 E2E workflow）
cd backend && python3 -m pytest tests/ -v

# 前端类型检查 + 构建
cd frontend && npm run build

# 端到端验证（启动 dev server 后另开终端）
python3 /path/to/SakuraAgentTeam/scripts/verify_progress.py
```

## 🤖 LLM 配置

默认使用 Mock Provider（不调用真实 API）。要启用真模型，编辑 `backend/.env`：

```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
DEFAULT_LLM_PROVIDER=openai
DEFAULT_LLM_MODEL=gpt-4o
```

## 📚 文档

| 文档 | 内容 |
|------|------|
| [docs/architecture.md](./docs/architecture.md) | 架构总览 · 任务拆分 · 开源参考 |
| [docs/usage.md](./docs/usage.md) | 使用说明 · API 速查 · 调试技巧 |
| [backend/README.md](./backend/README.md) | 后端细节 |

## 🗺️ 路线图

✅ M0 基础设施 · M1 单 Agent · M2 多 Agent 编排 · M3 可用性工程化
（详见 [architecture.md § 7](./docs/architecture.md#7-任务拆分milestone--sprint--issue)）

## 📄 许可证

MIT
