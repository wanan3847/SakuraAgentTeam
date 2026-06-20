# Changelog

SakuraAgentTeam 的所有变更记录。格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

## [Unreleased] — M4 阶段

### Added
- **M4-I2 部署 Agent 真实 docker build 验证**：DeploymentAgent 跑 `docker compose config` 验证生成的 `docker-compose.yml` 语法，把 `build_verified` 字段写到 artifact metadata
- **M4 测试套件**：[backend/tests/test_deployment_agent.py](../backend/tests/test_deployment_agent.py)（2 个用例）
- **docs/demo.md**：端到端演示文档（启动→创建→实时进度→产物→git 历史→回滚）
- **docs/architecture.md 精简**：1508 → 492 行；开源项目调研移到 docs/references.md
- **deploy.sh**：一键启动 dev/prod/stop/logs/clean
- **infra/docker-compose.yml** + **frontend/Dockerfile** + **nginx.conf**：Docker 生产部署
- **README.md 增强**：徽章 + 特性 + 5 分钟跑通 + 路线图

### Changed
- **M2-I2 修复**：engine.py 在 `agent.run()` 成功后调用 `update_agent_progress(COMPLETED)`，修复 agent_progress 永远显示 running 的 bug
- **M2-I7 修复**：routes.py `_execute_workflow` 把 `projects_root`/`project_id` 传给 `engine.run()`，修复产物没 commit 到 git 的 bug
- **Pydantic v2 兼容**：`class Config` 全部替换为 `model_config = SettingsConfigDict(...)`
- **datetime.utcnow() 弃用修复**：14 处全部改为 `datetime.now(timezone.utc).isoformat()`
- **AsyncClient 迁移**：`AsyncClient(app=...)` 替换为 `ASGITransport(app=app)`
- **requirements.txt**：新增 anthropic / GitPython / chromadb
- **frontend/package.json**：新增 axios

## [v1.0.0] — 2026-06-20 · 首次发布

### Added
- **M0 基础设施**（8/8）
  - M0-I1 目录结构（monorepo: backend/frontend/infra/docs/scripts）
  - M0-I2 FastAPI 脚手架 + Pydantic v2
  - M0-I3 React + Vite + TypeScript + Tailwind
  - M0-I4 LLM Provider 抽象（OpenAI/Anthropic 可插拔）
  - M0-I5 Tool 基类（file_read/file_write/shell_run）
  - M0-I6 Docker 沙箱（[backend/app/core/sandbox.py](../backend/app/core/sandbox.py)）
  - M0-I7 Git 产物仓库（[backend/app/foundation/git_repo.py](../backend/app/foundation/git_repo.py)）
  - M0-I8 GitHub Actions CI（ruff + pyright + pytest + eslint + vite build）

- **M1 单 Agent**（6/6）
  - M1-I1 Agent 基类 + Context/Plan/Artifact
  - M1-I2 需求 Agent（PRD 生成）
  - M1-I3 SessionManager（[backend/app/orchestration/session.py](../backend/app/orchestration/session.py)）
  - M1-I4 EventBus + SSE 流（[backend/app/orchestration/eventbus.py](../backend/app/orchestration/eventbus.py)）
  - M1-I5 前端会话页（[frontend/src/pages/SessionPage.tsx](../frontend/src/pages/SessionPage.tsx)）
  - M1-I6 端到端单 Agent 调试（[backend/scripts/debug_agent.py](../backend/scripts/debug_agent.py)）

- **M2 多 Agent 编排**（16/16）
  - M2-I1 DAG 定义（[backend/app/orchestration/workflows.py](../backend/app/orchestration/workflows.py)）
  - M2-I2 WorkflowEngine（DAG 调度 + 失败重试）
  - M2-I3-I7 6 个 Agent（design/frontend/backend/testing/review/deployment）
  - M2-I8 前端 DAG 可视化
  - M2-I9 部署 Agent（Dockerfile + docker-compose）
  - M2-I10 经验库（[backend/app/foundation/experience.py](../backend/app/foundation/experience.py)）
  - M2-I11 ChromaDB 向量检索
  - M2-I12 错误时检索注入 Prompt
  - M2-I13 成功后自动记录
  - M2-I14-I16 动态编排（greenfield/brownfield/incremental）

- **M3 可用性工程化**（5/5）
  - M3-I1 产物页 CodeBlock（[frontend/src/components/CodeBlock.tsx](../frontend/src/components/CodeBlock.tsx)，零依赖轻量高亮）
  - M3-I2 Session 历史页（[frontend/src/pages/HistoryPage.tsx](../frontend/src/pages/HistoryPage.tsx)）
  - M3-I3 单元测试套件（[backend/tests/](../backend/tests/)，24 个用例）
  - M3-I4 端到端集成测试（[backend/tests/test_e2e_workflow.py](../backend/tests/test_e2e_workflow.py)）
  - M3-I5 文档（architecture.md / usage.md）

### 测试覆盖
- 后端：24/24 通过，零警告
- 前端：1534 modules，0 errors / 0 warnings
- 端到端：7 agent 全部 completed，git 7+ commits

## 路线图

| 阶段 | 内容 | 状态 |
|------|------|------|
| M0 | 基础设施 | ✅ |
| M1 | 单 Agent 闭环 | ✅ |
| M2 | 多 Agent 编排 | ✅ |
| M3 | 可用性工程化 | ✅ |
| M4 | 进一步增强（真实 LLM + docker build 验证） | 🚧 |
| M5+ | 维护模式（bug 修复 + 用户反馈） | ⏳ |

## 致谢

设计灵感来自以下优秀开源项目：

- **[OpenHands](https://github.com/All-Hands-AI/OpenHands)** — LLM Provider 抽象、Tool 系统、Docker 沙箱
- **[Claude Code](https://docs.anthropic.com/en/docs/claude-code)** — Fork/Coordinator Agent 模式（参考其源码泄露分析）
- **[CrewAI](https://github.com/joaomdmoura/crewAI)** — Role-based Agent 设计
- **[LangGraph](https://github.com/langchain-ai/langgraph)** — DAG 编排
- **[smolagents](https://github.com/huggingface/smolagents)** — CodeAct Agent 模式
- **[DeerFlow](https://github.com/bytedance/deerflow)** — 多 Agent 协同工程
- **[Hermes](https://github.com/)** — 错误经验积累机制
- **[Neat-Freak](https://github.com/)** — 经验库"毕业"机制
- **[OpenDesign](https://github.com/)** — 前端 Agent 设计参考
- **Anthropic Skills** — 子 Agent 设计原则

详见 [docs/references.md](./references.md)。
