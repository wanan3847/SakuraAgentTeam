# 参考资料与开源项目调研

> 收集对 SakuraAgentTeam 有启发的开源项目、设计原则、CodeAct/Coordinator 等关键模式。
>
> 本文档是 [architecture.md](./architecture.md) 的"背景资料"附录，不影响执行路径。

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

