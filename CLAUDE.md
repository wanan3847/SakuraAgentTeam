# CLAUDE.md

AI 协作者规则手册。读 [docs/architecture.md](./docs/architecture.md) 了解全局。

## 必读

- 架构：[docs/architecture.md](./docs/architecture.md)（M0-M4 全景）
- 怎么用：[docs/usage.md](./docs/usage.md)
- 演示命令：[docs/demo.md](./docs/demo.md)
- 调研背景：[docs/references.md](./docs/references.md)
- 变更日志：[CHANGELOG.md](./CHANGELOG.md)
- 贡献规范：[CONTRIBUTING.md](./CONTRIBUTING.md)

## 强制规则

- **改代码前先读**：用 Read 工具读文件再改，不凭想象写
- **跑测试再提交**：`cd backend && ruff check . && python3 -m pytest tests/ -q` 必须全过
- **前端同步**：`cd frontend && npx tsc --noEmit && npm run build` 必须过
- **别引入新依赖**到 `requirements.txt` 不开 Issue
- **不在 docs/ 抄代码**：docs 引用代码用 `file:///` 链接，不嵌入大段源码

## 目录用途

- `backend/app/agents/` — 7 个角色 Agent（不要随便加 Agent 类型）
- `backend/app/orchestration/` — Session / Engine / Workflow（核心调度）
- `backend/app/foundation/` — LLM / Tool / Git / Experience（基础设施）
- `backend/data/` — 运行时数据（git 仓库、经验库），**永远别 commit**
- `docs/` — 公开文档（用户能读）
- `scripts/` — 根级 E2E 验证脚本

## Mock 模式

未设置 LLM Key 时所有 Agent 返回固定模板。`scripts/llm_connect_check.py` 验证真实 LLM 接入。

## 部署模式

- `./deploy.sh dev` — 本地开发（uvicorn --reload + vite dev）
- `./deploy.sh prod` — Docker 持续运行（**用户首选**）
- `./deploy.sh stop` / `logs` / `clean`

数据持久化在 `sakura_backend_data` volume（prod 模式）。

## 客户端与多源头

- **Web UI**：`http://localhost:8080`（prod）/ `:5173`（dev）
- **CLI**：`cd backend && python3 -m cli <cmd>` — task/sessions/status/logs/artifacts/cancel/doctor/config
  - 配置：`~/.sakura/config.toml`，环境变量 `SAKURA_API_URL` / `SAKURA_API_TOKEN`
- **Connectors webhook**（`app/api/connectors.py`）：
  - `POST /api/v1/connectors/github/issues` — GitHub Issue 触发
  - `POST /api/v1/connectors/github/pr` — GitHub PR/Comment 触发
  - `POST /api/v1/connectors/im` — 飞书/钉钉/Slack 通用
  - `POST /api/v1/connectors/upload` — 文件上传（MD/PDF/PNG/JPG）
  - `POST /api/v1/connectors/url` — URL 抓取
  - 签名 secret：`GITHUB_WEBHOOK_SECRET` / `IM_WEBHOOK_TOKEN`（不配跳过验证）

## 已知限制

- ChromaDB 在 PyPI 受限环境装不上，fallback 关键词检索
- sandbox 需 Docker daemon（无则降级本地执行）
