# SakuraAgentTeam 使用说明

> 快速上手、目录约定、API 速查、调试技巧

本文是 [architecture.md](./architecture.md) 的姊妹篇，专门讲"怎么用"。

## 1. 5 分钟跑通

### 1.1 启动后端

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 -m uvicorn app.api.main:app --reload --port 8000
```

启动后访问 `http://localhost:8000/docs` 看 OpenAPI 文档。

### 1.2 启动前端

```bash
cd frontend
npm install
npm run dev
```

打开 `http://localhost:5173/`。Vite 已经把 `/api/*` 代理到后端 8000 端口。

### 1.3 创建第一个任务

1. 访问 `http://localhost:5173/new-task`
2. 输入：`帮我做一个 Todo 应用，支持增删改查`
3. 点击「开始执行」→ 跳转到会话页
4. 实时看到 7 个 Agent 依次完成
5. 完成后可去「产物浏览」看代码

## 2. 项目目录约定

```
SakuraAgentTeam/
├── backend/                  # FastAPI 后端
│   ├── app/
│   │   ├── agents/          # 7 个 Agent 实现
│   │   ├── foundation/      # LLM / Tool / Git / Experience
│   │   ├── orchestration/   # Session / EventBus / Workflow
│   │   ├── api/             # FastAPI 路由
│   │   └── core/            # 配置 / 日志
│   ├── tests/               # pytest 测试（24 个用例）
│   ├── scripts/             # 工具脚本
│   ├── data/
│   │   ├── projects/        # 每个 session 一个 git 仓库
│   │   ├── experiences.json # 经验库
│   │   └── sessions.json    # 会话元数据
│   └── requirements.txt
├── frontend/                 # React + Vite
│   ├── src/
│   │   ├── pages/           # 6 个页面
│   │   ├── components/      # 复用组件（CodeBlock / Layout）
│   │   ├── services/api.ts  # 后端 API 封装
│   │   └── App.tsx
│   ├── package.json
│   └── vite.config.ts        # 代理 /api → 8000
├── scripts/                  # 根级脚本
│   └── verify_progress.py    # E2E 验证脚本
└── docs/
    ├── architecture.md       # 架构总览（先读这个）
    └── usage.md              # 本文
```

## 3. 7 个 Agent 角色

| 角色 | 职责 | 产物示例 |
|------|------|----------|
| requirements | 解析需求 → PRD.md | PRD.md |
| design | 架构 + API 契约 | architecture.md, api.md, database.md |
| frontend | React + Vite + TS 代码 | main.tsx, App.tsx, pages/, api.ts |
| backend | FastAPI + Pydantic 代码 | main.py, models.py, routes.py |
| testing | pytest 测试用例 | backend/tests/test_api.py |
| review | LLM 代码审查 + 修正 | review_report.md |
| deployment | Docker 部署配置 | Dockerfile, docker-compose.yml |

每个 Agent 的产物都会自动 commit 到项目 git 仓库（`data/projects/<session_id>/`）。

## 4. 核心 API 速查

### Sessions

```bash
# 创建 session
curl -X POST http://localhost:8000/api/v1/sessions \
  -H "Content-Type: application/json" \
  -d '{"requirement": "做一个 todo app"}'

# 启动 workflow
curl -X POST http://localhost:8000/api/v1/sessions/{id}/execute

# 查询 session（含 agent_progress、artifacts）
curl http://localhost:8000/api/v1/sessions/{id}

# 列出所有 session
curl http://localhost:8000/api/v1/sessions

# 取消
curl -X POST http://localhost:8000/api/v1/sessions/{id}/cancel
```

### Projects（Git 仓库）

```bash
# 列出所有项目
curl http://localhost:8000/api/v1/projects

# 查看 commit 历史
curl http://localhost:8000/api/v1/projects/{id}/commits

# 列出文件
curl http://localhost:8000/api/v1/projects/{id}/files

# 读取文件
curl http://localhost:8000/api/v1/projects/{id}/files/README.md

# 回滚
curl -X POST http://localhost:8000/api/v1/projects/{id}/rollback \
  -H "Content-Type: application/json" \
  -d '{"commit_hash": "abc1234"}'
```

### Experiences（经验库）

```bash
# 列出
curl http://localhost:8000/api/v1/experiences

# 语义搜索
curl "http://localhost:8000/api/v1/experiences?error_message=ImportError&top_k=5"

# 创建
curl -X POST http://localhost:8000/api/v1/experiences \
  -H "Content-Type: application/json" \
  -d '{"error_message": "...", "error_type": "...", "context": {}, "solution": "..."}'

# 评分
curl -X POST http://localhost:8000/api/v1/experiences/{id}/rate \
  -H "Content-Type: application/json" \
  -d '{"rating": 5}'
```

### Workflows（动态选择）

```bash
# 列出所有 workflow
curl http://localhost:8000/api/v1/workflows

# 根据需求选择
curl -X POST http://localhost:8000/api/v1/workflows/select \
  -H "Content-Type: application/json" \
  -d '{"requirement": "做一个新 todo app"}'
```

## 5. 调试技巧

### 5.1 单 Agent 调试

```bash
cd backend
python3 scripts/debug_agent.py --role requirements --requirement "做一个 todo app"
```

这会跳过 workflow，只跑一个 agent 并打印产物。

### 5.2 E2E 验证

```bash
# 后端 24 个测试（包含完整 workflow 端到端测试）
cd backend
python3 -m pytest tests/ -v

# 快速端到端验证（开新 session → 轮询 → 打印 progress）
python3 /path/to/SakuraAgentTeam/scripts/verify_progress.py
```

### 5.3 查看实时事件流（SSE）

打开浏览器 DevTools → Network → 找到 `event-stream` 请求 → 看 `EventStream` tab。

或者用 curl：

```bash
curl -N http://localhost:8000/api/v1/sessions/{id}/stream
```

事件类型：
- `session.started` - workflow 开始
- `agent.started` - agent 开始执行
- `agent.log` - agent 日志
- `agent.completed` - agent 完成
- `artifact.created` - 产物生成
- `session.completed` - 整个 workflow 完成
- `session.failed` - workflow 失败

### 5.4 看 git 仓库

```bash
cd backend/data/projects/{session_id}
git log --oneline --graph
ls -R
```

每个 agent 完成都会自动 commit，message 形如 `[requirements] PRD.md`。

## 6. LLM Provider 配置

MVP 默认使用 mock provider（不调用真实 API）。要启用真实 LLM，在 `backend/.env` 中：

```bash
# OpenAI
OPENAI_API_KEY=sk-...
DEFAULT_LLM_PROVIDER=openai
DEFAULT_LLM_MODEL=gpt-4o

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...
DEFAULT_LLM_PROVIDER=anthropic
DEFAULT_LLM_MODEL=claude-4-sonnet
```

支持的 provider 在 `backend/app/foundation/llm/` 下注册，参考 OpenHands 风格可继续扩展。

## 7. 经验库

经验库默认使用 ChromaDB（语义检索）+ 关键词回退（不依赖向量库也能用）。

- 数据存于 `backend/data/experiences.json`（关键词索引）
- ChromaDB 索引存于 `backend/data/chroma/`（如已安装）
- 用户在 UI 评分（1-5 星）会更新 experience 的 `rating` 字段
- 检索时高 rating 的经验优先返回

## 8. 常见问题

**Q: 前端 404 /api/v1/xxx？**
A: 检查 Vite 代理配置 `frontend/vite.config.ts` 是否正确指向 8000。

**Q: agent_progress 一直显示 running？**
A: 已修复 — 2026-06-20 提交的 engine.py 修改确保 agent.run() 成功后调用 update_agent_progress(COMPLETED)。

**Q: 项目目录是空的？**
A: 已修复 — `_execute_workflow` 现在把 `projects_root` 和 `project_id` 传给 `engine.run()`，agent 才知道往哪个 git 仓库 commit。

**Q: ChromaDB 不可用？**
A: 系统自动回退到关键词匹配。`backend/data/experiences.json` 始终是权威数据源。

**Q: 怎么扩展 Agent？**
A: 在 `backend/app/agents/` 新建 `<role>_agent.py`，继承 `Agent` 基类，在 `__init__.py` 的 `create_all_agents()` 注册。

## 9. 测试覆盖

| 测试文件 | 覆盖范围 | 用例数 |
|----------|----------|--------|
| test_api.py | API 路由 + Session + Project + Rollback | 10 |
| test_e2e_workflow.py | 端到端 workflow + agent_progress + 产物可读 | 3 |
| test_llm.py | LLM Provider 工厂 + OpenAI/Anthropic | 5 |
| test_tools.py | Tool 注册 + Input 校验 | 6 |
| **合计** | | **24** |

跑全部：`cd backend && python3 -m pytest tests/ -v`
