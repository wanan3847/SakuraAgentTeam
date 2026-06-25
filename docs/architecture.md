# 后端架构

> 给想深入理解 / 二次开发 SakuraAgentTeam 后端的工程师一份**实战导读**。
> 不讲空话,直接给代码入口 + 数据流。

---

## 0. 顶层一句话

```
SakuraAgentTeam 后端 = FastAPI + SQLAlchemy + LiteLLM + SSE + 7 种协作引擎
```

每一段都可以独立替换,但**约定 > 配置** 是底线 —— 路由 / 引擎 / 数据模型三者接口稳定,内部实现随便改。

---

## 1. 模块地图

```
backend/app/
├── api/                   # HTTP / SSE 路由层(对外)
│   ├── main.py            # FastAPI app 入口
│   ├── teams.py           # 4 个 chat 路由(per-user engine)
│   ├── routes.py          # experts / categories / presets
│   ├── connectors.py      # 第三方连接器
│   └── ...
│
├── orchestration/         # 协作引擎(7 种模式)
│   ├── agent_team.py      # get_engine / get_engine_for_user_async
│   ├── engine.py          # CollaborationEngine 核心
│   ├── workflows.py       # 7 种 Process 实现
│   ├── session.py         # 会话状态
│   ├── eventbus.py        # 事件总线(SSE 源头)
│   └── dynamic.py         # 动态建队
│
├── agents/                # 100+ 智能体定义
│   ├── base.py            # Agent 基类
│   ├── registry/          # 100+ agent 装载器
│   │   ├── creative.py    # 4 个创意类
│   │   ├── design.py      # 4 个设计类
│   │   ├── tech.py        # 7 个技术类
│   │   └── ...            # 共 13 个分类
│   └── ...
│
├── llm_providers/         # 用户 LLM 配置
│   ├── async_helpers.py   # build_llm_for_user_async(★ 核心)
│   ├── models.py          # CustomProvider 表
│   ├── registry.py        # 254 个内置供应商
│   └── routes.py          # 13 个 LLM API 端点
│
├── foundation/            # 基础设施
│   ├── llm/               # LLMProvider + MeteredLLMProvider
│   ├── tools/             # 10 个工具(file_edit / shell / grep / ...)
│   ├── skills/            # 11 个内置 Skill(generate_fullstack / tdd / diagnose / ...)
│   ├── mcp/               # MCP 客户端
│   ├── git_repo.py        # Git 仓库操作
│   ├── project.py         # 项目工作区
│   └── experience.py      # 经验库
│
├── auth/                  # 用户系统
│   ├── models.py          # User 表
│   ├── routes.py          # register / login / me
│   ├── jwt_utils.py       # JWT 签发 / 验证
│   ├── dependency.py      # get_current_user 依赖
│   └── database.py        # async_session / init_db
│
├── history/               # 历史记录
├── submissions/           # Agent 社区提交
└── core/                  # config / logging / sandbox
```

---

## 2. 请求生命周期(以 chat 为例)

```
浏览器 POST /api/v1/teams/{id}/chat
            │
            ▼
    api/teams.py:_stream_chat()
            │   user: User = Depends(get_current_user)  ← JWT 鉴权
            │   ↓
            │   1) 读 CustomProvider 表,选 is_default=true 的 LLM 配置
            │   2) build_llm_for_user_async(user.id) → MeteredLLMProvider
            │   3) llm_info SSE 事件先发,告诉前端"用的是你的 key"
            │   ↓
            ▼
    orchestration/agent_team.py:get_engine_for_user_async(user_id)
            │   每个 user_id 一个 CollaborationEngine,缓存到 _engines_by_user
            │   ↓
            ▼
    engine.py:CollaborationEngine.run(team, message, history, process)
            │   按 team.process 选 7 种 Process 之一
            │   循环:emit event → agent.run() → emit event
            │   ↓
            ▼
    workflows.py:GroupChatProcess / PipelineProcess / MasterProcess / ...
            │   每种 Process 决定:
            │   - 下一个发言者是谁
            │   - 是否终止
            │   - 事件如何 emit
            │   ↓
            ▼
    eventbus.py:EventBus.publish(CollaborationEvent)
            │   ↓
            ▼
    api/teams.py:_stream_chat() yield SSE
            │
            ▼
    浏览器 EventSource onmessage(event) → 更新 UI
```

**关键点**:
- `user_id` 沿请求一直传到 engine,engine 用它做 LLM provider 选择。
- SSE 是**单向**的:服务端 → 客户端。如果客户端要打断,只能断开连接。
- `MeteredLLMProvider` 包一层:每次 `achat()` 都记 token 用量,供 `/me/llm-config` 统计。

---

## 3. 7 种协作模式怎么挂上去的

`Process` 是一个协议,接受 `(team, message, history, ctx)` 返回 `AsyncIterator[CollaborationEvent]`。

```python
# orchestration/workflows.py
class GroupChatProcess:
    """群聊:按顺序循环发言,直到 max_rounds 或收敛。"""
    async def run(self, team, message, history, ctx):
        ...

class PipelineProcess:
    """流水线:每个 agent 处理一次,把上家输出当自己的输入。"""
    async def run(self, team, message, history, ctx):
        ...

class MasterProcess:
    """管家:CrewAI Hierarchical 风格,master 选下家。"""
    async def run(self, team, message, history, ctx):
        ...

class ConsensusProcess:
    """共识:AG2 GroupChat 风格,大家轮完一轮,主持人拍板。"""
    async def run(self, team, message, history, ctx):
        ...

class ParallelProcess:
    """并行:Anthropic Orchestrator-Workers 风格,所有 agent 并发跑。"""
    async def run(self, team, message, history, ctx):
        ...

class HandoffProcess:
    """转交:OpenAI Swarm 风格,agent 主动决定交棒给谁。"""
    async def run(self, team, message, history, ctx):
        ...

class GraphProcess:
    """状态图:LangGraph 风格,DAG + checkpoint。"""
    async def run(self, team, message, history, ctx):
        ...
```

**怎么新增一种模式**:
1. 继承 `BaseProcess`,实现 `run()`。
2. 在 `orchestration/workflows.py` 注册到 `PROCESS_REGISTRY`。
3. 在 `agents/types.py` 的 `ProcessType` 枚举加新值。
4. 前端 `HomePage` 的 `modeLabel` 映射加新值。

---

## 4. Per-user LLM 引擎(★ 本轮核心改动)

### 4.1 之前的问题

```python
# 老代码
async def chat(team_id, message):
    engine = get_engine()  # 永远用 .env 里的 OPENAI_API_KEY
    async for evt in engine.run(team, message, history):
        yield evt
```

**问题**:不管哪个用户登录,所有对话都走开发者共享 key,token 走开发者的额度,用户自己存的 key 完全没用。

### 4.2 现在

```python
# 新代码
async def chat(
    team_id: int,
    body: ChatBody,
    user: User = Depends(get_current_user),  # ← JWT 强制鉴权
):
    # 1. 用用户的 key 异步构建 LLM
    llm = await build_llm_for_user_async(user.id)
    # 2. 每个用户独立一个 engine,缓存到 _engines_by_user
    engine = await get_engine_for_user_async(user.id, llm_override=llm)
    # 3. 第一个 SSE 事件告诉前端"用的是你的 key"
    yield llm_info_event(llm)
    # 4. 跑对话
    async for evt in engine.run(team, message, history):
        yield evt
```

### 4.3 `build_llm_for_user_async()` 详解

```python
# backend/app/llm_providers/async_helpers.py
async def build_llm_for_user_async(user_id: int) -> Any:
    async with async_session() as session:
        # 1) 找 is_default=true 且 is_active=true 的
        cfg = await session.scalar(
            select(CustomProvider).where(
                CustomProvider.user_id == user_id,
                CustomProvider.is_default == True,
                CustomProvider.is_active == True,
            ).order_by(desc(CustomProvider.updated_at)).limit(1)
        )
        # 2) 退回到最新激活
        if cfg is None:
            cfg = await session.scalar(
                select(CustomProvider).where(
                    CustomProvider.user_id == user_id,
                    CustomProvider.is_active == True,
                ).order_by(desc(CustomProvider.updated_at)).limit(1)
            )

    if cfg is None:
        return _build_shared_llm()  # 兜底:用 .env 的开发者 key

    # 3) 根据 base_url + model 推断 provider 名称
    provider_name = _infer_provider_name(cfg.base_url, cfg.model)
    # 4) 用 LLMProviderFactory 构造
    inner = LLMProviderFactory.create(
        provider=provider_name,
        model=cfg.model or "gpt-4o-mini",
        api_key=cfg.api_key,
        base_url=cfg.base_url,
    )
    return MeteredLLMProvider(inner)  # 5) 包一层计费
```

### 4.4 数据流

```
用户登录
  ↓
POST /api/v1/auth/login
  ↓ 返回 {access_token, user}
  ↓
用户保存 LLM 配置
  ↓
POST /api/v1/llm/configs
  ↓ 写入 custom_providers 表
  ↓
用户发起对话
  ↓
POST /api/v1/teams/{id}/chat
  ↓
build_llm_for_user_async(user.id)
  ↓
SELECT * FROM custom_providers WHERE user_id=? AND is_default=true
  ↓
LLMProviderFactory.create(provider, model, api_key, base_url)
  ↓
MeteredLLMProvider(inner)  ← 计费包裹
  ↓
CollaborationEngine.run(...)
  ↓
SSE 流式输出
```

---

## 5. 数据模型(简表)

### 5.1 核心表

| 表 | 作用 | 关键字段 |
|----|------|---------|
| `users` | 用户 | `id`, `username`, `email`, `password_hash`, `is_admin` |
| `custom_providers` | 用户保存的 LLM | `user_id`, `provider_id`, `base_url`, `api_key`, `model`, `is_default`, `is_active` |
| `teams` | 团队 | `id`, `name`, `process`(group/pipeline/...), `member_ids` |
| `sessions` | 对话会话 | `id`, `user_id`, `team_id`, `created_at` |
| `messages` | 消息 | `session_id`, `role`, `content`, `agent_id`, `created_at` |
| `history` | 历史快照 | `user_id`, `team_id`, `last_message_at` |
| `submissions` | Agent 社区提交 | `user_id`, `agent_yaml`, `status`(pending/approved/rejected) |

### 5.2 关系

```
users 1─* custom_providers
users 1─* sessions
users 1─* history
users 1─* submissions

teams  1─* sessions
sessions 1─* messages
```

---

## 6. 异步 & 并发

### 6.1 为什么用 `async`

- **LLM 调用是 IO 密集型**:`await provider.achat(...)` 等响应时不占线程,FastAPI 同一进程能服务几百个并发请求。
- **SSE 流式**:每个 chat 连接一个长连接,`async generator` 自然支持。
- **多 agent 并行**:`ParallelProcess` 用 `asyncio.gather()` 同时调 N 个 agent,总耗时 ≈ max(t_i) 而不是 sum(t_i)。

### 6.2 工具并发

`base.py:AgentBase.run_tool()` 用 `asyncio.gather()` 并发跑多个独立工具调用,工具结果大于 8000 字符会写盘 + 摘要,避免撑爆 LLM 上下文。

### 6.3 锁

`CustomProvider.is_default` 更新用 `SELECT FOR UPDATE` 行锁,防止两个请求同时设 default。

---

## 7. 鉴权(JWT)

### 7.1 签发

```python
# auth/jwt_utils.py
def create_access_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.utcnow() + timedelta(hours=24),
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")
```

### 7.2 验证

```python
# auth/dependency.py
async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    payload = jwt.decode(token, SECRET, algorithms=["HS256"])
    user_id = int(payload["sub"])
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(401)
    return user
```

### 7.3 用法

```python
@router.post("/chat")
async def chat(
    body: ChatBody,
    user: User = Depends(get_current_user),  # ← 没 token 就 401
):
    ...
```

### 7.4 哪些路由要鉴权

| 路由 | 鉴权? | 说明 |
|------|--------|------|
| `GET /api/v1/experts` | ❌ | 公开 |
| `GET /api/v1/teams` | ❌ | 公开 |
| `POST /api/v1/teams/{id}/chat` | ✅ | 必填,per-user LLM |
| `POST /api/v1/auth/register` | ❌ | 公开 |
| `POST /api/v1/auth/login` | ❌ | 公开 |
| `GET /api/v1/me` | ✅ | |
| `GET /api/v1/me/llm-config` | ✅ | per-user LLM |
| `POST /api/v1/llm/configs` | ✅ | |
| `GET /api/v1/history` | ✅ | |
| `POST /api/v1/submissions` | ✅ | |

---

## 8. 借鉴的框架(在哪些文件里)

| 框架 | 借鉴点 | 在哪 |
|------|--------|------|
| **CrewAI** | `Agent` 4 件套 (role / goal / backstory / skills) + `Process.hierarchical` | `agents/base.py`, `workflows.py:MasterProcess` |
| **AG2 (AutoGen)** | `GroupChatManager` + 智能选择发言者 | `workflows.py:ConsensusProcess` |
| **Anthropic Multi-Agent** | Orchestrator-Workers 并行模式 | `workflows.py:ParallelProcess` |
| **MetaGPT** | 共享白板产物链 | `agents/base.py:_whiteboard` |
| **OpenAI Swarm** | Handoff 转交模式 | `workflows.py:HandoffProcess` |
| **LangGraph** | DAG 任务图 + checkpoint | `workflows.py:GraphProcess` |
| **Smolagents** | Agent Trace 执行追踪 | `agents/base.py:trace` |
| **LiteLLM** | 100+ LLM 供应商一行接入 | `foundation/llm/litellm_provider.py` |

---

## 9. 部署

### 9.1 单机

```bash
cd backend
python -m uvicorn app.api.main:app --host 0.0.0.0 --port 8000
```

### 9.2 Docker

```bash
cd infra
docker-compose up -d
```

`docker-compose.yml` 起 3 个容器:
- `backend` — FastAPI
- `frontend` — Nginx + 静态文件
- `sandbox` — 沙箱镜像(可选,跑 shell 工具用)

### 9.3 反向代理

生产环境建议 Nginx + Let's Encrypt,前端 `/api` 代理到 `backend:8000`,避免 CORS。

---

## 10. 测试

### 10.1 当前覆盖

```
backend/tests/
├── conftest.py
├── test_api.py                # 30+ 用例
├── test_cli.py                # 10+ 用例
├── test_connectors.py
├── test_deployment_agent.py
├── test_e2e_workflow.py
├── test_litellm_provider.py
├── test_llm.py
└── test_tools.py
```

### 10.2 跑测试

```bash
cd backend
pytest tests/ -v
pytest tests/ --cov=app --cov-report=term-missing
```

---

## 11. 性能 & 监控

### 11.1 关键指标

- **TTFT** (Time To First Token):`/chat` SSE 第一个事件到客户端的时间。目标 < 500ms。
- **Token / sec**:每个用户每小时消耗的 token,`MeteredLLMProvider` 记录。
- **并发 SSE 连接数**:`/api/v1/teams/{id}/chat` 长连接数。
- **Per-user engine 缓存命中**:`_engines_by_user` dict 命中 / 未命中比。

### 11.2 日志

`core/logging.py` 用 `structlog`,JSON 格式,字段:
- `event`:事件名(e.g. `chat_started`, `tool_called`)
- `user_id`:发起请求的用户
- `team_id`:团队
- `duration_ms`:耗时
- `tokens_in` / `tokens_out`:LLM 消耗

### 11.3 排错

| 现象 | 排查 |
|------|------|
| `401 Unauthorized` | JWT 过期 → 重新登录 |
| `429 Too Many Requests` | 中转站限流 → 换 key 或加 retry |
| `500` 配 LLM | `sakura me-llm` 看 `has_user_config` |
| SSE 卡住不发事件 | 看 `eventbus` 日志,`/chat` 第一个事件必是 `llm_info` |

---

## 12. 进一步阅读

- [docs/USER_LLM.md](./USER_LLM.md) — 用户 LLM key 流程
- [docs/CLI.md](./CLI.md) — CLI 命令行
- [docs/COLLABORATION_MODES.md](./COLLABORATION_MODES.md) — 7 种协作模式详解
- [docs/AGENT_GUIDE.md](./AGENT_GUIDE.md) — Agent 创建指南
- [CONTRIBUTING.md](../CONTRIBUTING.md) — 贡献指南
