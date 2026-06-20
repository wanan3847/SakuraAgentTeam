# SakuraAgentTeam — 多智能体可协同全栈 Agent 开发系统

> 架构设计文档 · v1.0 · 2025-06-20
>
> 本文档结合对 GitHub 优秀开源项目的调研（上半部分），与本项目的架构设计（下半部分）合并呈现，供立项审阅与团队协作参考。

---

## 目录

1. [行业现状与开源参考](#1-行业现状与开源参考)
2. [设计目标与核心假设](#2-设计目标与核心假设)
3. [系统总体架构](#3-系统总体架构)
4. [核心模块详细设计](#4-核心模块详细设计)
5. [技术选型](#5-技术选型)
6. [MVP 范围与验收标准](#6-mvp-范围与验收标准)
7. [任务拆分（Milestone → Sprint → Issue）](#7-任务拆分milestone--sprint--issue)
8. [目录结构](#8-目录结构)
9. [下一步行动](#9-下一步行动)

---

## 1. 行业现状与开源参考

### 1.1 2025-2026 年 AI Agent 格局概览

2025 年是 AI Agent 爆发元年。GitHub 上涌现了大量优质开源项目，按能力可分为三类：

| 类别 | 代表项目 | 核心特点 | Stars |
|------|----------|----------|-------|
| **AI 软件工程师（代码 Agent）** | [OpenHands](https://github.com/All-Hands-AI/OpenHands)（原 OpenDevin） | SWE-bench 72%、CodeAct、Runtime 沙箱、100+ LLM 支持、Software Agent SDK 重构 | 64k |
| | [Claude Code](https://docs.anthropic.com/en/docs/claude-code) | Agent Teams（16 个子 Agent 并行）、百万上下文、工程化思维 | — |
| **多 Agent 协作编排** | [CrewAI](https://github.com/crewai/crewai) | 角色+任务+Crew+工具+流程（Process），配置驱动，易上手 | 活跃 |
| | [LangGraph](https://github.com/langchain-ai/langgraph) | 图结构有状态编排、DAG 调度、生产级，来自 LangChain 团队 | 19.4k |
| **轻量 Agent 框架** | [smolagents](https://github.com/huggingface/smolagents)（HuggingFace） | ~1000 行核心代码、代码驱动 Agent、透明简洁 | 23.2k |
| | [DeerFlow](https://github.com/bytedance/deer-flow)（字节跳动） | 深度研究、多 Agent + 搜索 + 代码 + 网页操作、科研报告生成 | 17.3k |
| | [SuperAGI](https://github.com/transformer-optimus/SuperAGI) | 扩展性强、多 Agent 管理、工具市场 | 16.8k |
| **系统提示词研究** | [system-prompts-and-models-of-ai-tools](https://github.com/TransformerOptimus/system-prompts-and-models-of-ai-tools) | 收集 Devin/Cursor/Replit Agent 的核心 Prompt 和工具定义 | 134k |

### 1.2 关键开源项目深度解析

#### 1.2.1 OpenHands（最值得参考）

**核心定位**：自主 AI 软件工程师，首个 SWE-bench 得分超 50%（现 72%）的开源项目。

**架构亮点**：
- **Runtime 层**：Environment + Docker Sandbox 安全执行代码，防止 Agent 乱操作文件系统。
- **CodeAct Agent**：允许 Agent 在循环中编辑/执行代码，支持迭代修改（写→执行→观察→修正）。
- **Software Agent SDK（2025 重构）**：简洁接口，默认仅需几行代码即可定义一个 Agent，同时保留高度可配置性。
- **多模型支持**：统一 LLM Provider 抽象，支持 100+ 种模型后端。
- **评估框架**：内置 SWE-bench 评估基准，产物可量化对比。

**值得借鉴**：
- Docker 沙箱隔离（安全执行）
- 统一 Tool 接口 + 插件系统
- CodeAct 迭代执行模式（写-执行-反馈循环）
- 可量化的评测体系

#### 1.2.2 Claude Code 源码泄露分析（2026.03）

**事件概述**：2026年3月31日，Anthropic 的 Claude Code v2.1.88 npm 包中因 `.npmignore` 配置错误，意外包含了 59.8MB 的 Source Map 文件，完整暴露了 **51万行 TypeScript 源代码**。

**泄露规模**：

| 指标 | 数值 |
|------|------|
| TypeScript 文件 | 1,906 |
| 代码行数 | 512,847 |
| Source Map 大小 | 59.8 MB |
| 工具模块 | 40+ |
| 隐藏功能标志 | 44 |

**技术栈**：Bun + TypeScript + React/Ink（终端 UI）

**核心架构发现**：

| 模块 | 路径 | 功能 |
|------|------|------|
| **Tool 抽象** | `src/Tool.ts` | 统一工具接口：call、description、inputSchema、checkPermissions、prompt |
| **Task 系统** | `src/Task.ts` | 任务类型：local_bash、local_agent、remote_agent、in_process_teammate、dream |
| **Coordinator 模式** | `src/coordinator/coordinatorMode.ts` | 协调者模式：调度多个并行 Worker 处理复杂工作流 |
| **AgentTool** | `src/tools/AgentTool/` | 子代理工具：支持 fork 子代理、worker 类型 |
| **内置 Agent** | `src/tools/AgentTool/built-in/` | 6 个内置 Agent：generalPurpose、plan、explore、verification、claudeCodeGuide、statuslineSetup |

**Tool 接口设计（核心参考）**：

```typescript
// Claude Code 的 Tool 抽象（简化版）
type Tool<Input, Output, P> = {
  name: string
  aliases?: string[]
  inputSchema: ZodSchema<Input>
  outputSchema?: ZodSchema<Output>

  // 核心方法
  call(args: Input, context: ToolUseContext, canUseTool: CanUseToolFn,
       parentMessage: AssistantMessage, onProgress?: ToolCallProgress<P>): Promise<ToolResult<Output>>

  // 描述与权限
  description(input: Input, options): Promise<string>
  checkPermissions(input: Input, context: ToolUseContext): Promise<PermissionResult>
  prompt(options): Promise<string>

  // 生命周期钩子
  isEnabled(): boolean
  isConcurrencySafe(input: Input): boolean
  isReadOnly(input: Input): boolean
  isDestructive?(input: Input): boolean

  // UI 渲染
  renderToolUseMessage(input: Partial<Input>, options): React.ReactNode
  renderToolResultMessage?(content: Output, progressMessages, options): React.ReactNode
}
```

**Coordinator 模式（多 Agent 编排核心）**：

```typescript
// Claude Code 的协调者模式
// 一个 Coordinator 调度多个 Worker 并行执行任务

// Coordinator 的 System Prompt 核心逻辑
"You are a coordinator. Your job is to:
- Help the user achieve their goal
- Direct workers to research, implement and verify code changes
- Synthesize results and communicate with the user
- Answer questions directly when possible

Your Tools:
- AgentTool - Spawn a new worker
- SendMessageTool - Continue an existing worker
- TaskStopTool - Stop a running worker

Workers have access to standard tools, MCP tools, and project skills.
Delegate skill invocations to workers."
```

**内置 Agent 类型**：

| Agent 类型 | 文件 | 用途 |
|-----------|------|------|
| `generalPurposeAgent` | generalPurposeAgent.ts | 通用任务处理 |
| `planAgent` | planAgent.ts | 规划与任务拆解 |
| `exploreAgent` | exploreAgent.ts | 代码探索与研究 |
| `verificationAgent` | verificationAgent.ts | 验证与测试 |
| `claudeCodeGuideAgent` | claudeCodeGuideAgent.ts | Claude Code 使用指南 |
| `statuslineSetup` | statuslineSetup.ts | 状态栏配置 |

**隐藏功能发现**：

| 功能 | 说明 |
|------|------|
| **KAIROS** | 自主守护进程模式，后台运行，用户空闲时进行记忆整合 |
| **Undercover Mode** | 潜伏模式，匿名向开源项目贡献代码 |
| **Capybara 模型** | Claude 5 系列内部代号 |
| **Buddy** | 虚拟宠物系统 |
| **Fork Subagent** | 子代理 Fork 机制，共享父代理上下文和缓存 |

**值得借鉴的设计**：

1. **Tool 抽象**：统一的 Tool 接口，包含 call、checkPermissions、prompt、render 等完整生命周期
2. **Coordinator 模式**：一个协调者 + 多个 Worker 的多 Agent 编排模式
3. **Fork 机制**：子代理可以 Fork 自己，共享父代理的上下文和 Prompt Cache
4. **权限系统**：每个 Tool 都有 checkPermissions 方法，支持 alwaysAllow/alwaysDeny/alwaysAsk 规则
5. **进度反馈**：ToolCallProgress 回调，实时反馈执行进度
6. **UI 渲染**：每个 Tool 可以自定义 renderToolUseMessage 和 renderToolResultMessage

**源码位置**：已下载到 `reference/claude-code-source/src/`

#### 1.2.3 CrewAI（多 Agent 协作范式）

**核心定位**：角色扮演式多 Agent 团队编排框架。

**架构亮点**：
- **5 个核心概念**：Agent（角色+能力边界）、Task（具体任务指令）、Crew（团队容器）、Tool（工具集）、Process（流程编排，sequential/parallel/hierarchical）。
- **开箱即用**：3 行代码可定义一个 Crew，门槛极低。
- **Pipeline**：支持多 Crew 顺序或并行执行复杂工作流。

**值得借鉴**：
- Role-Based Agent 定义（每个 Agent 有明确定义的角色、目标、背景故事）
- Process 驱动编排（CrewAI 的 Process 类似我们设计的 WorkflowEngine）
- 工具注册与复用机制

#### 1.2.4 smolagents（HuggingFace）

**核心定位**：极简、轻量、透明的多 Agent 框架。

**架构亮点**：
- **极简代码**：核心逻辑约 1000 行（agents.py），无过度抽象。
- **代码驱动**：Agent 可直接在循环中生成并执行 Python/Shell 代码（类似 CodeAct）。
- **多后端**：支持 HF Models、自定义 LLM、本地模型。
- **ToolCall 模式**：原生支持函数调用，非字符串拼接。

**值得借鉴**：
- "少即是多"的设计哲学——避免过度工程
- 代码执行代理（Code Agent）的实现方式
- 透明性——代码即文档，易于理解和修改

#### 1.2.5 DeerFlow（字节跳动）

**核心定位**：深度研究型多 Agent，擅长科研报告生成。

**架构亮点**：
- **多阶段研究流**：搜索 → 爬取 → 分析 → 报告，Agent 各司其职。
- **基于 LangStack**：复用 LangChain 生态，工具集成丰富。
- **多媒体输出**：支持图文报告、语音播客等多媒体格式。

**值得借鉴**：
- 多 Agent 分阶段协作模式（搜索 Agent → 研究 Agent → 报告 Agent）
- 与外部工具深度集成（搜索、爬虫、代码执行）

### 1.3 开源项目共性设计模式总结

综合以上项目，提炼出 5 条核心设计原则：

| # | 原则 | 来源 |
|---|------|------|
| 1 | **统一 Agent 抽象**：每个 Agent 有 role、goal、tools、memory，生命周期标准化（plan→execute→review） | CrewAI、OpenHands |
| 2 | **Tool 优先**：Agent 通过工具与外界交互，而非直接操作。工具是安全隔离的边界 | OpenHands、CrewAI、smolagents |
| 3 | **沙箱执行**：代码执行必须在隔离环境（Docker/容器）中进行，防止危险操作 | OpenHands |
| 4 | **可观测**：日志、追踪、中间产物可视化，便于调试和人工干预 | OpenHands、DeerFlow |
| 5 | **评测驱动**：内置评估基准（SWE-bench 或自定义），保证 Agent 输出质量可量化 | OpenHands |

### 1.4 本项目与开源项目的差异定位

| | OpenHands | CrewAI | smolagents | DeerFlow | **SakuraAgentTeam（ours）** |
|---|---|---|---|---|---|
| 目标 | 单软件工程师解决 GitHub Issue | 多 Agent 角色协作完成复杂任务 | 极简代码生成 Agent | 深度研究/报告 | **全栈开发（前后端+数据库+部署）多 Agent 协同** |
| 流程 | Issue → 代码 → 测试 → PR | 角色定义 → Task → Crew → Process | 代码驱动迭代 | 搜索 → 研究 → 报告 | **需求 → 设计 → 前端 → 后端 → 测试 → 审查 → 部署** |
| 工具 | 代码执行、搜索、文件 | 可插拔 Tools | Code/本地执行 | 搜索、爬虫、代码 | **全栈工具链（前端框架、后端框架、数据库、部署）** |
| 沙箱 | Docker | 无 | 无 | 无 | **Docker 沙箱 + 文件系统权限控制** |
| 评测 | SWE-bench | 无 | 无 | 无 | **端到端功能验收 + 代码质量检查** |
| 前端 | CLI/Web | Python API | Python API | Web | **React 工作台（实时流 + 产物可视化）** |

---

## 2. 设计目标与核心假设

### 2.1 核心目标

**短期（MVP）**：一条自然语言需求 → 多 Agent 协作产出可运行的小型全栈应用（前后端 + 数据库 + 部署），并能自我审查与回滚。

**中期**：Agent 可插拔、任务可编排、产物可复盘、评测可量化。

**长期**：沉淀成通用的多 Agent 全栈开发工作台，支持多种技术栈和部署目标。

### 2.2 非目标（本次不做）

- 不做模型训练（直接对接现成 LLM API）
- 不做多云分布式训练
- 不做商业化 UI 业务系统

### 2.3 核心假设

| # | 假设 | 风险 |
|---|------|------|
| A1 | 假设 LLM（GPT-4o / Claude-4）在足够 prompt 下能正确生成全栈代码 | 中：复杂需求可能超出模型能力边界 |
| A2 | 假设 Docker 沙箱能有效隔离 Agent 操作 | 低：成熟技术 |
| A3 | 假设前端 Agent 能正确使用 React/Vite 脚手架 | 中：依赖脚手架模板质量 |
| A4 | 假设静态 DAG 编排足够覆盖 MVP 场景 | 低：MVP 范围可控 |

---

## 3. 系统总体架构

### 3.1 分层架构图

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

### 3.2 数据主流程（端到端）

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

### 3.3 核心数据流（参考 OpenHands CodeAct 模式）

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

## 4. 核心模块详细设计

### 4.1 Agent 抽象（参考 OpenHands + CrewAI）

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

### 4.1.5 子 Agent 设计参考（Anthropic Skills + OpenDesign + html-anything）

每个子 Agent 的设计参考成熟的 Skill 模式，采用分层渐进式指令结构：

#### 4.1.5.1 Anthropic Skills 规范（Agent Skills 标准）

**官方规范**：[agentskills.io](https://agentskills.io) | [GitHub](https://github.com/anthropics/skills) | 80k+ Stars

**Skill 目录结构**：

```
skill-name/
├── SKILL.md           # 核心指令文件（必需）
├── scripts/           # 可执行脚本
│   ├── setup.sh
│   └── validate.sh
└── resources/        # 参考资源
    ├── examples/
    └── templates/
```

**SKILL.md 核心结构**：

```markdown
# Skill Name

## 概述
简短描述这个 Skill 的用途。

## 触发条件
什么情况下应该使用这个 Skill？

## 指令（Instructions）
step-by-step 操作流程（Standard Operating Procedure）

### 步骤 1: ...
### 步骤 2: ...

## 示例（Examples）
输入 → 期望输出

## 约束（Constraints）
- 不应该做什么
- 限制条件

## 资源引用
引用 scripts/ 或 resources/ 中的文件
```

#### 4.1.5.2 前端 Agent 设计参考（OpenDesign + Anthropic Frontend Design）

**OpenDesign**：[nexu-io/open-design](https://github.com/nexu-io/open-design) | 55k Stars

**核心特点**：
- 本地优先的开源 Claude Design 替代方案
- 259+ Skills、142+ 组件库
- 72 套设计系统（Material、Tailwind UI、shadcn/ui 等）
- 支持 React/Vue/HTML 输出

**前端 Skills 生态**（277k+ 安装量）：

| Skill | Stars | 用途 |
|-------|-------|------|
| Anthropic Frontend Design | 277k+ | 设计审美驱动的 UI 生成 |
| UI/UX Pro Max | 55.8k | 设计智能数据库，快速匹配风格 |
| Impeccable | — | 精细化设计工坊 |
| web-artifacts-builder | — | 多文件 React 项目生成（支持 Tailwind + shadcn/ui） |
| Vercel Agent Skills | — | Vercel 部署集成 |

**本项目前端 Agent 参考设计**：

```python
# 前端 Agent Skill 结构
frontend_agent/
├── SKILL.md
├── scripts/
│   ├── create-vite.sh          # 脚手架创建
│   ├── install-deps.sh        # 依赖安装
│   └── validate-build.sh       # 构建验证
└── resources/
    ├── design-systems/          # 设计系统参考
    │   ├── tailwind-ui/
    │   ├── shadcn/
    │   └── material/
    └── templates/
        ├── component.tsx
        └── page.tsx
```

**前端 Agent Prompt 示例**：

```markdown
## 前端开发指令

### 技术栈
- React 18 + TypeScript
- Vite 构建工具
- Tailwind CSS + shadcn/ui 组件库
- 响应式设计，移动优先

### 开发流程
1. 分析 PRD 和设计要求
2. 选择合适的设计系统
3. 创建组件结构
4. 实现功能逻辑
5. 添加样式和动画
6. 测试响应式布局

### 代码规范
- 组件使用 PascalCase
- 样式使用 Tailwind CSS 类
- 状态管理使用 React Hooks
- 类型定义使用 TypeScript Interface
```

#### 4.1.5.3 后端 Agent 设计参考

**后端 Skills 生态**：

| Skill | 用途 |
|-------|------|
| code-reviewer | 代码审查规范 |
| git-automation | Git 操作自动化 |
| brand-guidelines | 品牌规范集成 |

**后端 Agent Prompt 示例**：

```markdown
## 后端开发指令

### 技术栈
- FastAPI + Pydantic
- SQLite（开发）/ PostgreSQL（生产）
- Docker 容器化

### API 设计规范
- RESTful 风格
- 版本化路由：/api/v1/...
- 统一错误响应格式
- 分页：cursor-based

### 代码规范
- 使用 async/await
- 类型提示完整
- 日志记录结构化
```

#### 4.1.5.4 经验积累设计参考（Neat-Freak + OpenClaw + LanceDB）

**Neat-Freak**：[KKKKhazix/khazix-skills/neat-freak](https://github.com/KKKKhazix/khazix-skills/tree/main/neat-freak)

**核心定位**：会话结束后对项目文档和记忆进行"洁癖级"审查与同步。

**核心设计理念**：

| 概念 | 说明 |
|------|------|
| **三类知识、三种受众** | Agent 记忆（自己）、CLAUDE.md（当前项目 AI）、docs/（其他人） |
| **记忆只增不改** | 每条教训生成新文件，旧的不删 |
| **docs 就地编辑** | 系统改 10 次，还是那一份 `ARCHITECTURE.md` |
| **毕业机制** | 稳定知识从记忆"毕业"到 docs，防止记忆膨胀 |

**记忆"毕业"机制**（核心创新）：

一条记忆满足以下任一条，就"毕业"到 docs/：

| 条件 | 说明 |
|------|------|
| 同一主题教训出现第 3 次 | 已是稳定知识而非"最近踩的坑" |
| 讲的是"系统怎么工作" | 本就是 docs 的职责 |
| 是"X 上线/落地"事件记录 | 现役事实进 docs，过程进 git log |

**防膨胀机制**：

| 文件 | 上限 | 超过后果 |
|------|------|----------|
| `MEMORY.md` | ≤200 行 且 ≤25KB | 超出部分会话开始时静默不加载 |
| `CLAUDE.md` | ~300 行 / ~15KB | 越长 adherence 越差 |
| 单条 memory 文件 | ~100 行 | 拆分或毕业 |

**执行流程**（5 步）：

```
第零步：尺寸体检（防膨胀）
    ↓
第一步：盘点现状（ls + 读所有 docs）
    ↓
第二步：识别变更（变更影响矩阵）
    ↓
第三步：实际修改（减优于加、合并优于追加、删除优于保留）
    ↓
第四步：自检清单（逐项过一遍）
    ↓
第五步：变更摘要
```

**变更影响矩阵示例**：

| 变更类型 | 要改的文件 |
|----------|-----------|
| 新增 API/路由 | CLAUDE.md 路由清单 + integration-guide + architecture |
| 新增环境变量 | CLAUDE.md 环境变量表 + runbook + integration-guide |
| 新增数据库表 | CLAUDE.md + architecture Data Model |
| 跨项目改动 | 上下游两边的 docs 都要对齐 |

---

**OpenClaw**：自改进 AI Agent，"The agent that grows with you"

**核心设计**：
- 从使用中自动创建 Skills
- LanceDB 向量数据库长期记忆
- 用户反馈驱动的自我优化

---

**本项目经验库设计（综合 Neat-Freak + OpenClaw）**：

```python
# 经验积累数据结构
class Experience:
    id: str
    error_type: str           # 错误类型
    error_message: str        # 错误信息
    context: {
        "agent_role": str,    # 哪个 Agent
        "task_type": str,     # 任务类型
        "project_type": str,   # 项目类型
        "code_snippet": str   # 相关代码片段
    }
    attempted_fixes: List[str]  # 尝试过的修复
    final_solution: str         # 最终解决方案
    success: bool
    user_rating: int            # 1-5 星评分
    occurrence_count: int       # 出现次数（用于"毕业"判断）
    status: str                 # "active" / "graduated" / "archived"
    created_at: datetime
    graduated_at: datetime      # 毕业时间
    embedding: List[float]      # 向量表示

# 经验"毕业"机制
class ExperienceGraduator:
    """将稳定经验毕业到知识库"""

    def check_graduation(self, exp: Experience) -> bool:
        """检查是否应该毕业"""
        # 条件 1：同一错误出现 3 次以上
        if exp.occurrence_count >= 3:
            return True

        # 条件 2：是"系统怎么工作"而非"踩过的坑"
        if self._is_system_knowledge(exp):
            return True

        # 条件 3：用户评分 5 星且成功解决
        if exp.user_rating == 5 and exp.success:
            return True

        return False

    def graduate(self, exp: Experience) -> str:
        """将经验毕业到 docs/"""
        # 1. 生成文档内容
        doc_content = self._generate_doc(exp)

        # 2. 写入 docs/troubleshooting/{error_type}.md
        doc_path = f"docs/troubleshooting/{exp.error_type}.md"
        self._write_doc(doc_path, doc_content)

        # 3. 更新经验状态
        exp.status = "graduated"
        exp.graduated_at = datetime.now()

        # 4. 原记忆文件缩成一行指针
        return f"已毕业到 {doc_path}"

# 经验检索
async def find_similar_experience(
    error_message: str,
    context: dict,
    top_k: int = 5
) -> List[Experience]:
    # 1. 提取错误特征
    error_type = extract_error_type(error_message)
    keywords = extract_keywords(error_message)

    # 2. 向量检索
    query_embedding = embedder.encode(error_message)
    vector_results = await vector_db.search(
        query_embedding,
        filter={"error_type": error_type, "status": "active"},
        top_k=top_k
    )

    # 3. 关键词过滤
    filtered = filter_by_keywords(vector_results, keywords)

    return filtered

# 防膨胀检查
def check_memory_size(memory_dir: str) -> dict:
    """检查记忆库大小，防止膨胀"""
    memory_size = get_dir_size(memory_dir)
    docs_size = get_dir_size("docs/")

    return {
        "memory_size": memory_size,
        "docs_size": docs_size,
        "is_inverted": memory_size > docs_size,  # 体量倒挂
        "needs_graduation": memory_size > 10 * 1024 * 1024  # > 10MB
    }
```

**经验库目录结构**：

```
data/
├── experiences/              # 活跃经验（未毕业）
│   ├── import_error_001.json
│   └── module_not_found_002.json
├── graduated/                # 已毕业经验（指针）
│   └── import_error_001.link
└── index.chroma/             # ChromaDB 向量索引

docs/
├── troubleshooting/          # 毕业后的稳定知识
│   ├── import-errors.md
│   └── module-not-found.md
└── architecture/
    └── ...
```

#### 4.1.5.5 全栈开发 Skills 生态

| 类别 | Skill 名称 | 用途 |
|------|-----------|------|
| **文档** | pdf / docx / pptx / xlsx | 文档处理 |
| **代码** | frontend-design | 前端设计生成 |
| | web-artifacts-builder | 多文件 React 项目 |
| | code-reviewer | 代码审查 |
| | git-automation | Git 操作 |
| **测试** | webapp-testing (Playwright) | E2E 测试 |
| **部署** | claude-api | 部署与 API |
| **企业** | brand-guidelines | 品牌规范 |
| **工具** | mcp-builder | MCP Server 构建 |

---

### 4.2 工具系统（参考 OpenHands Tool 抽象）

**工具基类**：

```python
# 参考：OpenHands 统一 Tool 接口 + smolagents 的 ToolCall 模式

class Tool(ABC):
    name: str
    description: str
    parameters: dict  # JSON Schema

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """在沙箱中安全执行"""
        ...
```

**核心工具集（MVP）**：

| 工具 | 功能 | 安全措施 |
|------|------|----------|
| `FileReadTool` | 读取文件内容 | 限制路径在项目目录内 |
| `FileWriteTool` | 写入/修改文件 | 同上 |
| `ShellRunTool` | 在 Docker 沙箱中执行命令 | Docker 容器内运行，超时控制 |
| `CodeLintTool` | 运行 lint / typecheck | 只读执行 |
| `CodeTestTool` | 运行单元测试 | 只读执行 |
| `LLMTool` | 封装 LLM 对话 | API 调用，无副作用 |
| `GitTool` | Git commit / branch | 只在项目目录内操作 |

### 4.3 编排层（参考 CrewAI Process + LangGraph）

**核心组件**：

| 组件 | 职责 | 参考 |
|------|------|------|
| `SessionManager` | Session 生命周期、持久化、恢复 | — |
| `TaskRouter` | 根据需求选择下一个 Agent | CrewAI Process |
| `WorkflowEngine` | 按 DAG 调度 Agent，失败重试/回滚 | LangGraph |
| `EventBus` | 事件发布/订阅，驱动前端 SSE 流 | — |

**默认全栈开发 DAG**：

```
需求澄清 ──► PRD ──► 架构设计 ──► 接口契约
                                 ├──► 前端开发 ──┐
                                 │              │
                                 └──► 后端开发 ──┼──► 集成测试 ──► 审查 ──► 部署
                                                │
                                          （并行执行）
```

### 4.4 基础层（参考 smolagents + OpenHands）

| 模块 | 职责 | 关键实现 |
|------|------|----------|
| `LLMProvider` | 统一封装 OpenAI/Anthropic/本地模型 | 可插拔 Provider 抽象，支持模型热切换 |
| `ToolRegistry` | 所有工具注册、权限控制、生命周期 | 插件式工具加载 |
| `MemoryStore` | 短期（Session）+ 长期（跨 Session 项目模式） | SQLite/PostgreSQL + 向量存储（可选） |
| `ProjectStore` | 每个项目产物，以 Git 仓库为单位存储 | 自动 init、commit、branch |
| `CodeSandbox` | Docker 容器管理（创建、执行、销毁） | 参考 OpenHands Runtime |

### 4.5 长期记忆与经验库（参考 Hermes）

**核心定位**：积累错误模式与解决方案，让系统"越用越好"。

**设计理念**：
- 每次 Agent 执行失败后，记录：错误类型、错误上下文、尝试的修复方案、最终解决方案
- 下次遇到类似错误时，优先从经验库检索历史解决方案
- 支持人工标注"有效/无效"，提升检索质量

**数据模型**：

```python
class Experience:
    """一条经验记录"""
    id: str
    error_type: str           # 错误类型，如 "ImportError", "ModuleNotFoundError"
    error_message: str        # 完整错误信息
    context: dict             # 上下文：Agent角色、任务描述、代码片段
    attempted_fixes: List[str] # 尝试过的修复方案
    final_solution: str       # 最终成功的解决方案
    success: bool             # 是否成功解决
    user_rating: int          # 用户评分 1-5
    created_at: datetime
    tags: List[str]           # 标签，如 ["react", "vite", "dependency"]
```

**核心接口**：

```python
class ExperienceStore:
    """经验库存储"""

    def add(self, experience: Experience) -> str:
        """添加一条新经验"""
        ...

    def search_similar(self, error_message: str, top_k: int = 5) -> List[Experience]:
        """根据错误信息检索相似经验（向量相似度 + 关键词匹配）"""
        ...

    def mark_effective(self, experience_id: str, rating: int):
        """用户标注经验有效性"""
        ...
```

**存储方案**：
- SQLite/PostgreSQL 存储结构化数据
- 可选：向量数据库（如 ChromaDB / Qdrant）用于语义检索
- MVP 阶段：先用 SQLite + 简单关键词匹配

**使用流程**：

```
Agent 执行失败
    ↓
提取错误信息（error_type + error_message）
    ↓
ExperienceStore.search_similar(error_message)
    ↓
若有相似经验 → 将历史解决方案注入 LLM Prompt
若无相似经验 → LLM 尝试新方案
    ↓
成功后 → 自动记录新经验到 ExperienceStore
    ↓
用户评分反馈 → 更新经验评分
```

**Prompt 注入示例**：

```
你之前遇到过类似的错误，以下是历史解决方案：

【经验 #1】
错误：ModuleNotFoundError: No module named 'react'
解决方案：在 package.json 所在目录执行 npm install
有效性：⭐⭐⭐⭐⭐

请参考以上经验，尝试修复当前错误。
```

---

### 4.6 动态编排（智能工作流选择）

**核心定位**：根据项目状态自动选择最合适的工作流，而非固定 DAG。

**设计理念**：
- 项目状态分为：**从零开始**（greenfield）、**有现有代码**（brownfield）、**增量迭代**（incremental）
- 不同状态对应不同的 Agent 编排策略
- 通过分析项目目录结构、Git 历史、现有技术栈自动判断

**项目状态判断规则**：

| 状态 | 判断条件 | 默认工作流 |
|------|----------|-----------|
| **从零开始** | 项目目录为空或只有 README | 完整流程：需求 → 设计 → 前端 → 后端 → 测试 → 审查 → 部署 |
| **有现有代码** | 存在 package.json / requirements.txt / 已有代码文件 | 分析现有代码 → 评估影响范围 → 选择性执行相关 Agent |
| **增量迭代** | 有 Git 历史，且用户需求明确指向某个模块 | 定向修改：只调用相关 Agent（如只改前端或只改后端） |

**核心组件**：

```python
class ProjectAnalyzer:
    """项目状态分析器"""

    def analyze(self, project_path: str) -> ProjectState:
        """分析项目状态"""
        has_code = self._has_existing_code(project_path)
        has_git = self._has_git_history(project_path)
        tech_stack = self._detect_tech_stack(project_path)

        if not has_code:
            return ProjectState.GREENFIELD
        elif has_git:
            return ProjectState.INCREMENTAL
        else:
            return ProjectState.BROWNFIELD

    def _detect_tech_stack(self, project_path: str) -> List[str]:
        """检测技术栈：React/Vue/FastAPI/Django/etc."""
        ...


class WorkflowSelector:
    """工作流选择器"""

    def select(self, state: ProjectState, user_requirement: str) -> Workflow:
        """根据项目状态和用户需求选择工作流"""
        if state == ProjectState.GREENFIELD:
            return self._greenfield_workflow(user_requirement)
        elif state == ProjectState.BROWNFIELD:
            return self._brownfield_workflow(user_requirement)
        else:
            return self._incremental_workflow(user_requirement)

    def _greenfield_workflow(self, requirement: str) -> Workflow:
        """从零开始：完整流程"""
        return Workflow(steps=[
            "requirement_agent",
            "design_agent",
            "frontend_agent",
            "backend_agent",
            "test_agent",
            "review_agent",
            "deploy_agent"
        ])

    def _brownfield_workflow(self, requirement: str) -> Workflow:
        """有现有代码：先分析，再选择性执行"""
        return Workflow(steps=[
            "code_analysis_agent",  # 新增：分析现有代码结构
            "impact_assessment_agent",  # 新增：评估影响范围
            # 根据分析结果动态选择后续 Agent
        ])

    def _incremental_workflow(self, requirement: str) -> Workflow:
        """增量迭代：定向修改"""
        # 通过 LLM 分析需求，判断涉及哪些模块
        affected_modules = self._analyze_affected_modules(requirement)
        return Workflow(steps=affected_modules)
```

**动态工作流示例**：

```
场景 1：用户说"帮我做一个 Todo 应用"
    → ProjectAnalyzer 检测到目录为空
    → WorkflowSelector 选择 GREENFIELD 工作流
    → 执行完整流程

场景 2：用户说"帮我给现有的 Todo 应用加一个登录功能"
    → ProjectAnalyzer 检测到已有代码
    → WorkflowSelector 选择 INCREMENTAL 工作流
    → 只执行：需求分析 → 设计（评估影响）→ 后端（加登录 API）→ 前端（加登录页）→ 测试 → 审查

场景 3：用户说"帮我修复这个 bug：前端点击删除按钮没反应"
    → ProjectAnalyzer 检测到已有代码
    → WorkflowSelector 选择 INCREMENTAL 工作流
    → 只执行：代码分析 → 前端修复 → 测试
```

---

### 4.7 前端（自研，差异化点）

参考开源项目均有简陋或缺失的前端，本项目将**工作台体验**作为差异化能力：

| 页面 | 功能 |
|------|------|
| 新建任务页 | 输入需求 → 展示 DAG 流程 → 开始执行 |
| 会话页 | 多 Agent 对话流 + 实时日志（SSE）+ 产物树 |
| 产物页 | 文件浏览 + 代码高亮 + 运行/测试/部署按钮 |
| 进度看板 | DAG 可视化 + 各 Agent 状态（pending/running/done/error） |
| 经验库页 | 查看历史错误与解决方案，支持搜索与评分 |

---

## 5. 技术选型

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

## 6. MVP 范围与验收标准

### 6.1 MVP 功能范围

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

### 6.2 验收标准

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

---

## 10. LLM 接入设计（用户自带 Key）

### 10.1 设计原则

- **官方不提供 API Key**：用户必须配置自己的 Key
- **支持多模型提供者**：参考 OpenHands 支持 100+ 模型，统一抽象
- **配置灵活**：支持环境变量、配置文件、前端输入三种方式

### 10.2 支持的模型提供者（MVP）

| 提供者 | 模型示例 | 配置方式 |
|--------|----------|----------|
| OpenAI | gpt-4o, gpt-4-turbo, gpt-3.5-turbo | `OPENAI_API_KEY` |
| Anthropic | claude-4-opus, claude-4-sonnet | `ANTHROPIC_API_KEY` |
| Azure OpenAI | 用户自定义部署 | `AZURE_OPENAI_API_KEY` + `AZURE_ENDPOINT` |
| 本地模型 | Ollama, vLLM, LM Studio | `LOCAL_MODEL_BASE_URL` |
| 其他 | DeepSeek, Moonshot, 智谱, 零一万物... | 统一接口 |

### 10.3 配置方式

**方式一：环境变量（推荐）**

```bash
# .env 文件
OPENAI_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-xxx
# 可选：指定默认模型
DEFAULT_LLM_PROVIDER=openai
DEFAULT_LLM_MODEL=gpt-4o
```

**方式二：前端配置**

用户在设置页面输入 API Key，存储在本地浏览器（localStorage），不上传服务器。

**方式三：配置文件**

```yaml
# config.yaml
llm:
  default_provider: openai
  default_model: gpt-4o
  providers:
    openai:
      api_key: ${OPENAI_API_KEY}
      models:
        - gpt-4o
        - gpt-4-turbo
    anthropic:
      api_key: ${ANTHROPIC_API_KEY}
      models:
        - claude-4-opus
        - claude-4-sonnet
```

### 10.4 LLM Provider 抽象

```python
class LLMProvider(ABC):
    """统一 LLM 提供者抽象"""

    @abstractmethod
    def chat(self, messages: List[dict], **kwargs) -> str:
        """同步对话"""
        ...

    @abstractmethod
    async def achat(self, messages: List[dict], **kwargs) -> str:
        """异步对话"""
        ...

    @abstractmethod
    def stream(self, messages: List[dict], **kwargs) -> Iterator[str]:
        """流式输出"""
        ...


class LLMProviderFactory:
    """LLM 提供者工厂"""

    _providers = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "azure": AzureOpenAIProvider,
        "ollama": OllamaProvider,
        # 可扩展...
    }

    @classmethod
    def create(cls, provider: str, config: dict) -> LLMProvider:
        provider_class = cls._providers.get(provider)
        if not provider_class:
            raise ValueError(f"Unsupported provider: {provider}")
        return provider_class(**config)
```

---

## 11. 经验库存储方案：向量数据库（ChromaDB）

### 11.1 为什么选择向量数据库

| 优势 | 说明 |
|------|------|
| **语义理解** | 能找到"意思相近"的错误，而非仅关键词匹配 |
| **检索质量高** | 即使错误信息表述不同，也能检索到相似经验 |
| **开箱即用** | ChromaDB 轻量级，无需额外部署服务 |
| **可扩展** | 支持后续升级到 Qdrant / Milvus 等生产级方案 |

### 11.2 技术选型

| 组件 | 选型 | 理由 |
|------|------|------|
| 向量数据库 | **ChromaDB** | 轻量级、Python 原生、无需额外部署、支持持久化 |
| Embedding 模型 | **sentence-transformers** 或 **OpenAI Embeddings** | 开源免费或 API 调用，按需选择 |
| 持久化存储 | ChromaDB 内置 SQLite | 无需额外数据库 |

### 11.3 实现方案

```python
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

class ExperienceStore:
    """经验库存储（ChromaDB 向量检索）"""

    def __init__(self, persist_dir: str = "data/experience_db"):
        # 初始化 ChromaDB（持久化到本地）
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(
            name="experiences",
            metadata={"hnsw:space": "cosine"}  # 余弦相似度
        )

        # 初始化 Embedding 模型（本地运行，免费）
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')

    def add(self, experience: Experience) -> str:
        """添加一条新经验"""
        # 生成向量
        text_to_embed = f"{experience.error_type}: {experience.error_message}"
        embedding = self.embedder.encode(text_to_embed).tolist()

        # 存入 ChromaDB
        self.collection.add(
            ids=[experience.id],
            embeddings=[embedding],
            metadatas=[{
                "error_type": experience.error_type,
                "error_message": experience.error_message,
                "final_solution": experience.final_solution,
                "success": experience.success,
                "user_rating": experience.user_rating,
                "tags": ",".join(experience.tags),
                "created_at": experience.created_at.isoformat()
            }],
            documents=[text_to_embed]
        )
        return experience.id

    def search_similar(self, error_message: str, top_k: int = 5) -> List[Experience]:
        """语义相似度检索"""
        # 生成查询向量
        query_embedding = self.embedder.encode(error_message).tolist()

        # 向量检索
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where={"success": True}  # 只返回成功解决的经验
        )

        # 转换为 Experience 对象
        experiences = []
        for i, doc in enumerate(results['documents']):
            exp = Experience(
                id=results['ids'][0][i],
                error_type=results['metadatas'][0][i]['error_type'],
                error_message=results['metadatas'][0][i]['error_message'],
                final_solution=results['metadatas'][0][i]['final_solution'],
                user_rating=results['metadatas'][0][i]['user_rating'],
                tags=results['metadatas'][0][i]['tags'].split(','),
            )
            experiences.append(exp)

        return experiences

    def mark_effective(self, experience_id: str, rating: int):
        """更新经验评分"""
        self.collection.update(
            ids=[experience_id],
            metadatas=[{"user_rating": rating}]
        )
```

### 11.4 使用流程

```
Agent 执行失败
    ↓
提取错误信息（error_type + error_message）
    ↓
ExperienceStore.search_similar(error_message)
    ↓
ChromaDB 向量检索 → 返回语义最相似的 Top 5 经验
    ↓
若有相似经验 → 将历史解决方案注入 LLM Prompt
若无相似经验 → LLM 尝试新方案
    ↓
成功后 → 自动记录新经验（生成向量并存入 ChromaDB）
    ↓
用户评分反馈 → 更新经验评分
```

### 11.5 Prompt 注入示例

```python
def build_prompt_with_experience(error_message: str, store: ExperienceStore) -> str:
    """构建带历史经验的 Prompt"""
    experiences = store.search_similar(error_message, top_k=3)

    if not experiences:
        return f"请尝试修复以下错误：\n{error_message}"

    exp_text = "\n\n".join([
        f"【经验 #{i+1}】\n"
        f"错误：{exp.error_message}\n"
        f"解决方案：{exp.final_solution}\n"
        f"有效性：{'⭐' * exp.user_rating}"
        for i, exp in enumerate(experiences)
    ])

    return f"""你之前遇到过类似的错误，以下是历史解决方案：

{exp_text}

请参考以上经验，尝试修复当前错误：
{error_message}"""
```

### 11.6 依赖安装

```bash
# requirements.txt
chromadb>=0.4.0
sentence-transformers>=2.2.0
```

### 11.7 后续优化方向

| 阶段 | 优化内容 |
|------|----------|
| MVP | ChromaDB + sentence-transformers（本地免费） |
| 进阶 | 切换到 OpenAI Embeddings（更高精度） |
| 生产 | 迁移到 Qdrant / Milvus（高并发、分布式） |

---

## 12. 开发顺序确认

### 阶段划分

| 阶段 | 内容 | 优先级 |
|------|------|--------|
| **Phase 1：基础核心** | Milestone 0 + Milestone 1（单 Agent 跑通） | 最高 |
| **Phase 2：多 Agent 编排** | Milestone 2（核心工作流） | 高 |
| **Phase 3：增强能力** | 经验库 + 动态编排 | 中 |
| **Phase 4：工程化** | Milestone 3（可用性 + 测试 + 文档） | 中 |

### Phase 1 详细任务（立即开始）

```
Milestone 0（约 1 周）
├── M0-I1: 初始化目录结构
├── M0-I2: FastAPI 脚手架
├── M0-I3: React + Vite 脚手架
├── M0-I4: LLM Provider 抽象 + OpenAI/Anthropic 实现
├── M0-I5: Tool 基类 + 基础工具
├── M0-I6: Docker 沙箱
├── M0-I7: Git 产物仓库
└── M0-I8: 基础 CI

Milestone 1（约 1 周）
├── M1-I1: Agent 基类
├── M1-I2: 需求 Agent（PRD 生成）
├── M1-I3: SessionManager
├── M1-I4: EventBus
├── M1-I5: 前端会话页基础
└── M1-I6: 端到端单 Agent 调试
```

---

> **下一步**：确认后立即开始 **Milestone 0 - I1：初始化目录结构**
