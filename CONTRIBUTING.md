# 贡献指南

欢迎为 SakuraAgentTeam 贡献代码、文档、Issue。本指南帮助你快速上手。

---

## 1. 行为准则

- 友善、专业、尊重他人
- 讨论对事不对人
- 接受建设性反馈，以项目目标为先

---

## 2. 开发环境

| 工具 | 版本 | 说明 |
|------|------|------|
| Python | ≥ 3.11 | 后端运行时 |
| Node.js | ≥ 20 | 前端运行时 |
| Docker | ≥ 24 | 沙箱 + 部署验证（可选） |
| Git | ≥ 2.40 | 产物仓库 |
| [uv](https://github.com/astral-sh/uv) | latest | Python 依赖管理（推荐） |

macOS 一键安装：

```bash
brew install python@3.11 node@20 git docker
```

---

## 3. 5 分钟跑通

```bash
# 克隆
git clone https://github.com/wanan3847/SakuraAgentTeam.git
cd SakuraAgentTeam

# 一键启动（自动创建 venv + 安装依赖 + 启动前后端）
./deploy.sh dev

# 浏览器打开
open http://localhost:5173
```

> 需要至少一个 LLM Key（`OPENAI_API_KEY` 或 `ANTHROPIC_API_KEY`）才能跑真实端到端；
> 不填则使用 mock，所有 Agent 走离线分支。

---

## 4. 项目结构

```
SakuraAgentTeam/
├── backend/                  # FastAPI 后端
│   ├── app/
│   │   ├── agents/           # 7 个角色 Agent
│   │   ├── api/              # HTTP/SSE 路由
│   │   ├── core/             # config / logging / sandbox
│   │   ├── foundation/       # LLM / 工具 / Git / 经验库
│   │   └── orchestration/    # Session / Engine / Workflow
│   ├── tests/                # pytest 测试
│   └── pyproject.toml
├── frontend/                 # React + Vite 前端
│   ├── src/pages/            # 6 个页面
│   └── src/services/api.ts   # API 客户端
├── docs/                     # 架构 / 演示 / 覆盖报告
├── infra/                    # Docker Compose / Sandbox 镜像
├── deploy.sh                 # 一键启动脚本
└── .github/workflows/ci.yml  # CI：lint + test + build
```

---

## 5. 开发规范

### 5.1 Python

- **Linter**：[Ruff](https://github.com/astral-sh/ruff)（集成 `pyflakes` / `isort` / `bugbear` / `pyupgrade`）
- **Formatter**：Ruff format（line-length=100）
- **Type check**：[Pyright](https://github.com/microsoft/pyright)（basic 模式）

```bash
cd backend

# 修复 + 检查
ruff check . --fix
ruff format .

# 类型检查
pyright app

# 一次性跑全部
ruff check . && ruff format --check . && pyright app
```

### 5.2 TypeScript / React

- **Linter**：ESLint（`@typescript-eslint` + `react-hooks`）
- **Formatter**：Prettier（默认配置）
- **Type check**：`tsc --noEmit`

```bash
cd frontend

npm run lint
npx tsc --noEmit
npm run build
```

### 5.3 通用

- 写新模块必须配单元测试（目标覆盖率 ≥ 当前模块均值）
- 公开函数加 docstring（中文，简短）
- 不引入新依赖前先开 Issue 讨论
- 一次 PR 只做一件事（避免超大型 diff）

---

## 6. 测试

```bash
cd backend

# 跑全部测试
pytest tests/ -v

# 跑单个文件
pytest tests/test_deployment_agent.py -v

# 覆盖率报告
pytest tests/ --cov=app --cov-report=term-missing

# 当前总覆盖率：70%（详见 docs/coverage.md）
```

测试约定：

- 文件名 `test_*.py`，函数名 `test_*`
- 异步测试用 `pytest-asyncio`（`asyncio_mode = "auto"`，无需手动 mark）
- HTTP 测试用 `httpx.AsyncClient` + `ASGITransport`，不依赖真实端口
- 临时文件用 `tmp_path` fixture，不污染工作区

---

## 7. 提 PR 流程

1. **Fork + 分支**
   ```bash
   git checkout -b feat/my-change
   ```

2. **开发 + 自检**
   ```bash
   # 后端
   cd backend && ruff check . && pyright app && pytest tests/

   # 前端
   cd frontend && npm run lint && npx tsc --noEmit && npm run build
   ```

3. **提交**
   ```bash
   git add -A
   git commit -m "feat(scope): 简明描述变更"
   git push origin feat/my-change
   ```

4. **开 PR**
   - 标题：`feat / fix / refactor / docs / test(scope): 描述`
   - 描述：What / Why / How，可附截图或日志
   - 关联相关 Issue

5. **CI 通过 + 至少 1 位维护者 Review 后合并**

---

## 8. Commit 规范

采用 [Conventional Commits](https://www.conventionalcommits.org/) 简化版：

```
<type>(<scope>): <subject>

<body>

<footer>
```

| type | 说明 |
|------|------|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `refactor` | 重构（无功能变化） |
| `docs` | 文档变更 |
| `test` | 测试增删改 |
| `chore` | 构建 / CI / 依赖 |
| `style` | 格式（无逻辑变化） |

scope 示例：`agents`、`api`、`orchestration`、`frontend`、`ci`。

---

## 9. 文档

| 文档 | 用途 |
|------|------|
| [README.md](./README.md) | 项目入口 / 5 分钟跑通 |
| [docs/architecture.md](./docs/architecture.md) | 系统设计（M0-M4 全景） |
| [docs/references.md](./docs/references.md) | 开源项目调研背景 |
| [docs/demo.md](./docs/demo.md) | 端到端演示命令清单 |
| [docs/coverage.md](./docs/coverage.md) | 测试覆盖率报告 |
| [CHANGELOG.md](./CHANGELOG.md) | 版本变更日志 |
| [docs/usage.md](./docs/usage.md) | API 使用说明 |

修改架构、API、新增依赖时，同步更新对应文档。

---

## 10. 遇到问题？

1. 先搜 [Issues](https://github.com/wanan3847/SakuraAgentTeam/issues) 看是否有人提过
2. 提新 Issue 时附：
   - 复现步骤
   - 期望 vs 实际
   - 环境（OS / Python / Node 版本）
   - 关键日志

---

## 11. 许可证

贡献的代码默认采用 [MIT](./LICENSE) 协议。提交 PR 即表示同意。
