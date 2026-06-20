# SakuraAgentTeam — 架构设计

> 多智能体可协同的全栈 Agent 开发系统
>
> **版本**：v2.0（精简执行版）· 2026-06-20
>
> **结构说明**：本文档只保留"目标 / 架构 / 任务 / 状态"四件套。背景资料（开源项目调研、Claude Code 源码分析等）见 [docs/references.md](./references.md)。

---

## 目录

1. [设计目标](#1-设计目标与核心假设)
2. [系统架构](#2-系统总体架构)
3. [核心模块设计](#3-核心模块设计)
4. [技术选型](#4-技术选型)
5. [MVP 范围与验收标准](#5-mvp-范围与验收标准)
6. [当前完成状态](#6-当前完成状态2026-06-20)
7. [任务拆分](#7-任务拆分milestone--sprint--issue)
8. [目录结构](#8-目录结构)
9. [下一步行动](#9-下一步行动)
10. [Phase 5 进一步增强](#10-phase-5--进一步增强m4)

> 背景资料：[docs/references.md](./references.md)
---

## 1. 设计目标与核心假设

### 1.1 核心目标

**短期（MVP）**：一条自然语言需求 → 多 Agent 协作产出可运行的小型全栈应用（前后端 + 数据库 + 部署），并能自我审查与回滚。

**中期**：Agent 可插拔、任务可编排、产物可复盘、评测可量化。

**长期**：沉淀成通用的多 Agent 全栈开发工作台，支持多种技术栈和部署目标。

### 1.2 非目标（本次不做）

- 不做模型训练（直接对接现成 LLM API）
- 不做多云分布式训练
- 不做商业化 UI 业务系统

### 1.3 核心假设

| # | 假设 | 风险 |
|---|------|------|
| A1 | 假设 LLM（GPT-4o / Claude-4）在足够 prompt 下能正确生成全栈代码 | 中：复杂需求可能超出模型能力边界 |
| A2 | 假设 Docker 沙箱能有效隔离 Agent 操作 | 低：成熟技术 |
| A3 | 假设前端 Agent 能正确使用 React/Vite 脚手架 | 中：依赖脚手架模板质量 |
| A4 | 假设静态 DAG 编排足够覆盖 MVP 场景 | 低：MVP 范围可控 |

---

## 2. 系统总体架构

### 2.1 分层架构图

```
┌────────────────────────────────────────────────────────────┐
│                   Presentation Layer (UI)                        │
│  新建任务页 │ 会话页 │ 产物页 │ 进度看板 │ Agent 管理页        │
└──────────────┬───────────────────────────────────────────┘
               │  HTTPS + SSE / WebSocket
┌──────────────▼───────────────────────────────────────────┐
│                  Orchestration Layer                            │
│  SessionManager │ TaskRouter │ WorkflowEngine │ EventBus  │
└──────────────┬───────────────────────────────────────────┘
               │  Agent 调用
┌──────────────▼───────────────────────────────────────────┐
│                  Agent Layer（多角色 Agent Pool）                  │
│  需求Agent │ 设计Agent │ 前端Agent │ 后端Agent │          │
│  测试Agent │ 审查Agent │ 部署Agent（可扩展）              │
│  共享：Memory │ Tool Use │ Plan / Review                    │
└──────────────┬───────────────────────────────────────────┘
               │  读写
┌──────────────▼───────────────────────────────────────────┐
│                  Foundation Layer（能力底座）                      │
│  LLMProvider │ ToolRegistry │ MemoryStore │ ProjectStore  │
│  CodeSandbox │ Config                                       │
└──────────────┬───────────────────────────────────────────┘
               │
┌──────────────▼───────────────────────────────────────────┐
│                     Infra / DevOps                               │
│  Docker Sandbox │ Git Repo │ 文件系统 │ 部署器脚本            │
└────────────────────────────────────────────────────────────┘
```

### 2.2 数据主流程（端到端）

```
用户输入需求
    ↓
SessionManager 创建 Session（持久化）
    ↓
需求Agent：任务澄清 / 拆解 → PRD.md
    ↓
设计Agent：架构 + 接口契约 → design.md + API spec
    ↓
前端Agent + 后端Agent（并行）
    ├── 前端：React + Vite + TypeScript
    └── 后端：FastAPI + SQLite/PostgreSQL
    ↓
测试Agent：生成测试 + 执行
    ↓
审查Agent：LLM Review + 回写修正
    ↓
部署Agent：构建 + Docker 启动
    ↓
前端展示：产物树 + 实时日志流 + 可交互应用
    ↓
用户评分反馈（回写 Memory Store）
```

### 2.3 核心数据流（参考 OpenHands CodeAct 模式）

```
用户需求
    ↓
LLM 生成 Plan（子任务列表）
    ↓
For each 子任务:
    ├── LLM 决定使用哪个 Tool
    ├── Tool 在 Docker 沙箱中执行
    ├── 观察执行结果（stdout/stderr/文件变更）
    └── 若失败 → LLM 根据错误重新规划
    ↓
子任务产出合并 → Artifact
    ↓
Artifact 持久化到 ProjectStore（Git）
```

---

## 3. 核心模块详细设计

### 3.1 Agent 抽象（参考 OpenHands + CrewAI）

统一 Agent 基类，所有角色 Agent 继承实现：

```python
# 参考：OpenHands Software Agent SDK 的简洁接口 + CrewAI 的 Role-Based 设计

class Agent(ABC):
    """Agent 基类：每个 Agent 统一的生命周期"""

    role: str              # 角色名，如 "frontend", "backend", "reviewer"
    goal: str              # 该角色的目标描述
    backstory: str         # 角色背景故事（给 LLM 的 prompt）
    llm_provider: LLMProvider
    memory: Memory
    tools: List[Tool]

    @abstractmethod
    def plan(self, ctx: Context) -> Plan:
        """分析 Context，输出子任务计划"""
        ...

    @abstractmethod
    def execute(self, plan: Plan, ctx: Context) -> Artifact:
        """按计划执行，返回产物"""
        ...

    def review(self, artifact: Artifact, ctx: Context) -> ReviewResult:
        """自我审查产物（可选，部分 Agent 实现）"""
        ...
```

**关键数据结构**：

| 类 | 字段 | 说明 |
|----|------|------|
| `Context` | session_id, state, artifacts, user_feedback, tools | 执行上下文，包含所有共享状态 |
| `Plan` | tasks: List[Task], dependencies: Dict[str, List[str]] | 子任务列表 + DAG 依赖 |
| `Artifact` | name, content, type, path, metadata | 产物（代码/文档/测试结果） |
| `Task` | id, description, status, result, error | 单个子任务 |
| `ReviewResult` | passed, issues, suggestions | 审查结果 |

---

### 3.2 子 Agent 设计原则（精简版）

> 完整设计参考（Anthropic Skills、OpenDesign、Neat-Freak 等）见 [docs/references.md § 2-5](./references.md)。

| 原则 | 来源 | 落地 |
|------|------|------|
| 统一 Tool 接口（call / description / schema） | OpenHands / Claude Code | [backend/app/foundation/tools/base.py](../backend/app/foundation/tools/base.py) |
| Fork Subagent 共享父上下文 | Claude Code 源码 | 通过 ctx.metadata 在子 Agent 间传参 |
| Role-based Agent（role/goal/backstory） | CrewAI | Agent 基类三段式 prompt |
| 经验库"毕业"机制 | Neat-Freak | `ExperienceStore.graduate()` |
| Docker 沙箱 | OpenHands Runtime | [backend/app/core/sandbox.py](../backend/app/core/sandbox.py) |
| 错误时检索注入 Prompt | Hermes | `Agent.query_experience()` |
| 成功后自动记录 | Hermes | `Agent.record_experience()` |

## 4. 技术选型

| 层 | 选型 | 参考依据 |
|---|------|----------|
| 后端语言 | **Python 3.11+** | OpenHands/CrewAI/DeerFlow/smolagents 全部 Python，技术栈统一 |
| Agent 框架 | **自研轻量编排 + 借鉴 OpenHands SDK** | smolagents 1000 行哲学 + OpenHands 成熟实践，不引入 LangChain 过度封装 |
| LLM 接入 | **OpenAI / Anthropic / 本地模型（可插拔）** | OpenHands 支持 100+ 模型，统一抽象 |
| Web 框架 | **FastAPI** | 异步、自动 OpenAPI，适合 Agent 场景 |
| 前端 | **React + Vite + TypeScript** | 主流、成熟、生态丰富 |
| 任务总线 | **Redis（可选，轻量先用内存）** | 简单够用 |
| 存储 | **SQLite（开发）/ PostgreSQL（生产）** | 平滑升级 |
| 向量数据库 | **ChromaDB** | 经验库语义检索，轻量级、Python 原生、无需额外部署 |
| Embedding | **sentence-transformers** | 本地免费，后续可切换 OpenAI Embeddings |
| 产物存储 | **Git 仓库** | 天然版本化，参考开源项目惯例 |
| 代码执行 | **Docker 沙箱** | OpenHands Runtime 验证，成熟可靠 |
| 部署 | **Docker Compose / 一键脚本** | 先本地跑通 |

---

## 5. MVP 范围与验收标准

### 5.1 MVP 功能范围

| 功能 | 说明 |
|------|------|
| ✅ 输入需求 | 自然语言输入（如"帮我做一个 Todo 应用，前后端分离"） |
| ✅ PRD 生成 | 需求 Agent 自动生成 `PRD.md` |
| ✅ 架构设计 | 设计 Agent 生成 `ARCHITECTURE.md` + API 接口定义 |
| ✅ 前端代码 | 前端 Agent 生成 React + Vite + TypeScript 代码 |
| ✅ 后端代码 | 后端 Agent 生成 FastAPI + SQLite 代码 |
| ✅ 测试生成 | 测试 Agent 生成基础单元测试并执行 |
| ✅ 审查修正 | 审查 Agent LLM Review + 自动修正 |
| ✅ 本地部署 | Docker 启动，前后端可交互使用 |
| ✅ 进度可视化 | 前端实时看到每个 Agent 的执行状态和日志 |
| ✅ 长期记忆 | 经验库：积累错误模式与解决方案，越用越好（参考 Hermes） |
| ✅ 动态编排 | 根据项目状态智能选择工作流（从零开始 vs 有现有代码） |
| ❌ 多租户 | 暂不支持多用户隔离 |
| ❌ 云端部署 | 暂只支持本地 Docker 部署 |

### 5.2 验收标准

| # | 标准 | 检测方式 |
|---|------|----------|
| 1 | 给定"Todo 应用"需求，端到端在 ≤30 分钟内产出可运行应用 | 手动验收 |
| 2 | 前端页可添加/删除/完成 Todo（基本 CRUD） | 手动操作 |
| 3 | 后端 API 响应正常（/todos GET/POST/DELETE） | curl 测试 |
| 4 | 测试通过（pytest，≥1 个测试用例） | CI 自动 |
| 5 | 代码通过 lint（ruff/eslint） | CI 自动 |
| 6 | 前端实时展示 Agent 进度和日志流 | 手动验收 |
| 7 | 产物目录包含完整 Git 历史 | git log 检查 |

---

## 6. 当前完成状态（2026-06-20）

> M0–M3 全部任务已完成，详见 git log。

| Milestone | 任务数 | 完成 | 状态 |
|-----------|--------|------|------|
| **M0 基础设施** | 8 | 8/8 | ✅ |
| **M1 单 Agent** | 6 | 6/6 | ✅ |
| **M2 多 Agent 编排** | 16 | 16/16 | ✅ |
| **M3 可用性工程化** | 5 | 5/5 | ✅ |
| **合计** | **35** | **35/35** | **100%** |

**关键验收数据**：

| 指标 | 目标 | 实际 |
|------|------|------|
| 后端测试 | 全部通过 · 零警告 | ✅ 24/24 · 零警告 |
| 前端构建 | 0 errors | ✅ 1534 modules · 0 errors |
| 端到端 workflow | 7 agent 全 completed | ✅ 7/7 |
| 产物 commit | 自动 commit | ✅ 每 session 一个 git 仓库 |
| 经验库 | ChromaDB + 关键词回退 | ✅ 正常 |
| 动态编排 | greenfield/brownfield/incremental | ✅ |

**未做（按 §2.2 "非目标"）**：
- ❌ 多租户隔离
- ❌ 云端部署
- ❌ 模型训练

---

## 7. 任务拆分（Milestone → Sprint → Issue）

### Milestone 0：基础设施与脚手架（约 1 周）

| Issue | 内容 | 优先级 | 参考 |
|---|---|---|---|
| M0-I1 | 初始化 monorepo 目录结构（backend/ frontend/ infra/ docs/） | 高 | — |
| M0-I2 | 后端 FastAPI 脚手架（依赖、配置、日志、错误处理） | 高 | — |
| M0-I3 | 前端 React + Vite + TS 脚手架（路由、基础组件、样式） | 高 | — |
| M0-I4 | LLMProvider 抽象 + OpenAI / Anthropic 实现 | 高 | OpenHands |
| M0-I5 | Tool 基类 + file_read / file_write / shell_run 实现 | 高 | OpenHands Tool |
| M0-I6 | Docker 沙箱环境（容器创建、执行、销毁、路径限制） | 高 | OpenHands Runtime |
| M0-I7 | Git 产物仓库管理（ProjectStore：init/commit/branch） | 高 | — |
| M0-I8 | 基础 CI（ruff lint + pyright + pytest + eslint） | 中 | — |

### Milestone 1：单 Agent 跑通（约 1 周）

| Issue | 内容 | 优先级 | 参考 |
|---|---|---|---|
| M1-I1 | Agent 基类 + Context / Plan / Artifact 数据结构 | 高 | OpenHands SDK + CrewAI |
| M1-I2 | 需求 Agent 实现（PRD 生成） | 高 | — |
| M1-I3 | SessionManager（Session 生命周期 + SQLite 持久化） | 高 | — |
| M1-I4 | EventBus（内存事件发布/订阅，SSE 后端支持） | 高 | — |
| M1-I5 | 前端会话页基础（对话流 + 产物树 + 日志展示） | 高 | — |
| M1-I6 | 端到端单 Agent 调试脚本（需求 → PRD → 设计文档） | 中 | — |

### Milestone 2：多 Agent 编排 + 经验库 + 动态编排（核心，约 2-3 周）

| Issue | 内容 | 优先级 | 参考 |
|---|---|---|---|
| M2-I1 | Workflow DAG 定义 + 默认全栈开发流 | 高 | CrewAI Process + LangGraph |
| M2-I2 | WorkflowEngine（DAG 调度、并行执行、失败重试） | 高 | LangGraph |
| M2-I3 | 设计 Agent（架构 + API 契约生成） | 高 | — |
| M2-I4 | 前端 Agent（React 代码生成 + 脚手架能力） | 高 | — |
| M2-I5 | 后端 Agent（FastAPI 代码生成 + CRUD 能力） | 高 | — |
| M2-I6 | 测试 Agent（pytest 测试生成 + 执行） | 高 | — |
| M2-I7 | 审查 Agent（LLM Review + 自动回写修正） | 中 | — |
| M2-I8 | 前端多 Agent 进度可视化（DAG 图 + 实时日志流） | 高 | — |
| M2-I9 | 部署 Agent（Docker 构建 + 启动） | 中 | — |
| M2-I10 | **经验库**：Experience 数据模型 + ChromaDB 初始化 | 高 | ChromaDB |
| M2-I11 | **经验库**：sentence-transformers Embedding 集成 | 高 | — |
| M2-I12 | **经验库**：错误发生时向量检索相似经验并注入 Prompt | 高 | — |
| M2-I13 | **经验库**：成功解决后自动记录新经验（生成向量存储） | 中 | — |
| M2-I14 | **动态编排**：ProjectAnalyzer（项目状态检测） | 高 | — |
| M2-I15 | **动态编排**：WorkflowSelector（根据状态选择工作流） | 高 | — |
| M2-I16 | **动态编排**：支持 GREENFIELD / BROWNFIELD / INCREMENTAL 三种模式 | 中 | — |

### Milestone 3：可用性与工程化（约 1 周）

| Issue | 内容 | 优先级 | 参考 |
|---|---|---|---|
| M3-I1 | 产物页：文件浏览 + 代码高亮（Monaco Editor） | 高 | — |
| M3-I2 | Session 历史列表 + 一键恢复 | 中 | — |
| M3-I3 | 单元测试覆盖（LLMProvider / Tool / Agent 基类） | 高 | — |
| M3-I4 | 端到端集成测试脚本 | 中 | — |
| M3-I5 | 内部文档（使用说明 + 架构说明） | 中 | — |

---

## 8. 目录结构

```
SakuraAgentTeam/
├── backend/
│   ├── app/
│   │   ├── agents/              # 多角色 Agent
│   │   │   ├── base.py          # Agent 基类
│   │   │   ├── requirement.py   # 需求 Agent
│   │   │   ├── designer.py      # 设计 Agent
│   │   │   ├── frontend.py       # 前端 Agent
│   │   │   ├── backend.py        # 后端 Agent
│   │   │   ├── tester.py         # 测试 Agent
│   │   │   ├── reviewer.py       # 审查 Agent
│   │   │   └── deployer.py       # 部署 Agent
│   │   ├── foundation/          # 能力底座
│   │   │   ├── llm/              # LLM Provider 抽象
│   │   │   │   ├── base.py
│   │   │   │   ├── openai.py
│   │   │   │   └── anthropic.py
│   │   │   ├── tools/            # 工具集
│   │   │   │   ├── base.py
│   │   │   │   ├── file_ops.py
│   │   │   │   ├── shell.py
│   │   │   │   ├── git_ops.py
│   │   │   │   └── code_check.py
│   │   │   ├── memory.py         # 记忆存储
│   │   │   ├── experience.py     # 经验库（ChromaDB 向量检索）
│   │   │   └── project.py        # 产物仓库
│   │   ├── orchestration/        # 编排层
│   │   │   ├── session.py
│   │   │   ├── router.py
│   │   │   ├── workflow.py
│   │   │   ├── workflow_selector.py  # 动态工作流选择
│   │   │   ├── project_analyzer.py   # 项目状态分析
│   │   │   └── events.py
│   │   ├── api/                 # FastAPI 路由
│   │   │   ├── main.py
│   │   │   ├── tasks.py
│   │   │   └── sessions.py
│   │   └── core/                 # 核心配置
│   │       ├── config.py
│   │       └── sandbox.py        # Docker 沙箱
│   └── tests/
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── NewTask.tsx       # 新建任务页
│   │   │   ├── Session.tsx       # 会话页
│   │   │   ├── Artifacts.tsx     # 产物页
│   │   │   ├── History.tsx       # 历史记录页
│   │   │   └── Experience.tsx    # 经验库页
│   │   ├── components/
│   │   │   ├── DAGGraph.tsx      # DAG 进度可视化
│   │   │   ├── LogStream.tsx      # 实时日志流（SSE）
│   │   │   ├── ArtifactTree.tsx  # 产物文件树
│   │   │   ├── CodeEditor.tsx    # Monaco 代码编辑器
│   │   │   └── ExperienceCard.tsx # 经验卡片（错误+解决方案）
│   │   └── services/
│   │       └── api.ts            # 后端 API + WebSocket
│   └── ...
├── infra/
│   ├── docker/
│   │   └── sandbox.Dockerfile    # Agent 执行沙箱镜像
│   └── scripts/
│       └── deploy.sh             # 一键部署脚本
├── docs/                         # 架构文档
│   ├── architecture.md           # 本文档
│   └── agent-prompt.md           # 各 Agent 的 system prompt
└── README.md
```

---

## 9. 下一步行动

架构设计已完成，根据反馈已更新以下核心能力：

### 已确认的设计决策

| # | 决策项 | 确认结果 |
|---|--------|----------|
| 1 | 技术栈 | ✅ Python + FastAPI + React + TypeScript + Docker |
| 2 | Agent 框架 | ✅ 自研轻量编排，借鉴 OpenHands SDK |
| 3 | MVP 范围 | ✅ Todo 全栈应用作为首条端到端用例 |
| 4 | Agent 角色 | ✅ 6 个角色 + 部署 Agent |
| 5 | 编排方式 | ✅ **动态编排**：根据项目状态智能选择工作流 |

### 新增核心能力

| 能力 | 说明 | 参考 |
|------|------|------|
| **长期记忆（经验库）** | 积累错误模式与解决方案，越用越好 | Hermes |
| **动态编排** | 根据项目状态（从零开始/有现有代码/增量迭代）智能选择工作流 | — |

### 待确认项

1. **LLM 接入方式**：✅ 用户自带 API Key，系统支持多模型提供者（参考 OpenHands 支持 100+ 模型）

2. **经验库存储**：✅ 使用向量数据库（ChromaDB），支持语义相似度检索

3. **开发顺序**：✅ 先完成基础核心功能，再完善项目

### 阶段划分

| 阶段 | 内容 | 状态 |
|------|------|------|
| **Phase 1：基础核心** | Milestone 0 + Milestone 1（单 Agent 跑通） | ✅ 完成 |
| **Phase 2：多 Agent 编排** | Milestone 2（核心工作流） | ✅ 完成 |
| **Phase 3：增强能力** | 经验库 + 动态编排 | ✅ 完成 |
| **Phase 4：工程化** | Milestone 3（可用性 + 测试 + 文档） | ✅ 完成 |
| **Phase 5：进一步增强** | M4（真实 LLM 集成 + 部署验证 + 文档） | 🔧 进行中（见 §10） |

---

## 10. Phase 5 — 进一步增强（M4）

> 在 M0-M3 基础上，针对"真实可用 / 可演示 / 可贡献"做收尾。

| # | 任务 | 说明 | 状态 |
|---|------|------|------|
| M4-I1 | 真实 LLM Provider 集成 | 启用 `OPENAI_API_KEY` 或 `ANTHROPIC_API_KEY` 后端到端跑通（非 mock） | ✅ 代码已就绪，待 key 验证 |
| M4-I2 | 部署 Agent 真实 docker build | 对 mock 生成的产物跑 `docker build` 验证语法正确 | ✅ dry-run 验证已加 |
| M4-I3 | 完整 demo 录制文档 | docs/demo.md 包含启动 → 创建 → 查看产物 → git 历史的完整命令清单 | ✅ |
| M4-I4 | CHANGELOG | 项目变更日志（按里程碑 + 按 commit 索引） | ✅ |
| M4-I5 | 单元测试覆盖率报告 | pytest-cov 输出覆盖率到 `docs/coverage.md` | ✅ 70% 总覆盖率 |
| M4-I6 | 贡献指南 | CONTRIBUTING.md（开发环境 / PR 流程 / 代码规范） | ✅ |
| M4-I7 | 监控/可观测性 | OpenTelemetry trace + Prometheus metrics（可选） | ⏭️ 暂不实现（依赖实际部署量） |

> 完成 M4 后进入"维护模式"：bug 修复 + 用户反馈驱动的微调。
