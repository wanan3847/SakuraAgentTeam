# SakuraAgentTeam — 端到端演示

> 从零开始跑通一个完整任务：启动 → 创建 → 实时看进度 → 查看产物 → Git 历史 → 经验库

## 步骤 1：启动

```bash
cd /path/to/SakuraAgentTeam
./deploy.sh dev
```

启动后：
- 后端：<http://localhost:8000/docs>
- 前端：<http://localhost:5173>

终端输出（节选）：

```
[INFO] [INFO] 后端 PID: 12345（停止：./deploy.sh stop）
[INFO] [INFO] 前端 PID: 12346
[INFO] [INFO] 全部启动完成。后端日志：tail -f logs/backend.log
```

## 步骤 2：创建任务

### 方式 A：浏览器（推荐）

打开 <http://localhost:5173/new-task>，输入：

```
帮我做一个 todo 应用，支持增删改查
```

点击 **开始执行**，跳转到会话页。

### 方式 B：curl

```bash
SID=$(curl -s -X POST http://localhost:8000/api/v1/sessions \
  -H "Content-Type: application/json" \
  -d '{"requirement":"帮我做一个 todo 应用，支持增删改查"}' \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['id'])")

echo "Session ID: $SID"

curl -s -X POST http://localhost:8000/api/v1/sessions/$SID/execute \
  -H "Content-Type: application/json" \
  -d "{\"requirement\":\"帮我做一个 todo 应用，支持增删改查\"}"
```

## 步骤 3：实时查看进度

### 浏览器

会话页会实时显示 7 个 Agent 的状态变化（pending → running → completed）。

### curl + jq 轮询

```bash
while true; do
  STATUS=$(curl -s http://localhost:8000/api/v1/sessions/$SID \
    | python3 -c "import json,sys; d=json.load(sys.stdin)['data']; print(f\"{d['status']:10s} | completed: {sum(1 for p in d['agent_progress'].values() if p['status']=='completed')}/{len(d['agent_progress'])}\")")
  echo "$STATUS"
  [[ "$STATUS" == completed* || "$STATUS" == failed* ]] && break
  sleep 1
done
```

输出（节选）：

```
running    | completed: 0/7
running    | completed: 1/7
running    | completed: 3/7
running    | completed: 5/7
running    | completed: 6/7
completed  | completed: 7/7
```

### SSE 事件流（高级）

```bash
curl -N http://localhost:8000/api/v1/sessions/$SID/stream
```

## 步骤 4：查看产物

### 方式 A：浏览器

1. 打开 <http://localhost:5173/artifacts> 选 session
2. 或打开 <http://localhost:5173/artifacts/$SID> 直达

会看到完整文件树 + 代码高亮（CodeBlock 组件，零依赖）。

### 方式 B：API 列出文件

```bash
curl -s http://localhost:8000/api/v1/projects/$SID/files | python3 -m json.tool
```

### 方式 C：直接读项目目录

```bash
cd /Users/yangyazhou/SakuraAgentTeam/backend/data/projects/$SID
ls -R
cat PRD.md
cat architecture.md
cat frontend/src/App.tsx
```

## 步骤 5：看 Git 提交历史

每个 Agent 完成后会自动 commit。

```bash
cd /Users/yangyazhou/SakuraAgentTeam/backend/data/projects/$SID
git log --oneline --graph
```

预期输出（节选）：

```
* 9d2c1ab [deployment] docker-compose.yml, Dockerfile, DEPLOYMENT.md
* 5b4e8c0 [review] review_report.md
* 7c3f9aa [testing] backend/tests/test_api.py
* a8e1d2b [backend] backend/main.py, models.py, schemas.py, routes.py
* 1f7b3c8 [frontend] frontend/src/App.tsx, main.tsx, pages.tsx
* 0c9b2d3 [design] architecture.md, api.md, database.md
* 2e4a7f0 [requirements] PRD.md
* f1a3b5c Initial commit
```

## 步骤 6：经验库

```bash
# 列出所有经验
curl -s http://localhost:8000/api/v1/experiences | python3 -m json.tool

# 搜索
curl -s "http://localhost:8000/api/v1/experiences?error_message=ImportError" \
  | python3 -m json.tool

# 评分（5★）
curl -X POST http://localhost:8000/api/v1/experiences/<exp_id>/rate \
  -H "Content-Type: application/json" \
  -d '{"rating": 5}'
```

或在浏览器打开 <http://localhost:5173/experiences>，图形化搜索 + 评分。

## 步骤 7：回滚

如果想撤销某次 agent 的产物：

```bash
# 看 commit hash
cd /Users/yangyazhou/SakuraAgentTeam/backend/data/projects/$SID
git log --oneline

# 回滚到上一版本
curl -X POST http://localhost:8000/api/v1/projects/$SID/rollback \
  -H "Content-Type: application/json" \
  -d '{"commit_hash": "1f7b3c8"}'
```

## 步骤 8：停止服务

```bash
./deploy.sh stop
```

## 验收清单

跑完上述步骤后，确认：

- [ ] 后端 pytest 24/24 通过（现在 26/26）
- [ ] 前端 vite build 成功（1534 modules, 0 errors）
- [ ] 7/7 agent 全部 completed
- [ ] 项目目录有 7+ 文件（PRD.md / architecture.md / frontend/* / backend/*）
- [ ] git log 有 7+ commits（每个 agent 一个）
- [ ] docker compose config 验证通过（artifact.metadata["build_verified"] = True）

## 进阶：多 LLM Provider

```bash
# 切换到 Anthropic
cd backend
echo "ANTHROPIC_API_KEY=sk-ant-..." >> .env
echo "DEFAULT_LLM_PROVIDER=anthropic" >> .env
echo "DEFAULT_LLM_MODEL=claude-sonnet-4-20250514" >> .env

# 重启
./deploy.sh stop && ./deploy.sh dev
```

支持的 Provider：[OpenAI, Anthropic, Azure, OpenRouter, 本地模型（Ollama）] — 详见 [docs/references.md § 7](./references.md)。
