# SakuraAgentTeam 使用说明

> 快速上手、目录约定、API 速查、调试技巧

本文是 [architecture.md](./architecture.md) 的姊妹篇，专门讲"怎么用"。

## 1. 5 分钟跑通

### 1.1 启动

两种模式按需选：

```bash
# 方式 A：Docker（推荐 — 持续运行，重启电脑后重新拉起即可）
./deploy.sh prod
# 前端：http://localhost:8080
# 后端 API：http://localhost:8000/docs

# 方式 B：本地开发（uvicorn --reload + vite dev，代码热重载）
./deploy.sh dev
# 前端：http://localhost:5173
# 后端 API：http://localhost:8000/docs
```

Docker 模式背后：`docker compose -f infra/docker-compose.yml up -d --build`，数据持久化在 `sakura_backend_data` volume（重启不丢）。

其他命令：

```bash
./deploy.sh stop      # 停所有
./deploy.sh logs      # 看 Docker 日志
./deploy.sh sandbox   # 构建 Agent 沙箱镜像
./deploy.sh clean     # 清数据 + 镜像
```

### 1.2 创建第一个任务

1. 访问 `http://localhost:5173/new-task`（dev）或 `http://localhost:8080/new-task`（prod）
2. 输入：`帮我做一个 Todo 应用，支持增删改查`
3. 点击「开始执行」→ 跳转到会话页
4. 实时看到 7 个 Agent 依次完成
5. 完成后去「产物浏览」看代码

完整演示见 [docs/demo.md](./demo.md)。

### 1.3 CLI 客户端（不开浏览器也能用）

```bash
cd backend
python3 -m cli config set --api-url http://localhost:8000   # 首次配置
python3 -m cli task "做个 todo app"          # 提交任务 + 流式跟踪
python3 -m cli sessions                     # 列出所有会话
python3 -m cli status <session_id>          # 查看详情（加 --watch 持续刷新）
python3 -m cli artifacts <session_id>       # 看产物
python3 -m cli logs <session_id>            # 流式日志（JSON 行）
python3 -m cli cancel <session_id>           # 取消
python3 -m cli projects                     # 列出项目
python3 -m cli doctor                       # 诊断连接 / 健康检查
```

配置存 `~/.sakura/config.toml`，环境变量 `SAKURA_API_URL` / `SAKURA_API_TOKEN` 覆盖。
所有 list / get 命令支持 `--output json` 输出 JSON 便于脚本处理。

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

### Connectors（多源头输入）

通过 webhook 把需求从外部工具推过来，所有端点都创建 session 并触发工作流。

| 端点 | 用途 | 安全 |
|---|---|---|
| `POST /api/v1/connectors/github/issues` | GitHub Issue 触发 | `X-Hub-Signature-256` + `GITHUB_WEBHOOK_SECRET` |
| `POST /api/v1/connectors/github/pr` | GitHub PR / 评论触发 | 同上 |
| `POST /api/v1/connectors/im` | 飞书/钉钉/Slack/企微通用 | `X-IM-Token` + `IM_WEBHOOK_TOKEN` |
| `POST /api/v1/connectors/upload` | 文件上传（MD/PDF/PNG/JPG）| — |
| `POST /api/v1/connectors/url` | URL 网页抓取 | — |

**GitHub Issue 触发示例**（GitHub Webhook → Sakura）：

```bash
# GitHub 仓库 Settings → Webhooks → Add
# Payload URL: https://your-host/api/v1/connectors/github/issues
# Content type: application/json
# Secret: <和 GITHUB_WEBHOOK_SECRET 一致>
# Events: Issues, Issue comments
```

**飞书机器人示例**：

```bash
curl -X POST http://localhost:8000/api/v1/connectors/im \
  -H "Content-Type: application/json" \
  -H "X-IM-Token: $IM_WEBHOOK_TOKEN" \
  -d '{"source":"feishu","text":"做个登录页","sender":"u_123","chat_id":"oc_abc"}'
```

**文件上传**（multipart）：

```bash
curl -X POST http://localhost:8000/api/v1/connectors/upload \
  -F "file=@spec.pdf" \
  -F "project_id=my-app"
```

**URL 抓取**：

```bash
curl -X POST http://localhost:8000/api/v1/connectors/url \
  -H "Content-Type: application/json" \
  -d '{"urls":["https://example.com/spec"]}'
```

不配 secret 时签名验证自动跳过（开发友好）。生产建议配 `GITHUB_WEBHOOK_SECRET` + `IM_WEBHOOK_TOKEN`。

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
