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

## 已知限制

- ChromaDB 在 PyPI 受限环境装不上，fallback 关键词检索
- sandbox 需 Docker daemon（无则降级本地执行）
