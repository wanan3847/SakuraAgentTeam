# SakuraAgentTeam 使用说明

> 快速上手、目录约定、API 速查、调试技巧

本文是 [architecture.md](./architecture.md) 的姊妹篇，专门讲"怎么用"。

## 1. 5 分钟跑通

### 1.1 启动

```bash
# 方式 A：一键启动（推荐）
./deploy.sh dev

# 方式 B：手动
# 后端
cd backend && python3 -m uvicorn app.api.main:app --reload --port 8000
# 前端（另一个终端）
cd frontend && npm install && npm run dev
```

- 后端 API 文档：`http://localhost:8000/docs`
- 前端页面：`http://localhost:5173`（Vite 已把 `/api/*` 代理到 8000）

### 1.2 创建第一个任务

1. 访问 `http://localhost:5173/new-task`
2. 输入：`帮我做一个 Todo 应用，支持增删改查`
3. 点击「开始执行」→ 跳转到会话页
4. 实时看到 7 个 Agent 依次完成
5. 完成后去「产物浏览」看代码

完整演示见 [docs/demo.md](./demo.md)。

## 2. 7 个 Agent 角色

| 角色 | 职责 | 产物示例 |
|------|------|----------|
| requirements | 解析需求 → PRD.md | PRD.md |
| design | 架构 + API 契约 | architecture.md, api.md, database.md |
| frontend | React + Vite + TS 代码 | main.tsx, App.tsx, pages/, api.ts |
| backend | FastAPI + Pydantic 代码 | main.py, models.py, routes.py |
| testing | pytest 测试用例 | backend/tests/test_api.py |
| review | LLM 代码审查 + 修正 | review_report.md |
| deployment | Docker 部署配置 + 真实验证 | Dockerfile, docker-compose.yml |

每个 Agent 的产物都会自动 commit 到项目 git 仓库（`backend/data/projects/<session_id>/`）。

## 3. 核心 API 速查

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

## 4. 调试技巧

### 4.1 单 Agent 调试

```bash
cd backend
python3 scripts/debug_agent.py --role requirements --requirement "做一个 todo app"
```

跳过 workflow，只跑一个 agent 并打印产物。

### 4.2 E2E 验证

```bash
# 后端 26 个测试（包含完整 workflow 端到端 + deployment agent 真实验证）
cd backend && python3 -m pytest tests/ -v

# 快速端到端验证（开新 session → 轮询 → 打印 progress）
python3 scripts/verify_progress.py
```

### 4.3 实时事件流（SSE）

浏览器 DevTools → Network → 找 `event-stream` 请求 → 看 `EventStream` tab。

或 curl：

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

### 4.4 看 git 仓库

```bash
cd backend/data/projects/{session_id}
git log --oneline --graph
ls -R
```

每个 agent 完成都会自动 commit，message 形如 `[requirements] PRD.md`。

## 5. LLM Provider 配置

```bash
# 1. 编辑 backend/.env
echo "OPENAI_API_KEY=sk-..." >> backend/.env
echo "DEFAULT_LLM_PROVIDER=openai" >> backend/.env
echo "DEFAULT_LLM_MODEL=gpt-4o" >> backend/.env

# 2. 验证接入（不消耗 token）
cd backend && python3 scripts/llm_connect_check.py
# 退出码 0 = 就绪，1 = 未配置，2 = 加载失败
```

支持：`openai`（gpt-4o / gpt-4-turbo / ...）和 `anthropic`（claude-sonnet-4 / claude-opus-4 / ...）。

Provider 注册位置：`backend/app/foundation/llm/`。扩展方式参考 OpenHands 风格，新建 `xxx_provider.py` + 在 `__init__.py` 注册。

## 6. 经验库

默认使用 ChromaDB（语义检索）+ 关键词回退（不依赖向量库也能用）。

- 数据源：`backend/data/experiences.json`（始终是权威数据源）
- ChromaDB 索引：`backend/data/chroma/`（如已安装）
- 用户在 UI 评分（1-5 星）会更新 experience 的 `rating` 字段
- 检索时高 rating 的经验优先返回

**Known Limitations**：ChromaDB 在某些环境（PyPI 受限 / onnxruntime 装不上）会自动 fallback 到关键词检索，功能不受影响。装上：`uv pip install chromadb`。

## 7. 常见问题

**Q: 前端 404 /api/v1/xxx？**
A: 检查 Vite 代理配置 `frontend/vite.config.ts` 是否正确指向 8000。

**Q: agent_progress 一直显示 running？**
A: 检查 `backend/app/orchestration/engine.py` 的 `agent.run()` 后是否调用 `update_agent_progress(COMPLETED)`。

**Q: 项目目录是空的？**
A: 检查 `_execute_workflow` 是否把 `projects_root` 和 `project_id` 传给 `engine.run()`。

**Q: ChromaDB 不可用？**
A: 系统自动回退到关键词匹配，`backend/data/experiences.json` 始终是权威数据源。

**Q: 怎么扩展 Agent？**
A: 在 `backend/app/agents/` 新建 `<role>_agent.py`，继承 `Agent` 基类，在 `__init__.py` 的 `create_all_agents()` 注册。

## 8. 测试

```bash
cd backend && python3 -m pytest tests/ -v
```

**26 个测试**，覆盖：API 路由、LLM Provider 工厂、Tool 注册、E2E workflow、deployment agent docker 验证。详细：[docs/coverage.md](./coverage.md)。
