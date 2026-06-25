# 用户 LLM Key 流程

> 本文档回答 3 个问题:
> 1. **为什么** SakuraAgentTeam 让每个用户填自己的 LLM Key?
> 2. **怎么用** —— 从注册到第一次对话的完整路径
> 3. **怎么排错** —— 遇到"我配了 Key 但 token 还是从开发者那里走" 怎么办

---

## 1. 为什么是"用户自己带 Key"

### 1.1 之前的问题

```
用户 A 登录 → 发对话
   ↓
后端 .env 里的 OPENAI_API_KEY (开发者付费的) → 调 DeepSeek
   ↓
token 走开发者账户 → 开发者破产
```

这种"开发者替所有人付账"的模式,有几个坏处:

| 问题 | 后果 |
|------|------|
| 开发者单点破产风险 | 一个用户滥用,所有人服务挂 |
| 用户不知道谁在付钱 | 用着心里不踏实 |
| 配额不灵活 | 公司用户需要走自己的 Azure OpenAI,不能 |
| 合规 | 企业数据走第三方 key,违反数据保护法规 |

### 1.2 现在的方案

```
用户 A 登录 → 在「我的 LLM」页填自己的 DeepSeek Key
   ↓
保存到 custom_providers 表(user_id=A, base_url=..., api_key=sk-...)
   ↓
A 发对话 → 后端读 A 的 custom_providers
   ↓
用 A 自己的 key 调 DeepSeek → token 走 A 的账户
```

**SakuraAgentTeam 服务器**只是个中转,**不收 token,也不存对话内容** —— 你的 key 你的对话你做主。

---

## 2. 完整使用路径

### 2.1 注册

1. 访问 <http://localhost:5173/register>
2. 填用户名 / 邮箱 / 密码
3. 提交 → 自动登录 → 跳到首页

### 2.2 配置自己的 LLM

#### 方式一:Web UI(推荐)

1. 顶栏右上角点头像 → 「我的 LLM」
2. 点「添加 LLM 配置」
3. 选厂商(254 个里挑一个)
4. 填 `display_name`(随便起,自己看) / `base_url` / `api_key` / `model`
5. 点「测试连接」(可选,但强烈建议)
6. 看到绿色 ✓ 后点「保存」
7. 在配置列表里,把这条设为「默认」

#### 方式二:CLI

```bash
# 1. 登录
sakura login

# 2. 填 LLM
sakura llm-save \
  --provider openai \
  --base-url https://api.deepseek.com/v1 \
  --api-key sk-... \
  --model deepseek-chat \
  --display-name "我的 DeepSeek" \
  --default
```

#### 方式三:cURL(直接调 API)

```bash
curl -X POST http://localhost:8000/api/v1/llm/configs \
  -H "Authorization: Bearer <your_jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "provider_id": "openai",
    "display_name": "我的 DeepSeek",
    "base_url": "https://api.deepseek.com/v1",
    "api_key": "sk-...",
    "model": "deepseek-chat",
    "is_default": true
  }'
```

### 2.3 验证配置生效

#### Web

进「我的 LLM」页面,应该看到:

```
✓ 我的 DeepSeek (default)
  提供商: openai (推断)
  模型:   deepseek-chat
  Base URL: https://api.deepseek.com/v1
  key:    sk-*** (已保存)
```

#### CLI

```bash
sakura me-llm
```

输出:

```
你的对话正在使用你自己保存的 LLM 配置 ↓
  名称:     我的 DeepSeek
  提供商:   openai
  模型:     deepseek-chat
  Base URL: https://api.deepseek.com/v1
  已保存 key: True
```

### 2.4 第一次对话

1. 顶栏「立即开始」→ 选一个预设团队(比如「论文写作小组」)
2. 输入消息
3. **第一个 SSE 事件** 必是 `llm_info`,前端会显示:

```
🟢 你的 DeepSeek · deepseek-chat
```

如果显示「开发者共享 key」,说明你的默认配置**没生效**,去「我的 LLM」检查。

---

## 3. 数据流详解

### 3.1 关键表

```sql
-- backend/.venv/.../sakura.db
CREATE TABLE custom_providers (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL,           -- ← 哪个用户
    provider_id   VARCHAR(64) NOT NULL,       -- 'openai' / 'anthropic' / ...
    display_name  VARCHAR(128) NOT NULL,      -- 用户自己起的名字
    base_url      VARCHAR(512) NOT NULL,
    api_key       VARCHAR(512) NOT NULL,      -- 加密存储
    model         VARCHAR(128),
    is_default    BOOLEAN DEFAULT FALSE,      -- 多个配置时哪个生效
    is_active     BOOLEAN DEFAULT TRUE,
    updated_at    DATETIME,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

### 3.2 关键代码

```python
# backend/app/llm_providers/async_helpers.py
async def build_llm_for_user_async(user_id: int) -> Any:
    """异步为指定用户构建 LLM provider"""
    async with async_session() as session:
        # 1) 优先 is_default=true 且 is_active=true
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
        return _build_shared_llm()  # 兜底:用 .env 开发者 key

    # 3) 根据 base_url 推断 provider_name
    provider_name = _infer_provider_name(cfg.base_url, cfg.model)
    # 4) LiteLLM / OpenAI / Anthropic 工厂方法
    inner = LLMProviderFactory.create(
        provider=provider_name,
        model=cfg.model or "gpt-4o-mini",
        api_key=cfg.api_key,
        base_url=cfg.base_url,
    )
    return MeteredLLMProvider(inner)  # 5) 计费包裹
```

### 3.3 Per-user engine

```python
# backend/app/orchestration/agent_team.py
_engines_by_user: dict[int, CollaborationEngine] = {}

async def get_engine_for_user_async(user_id: int) -> CollaborationEngine:
    """每个用户独立维护一个 CollaborationEngine"""
    if user_id not in _engines_by_user:
        llm = await build_llm_for_user_async(user_id)
        _engines_by_user[user_id] = CollaborationEngine(llm)
    return _engines_by_user[user_id]
```

---

## 4. 254 个供应商列表怎么用

### 4.1 列表 API

```bash
curl http://localhost:8000/api/v1/llm/providers | jq '.data[0:5]'
```

返回结构:

```json
{
  "id": "openai",
  "display_name": "OpenAI",
  "country": "美国",
  "default_base_url": "https://api.openai.com/v1",
  "default_model": "gpt-4o-mini",
  "auth_type": "bearer",
  "tags": ["协议类", "旗舰"]
}
```

### 4.2 常用配置模板

| 供应商 | base_url | model |
|--------|----------|-------|
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| Anthropic | `https://api.anthropic.com` | `claude-3-5-sonnet-20241022` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| 智谱 GLM | `https://open.bigmodel.cn/api/paas/v4` | `glm-4-flash` |
| Moonshot Kimi | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` |
| Ollama(本地) | `http://localhost:11434/v1` | `qwen2.5:7b` |
| 自定义 OpenAI 兼容 | `<你的端点>/v1` | `<你的模型名>` |

> 完整 254 个供应商清单:启动后访问 `GET /api/v1/llm/providers`,或 Web 端 ProvidersPage。

---

## 5. 故障排查

### 5.1 「我配了 Key,但 token 还是从开发者那里走」

**症状**:`sakura me-llm` 输出 `你还没有保存任何 LLM 配置 — 当前用开发者共享 key`

**排查**:

1. 查数据库:
   ```bash
   sqlite3 backend/data/sakura.db \
     "SELECT id, user_id, display_name, is_default, is_active FROM custom_providers"
   ```
   应该看到至少一行 `is_default=1, is_active=1`。

2. 如果没看到行 → 保存失败,看后端日志:
   ```bash
   # 后端
   tail -f backend/logs/*.log | grep llm_config
   ```

3. 如果有行但 `is_default=0` → 进 Web 把它设为默认,或:
   ```bash
   sakura llm-set-default <config_id>
   ```

4. 如果 `is_default=1` 但还是没用 → 检查 user_id 是否对得上:
   ```bash
   # 用户 A 的 id
   sakura whoami
   # 配置的 user_id
   sqlite3 ... "SELECT user_id FROM custom_providers"
   ```

### 5.2 「第一个 SSE 事件是 `source: shared`」

**症状**:浏览器 / CLI 显示「开发者共享 key」

**原因**:`build_llm_for_user_async()` 兜底逻辑被触发了 —— 没找到用户的 LLM 配置。

**修复**:回到 §5.1。

### 5.3 「测试连接失败」

**症状**:Web 端「测试连接」红色 ✗

**排查**:
- `base_url` 是否带 `/v1` 后缀?OpenAI 兼容端点通常需要。
- `api_key` 是否有空格 / 换行?
- `model` 名字是否拼写对?
- 直接 cURL 试一下:
  ```bash
  curl -X POST https://api.deepseek.com/v1/chat/completions \
    -H "Authorization: Bearer sk-..." \
    -H "Content-Type: application/json" \
    -d '{"model":"deepseek-chat","messages":[{"role":"user","content":"hi"}]}'
  ```

### 5.4 「对话走我的 key,但 LLM 报 401」

**症状**:SSE 流里看到 `401 Unauthorized`

**原因**:`api_key` 过期 / 余额不足 / 模型名配错。

**修复**:进「我的 LLM」,更新这条配置的 `api_key` 或 `model`。

### 5.5 「中转站限流」

**症状**:SSE 报 `Connection error` / `OpenAIException`

**原因**:你用的中转站并发上限太低,所有用户撞墙。

**修复**:
- 换更稳的中转站
- 自己用 LiteLLM / vLLM 部署
- 在 `.env` 加 retry:
  ```bash
  LLM_MAX_RETRIES=3
  LLM_RETRY_DELAY=1.0
  ```

---

## 6. 多配置策略

### 6.1 场景

- 配置 A:`deepseek-chat` (便宜,日常用)
- 配置 B:`claude-3-5-sonnet` (贵,关键任务)
- 配置 C:本地 Ollama (离线兜底)

### 6.2 用法

1. 全部保存到 `custom_providers`
2. 把 A 设为 `is_default=true`(日常)
3. 发对话时,如果 SSE 显示「用的是 A」,但你想切到 B:
   - 简单做法:进「我的 LLM」,把 B 设为 default
   - 高级做法:`/api/v1/llm/configs/{id}/activate` 临时激活

### 6.3 命令行切换

```bash
# 列出所有配置
sakura llm-list

# 切换默认
sakura llm-set-default <config_id>

# 临时使用(不修改默认)
sakura task --llm-config <config_id> "..."
```

---

## 7. 安全 & 隐私

### 7.1 Key 怎么存

- 数据库里**明文存**(SQLite 文件本身没加密)。
- 建议:生产环境**加密磁盘**(e.g. macOS FileVault) + 定期备份。
- 进阶:用 `cryptography.fernet` 包一层 key 加密,但**密钥放哪是新问题**。

### 7.2 Key 怎么传

- HTTPS only(生产)。
- Web 端 `api_key` 字段是 `<input type="password">`,不在 URL 出现。
- SSE 流里**不会**回显 api_key(只回 `has_api_key: true`)。

### 7.3 Key 怎么删

```bash
# Web:「我的 LLM」→ 选配置 → 「删除」
# CLI:
sakura llm-delete <config_id>
```

---

## 8. FAQ

**Q:一个 LLM 配置能给多个用户用吗?**
A:不能。每个用户的 key 独立,user_id 是天然隔离。

**Q:可以临时用开发者的 key 吗?**
A:可以。如果你的 `custom_providers` 表是空的,后端**自动**兜底用 `.env` 的 `OPENAI_API_KEY`。但 token 走开发者账户,长期不推荐。

**Q:为什么我有 2 个配置都 `is_default=true`?**
A:不允许。后端在切换默认时用事务 + 行锁,保证只有一个 default。早期手工 SQL 改的可能造成这种状态,跑 `sakura llm-fix-defaults` 修复。

**Q:本地 Ollama 配置后,前端一直说"连接失败"?**
A:Ollama 默认监听 `127.0.0.1:11434`,**不**对外开放。如果 SakuraAgentTeam 跑在 Docker,需要:
- `network_mode: host`,或
- 把 Ollama 也跑在 Docker,用 `docker network` 联通

**Q:能用同一个 key 配多个 base_url 吗?**
A:可以。每个配置独立存(`base_url` 字段是配置的一部分),一个 key 配 OpenAI 官方 + Azure OpenAI + 自建中转都行。

**Q:LLM key 在 URL 里行不行?**
A:不建议。base_url 不存 key,key 独立字段。

---

## 9. 进阶:per-call override

如果某次对话想**临时**用别的 LLM(不修改默认),可以加 query param:

```
POST /api/v1/teams/1/chat?llm_config_id=42
```

后端在 `teams.py:_stream_chat()` 第一行检查,临时覆盖。

> 还没实现,是个 TODO,本轮没做。

---

## 10. 参考

- [docs/ARCHITECTURE.md](./ARCHITECTURE.md) — 后端架构详解
- [docs/CLI.md](./CLI.md) — CLI 命令
- `/api/v1/llm/providers` — 254 个供应商列表
- `/api/v1/me/llm-config` — 我的 LLM 配置
- `sakura me-llm` — CLI 查询
- `sakura llm-save` / `llm-list` / `llm-set-default` / `llm-delete` — CLI 管理
