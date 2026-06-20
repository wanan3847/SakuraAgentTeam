# SakuraAgentTeam

> 多智能体可协同的全栈 Agent 开发系统 · 从自然语言需求到可运行应用

[![Backend Tests](https://img.shields.io/badge/backend-26%2F26%20passing-brightgreen)](./backend/tests)
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

## 🚀 5 分钟跑通

```bash
# 1. 克隆
git clone https://github.com/wanan3847/SakuraAgentTeam.git
cd SakuraAgentTeam

# 2. 一键启动（自动创建环境 + 安装依赖 + 启动前后端）
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
│   │   ├── orchestration/   # Session / Engine / Workflow
│   │   ├── api/             # FastAPI 路由
│   │   └── core/            # config / logging / sandbox
│   ├── tests/               # 26 个 pytest 测试
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
