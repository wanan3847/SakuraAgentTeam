# 子 Agent 协作改造实施方案

## 目标

把当前“多个 agent 轮流聊天”的协作体验，改造成“围绕任务图推进、共享上下文、产出可检查成果”的协作系统。

用户感知目标：

- agent 之间有明确关联，不再各说各话。
- 每个 agent 都消费上游产物，并产出自己的结构化结果。
- 最终必须交付一个可读、可导出、可复用的成果，而不是几段散乱回复。
- 过程可视化：用户能看到任务拆解、执行状态、白板产物、最终报告。

工程目标：

- 保留现有 `group / pipeline / master / consensus / parallel / handoff / graph` 模式入口。
- 优先强化 `graph` 和 `master`，再让其他模式复用统一的任务图执行内核。
- 后端用结构化 `TaskNode`、`Artifact`、`SharedContext` 串联 agent。
- 前端 Workspace 展示任务图、白板产物、最终交付物。

## 现状判断

当前项目已有一些雏形：

- `backend/app/orchestration/agent_team.py`
  - 有 `CollaborationEngine`
  - 有 group、hierarchical、consensus、parallel 逻辑
  - 有 whiteboard / graph / handoff / trace 相关概念
- `backend/app/api/teams.py`
  - 已暴露 `/teams/{id}/chat`
  - 已暴露 `/teams/{id}/graph`
  - 已暴露 `/teams/{id}/handoff`
  - 已暴露 `/whiteboard/{session_id}`
- `frontend/src/pages/WorkspacePage.tsx`
  - 已能处理 `graph_snapshot`
  - 已能处理 `whiteboard_snapshot`
  - 已能处理 `agent_trace`
  - 已能显示 graph / whiteboard / trace 面板

但核心问题是：

- 主执行路径仍然偏“消息流”，不是“任务流”。
- agent 输出没有统一 schema，后续 agent 很难稳定继承。
- whiteboard 更像附属展示，不是强制协作上下文。
- graph 任务状态还没有成为所有模式的统一底座。
- 最终没有强制 `final_deliverable`，所以用户容易觉得“没有成果”。

## 参考模式

### CrewAI

借鉴点：

- Agent 有 `role / goal / backstory`。
- Task 有 `description / expected_output / agent / context`。
- Process 控制 sequential / hierarchical。

落地方式：

- 每个任务节点都必须有 `expected_output`。
- agent 调用时必须看到自己的 role、目标、上游 context、输出格式。
- sequential / master 模式不要直接聊天，改成 Task 顺序执行。

### AutoGen / AG2

借鉴点：

- GroupChatManager 选择下一个发言者。
- 对话历史可以用于动态协商。

落地方式：

- group 模式可以保留多轮讨论，但讨论结束后必须生成结构化决议。
- 不能让 group 模式只产出聊天记录，必须落到 `DecisionArtifact` 或 `FinalReportArtifact`。

### Anthropic Orchestrator-Workers

借鉴点：

- orchestrator 先拆任务。
- worker 独立完成子任务。
- orchestrator 汇总结果。

落地方式：

- `master` 模式默认使用这个模式。
- manager 第一步输出 `TaskPlan`。
- workers 根据任务并行或按依赖执行。
- manager 最后输出最终交付物。

### MetaGPT

借鉴点：

- 软件公司 SOP。
- 上游产物传给下游角色。
- 产物比聊天更重要。

落地方式：

- 需求、设计、实现、测试、评审、部署分别对应 artifact。
- 下游 prompt 直接引用上游 artifact，而不是只引用自然语言聊天历史。

### LangGraph

借鉴点：

- 状态图。
- 节点状态可恢复、可检查。
- 每个节点读取状态并写回状态。

落地方式：

- 统一内核使用任务 DAG。
- 节点状态包括 `pending / ready / running / done / failed / skipped`。
- 每个节点完成后写入 artifact，并广播 `graph_snapshot`。

## 核心设计

### 1. 统一协作数据模型

新增或重构到 `backend/app/orchestration/collaboration_state.py`。

建议模型：

```python
from dataclasses import dataclass, field
from typing import Any, Literal

TaskState = Literal["pending", "ready", "running", "done", "failed", "skipped"]
ArtifactType = Literal[
    "task_plan",
    "requirements",
    "design_spec",
    "implementation_plan",
    "code_patch",
    "test_report",
    "review_report",
    "deployment_note",
    "decision",
    "final_report",
]

@dataclass
class Artifact:
    id: str
    task_id: str
    agent_id: str
    agent_name: str
    type: ArtifactType
    title: str
    content: str
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0

@dataclass
class TaskNode:
    id: str
    name: str
    description: str
    expected_output: str
    agent_id: str
    dependencies: list[str] = field(default_factory=list)
    state: TaskState = "pending"
    artifact_ids: list[str] = field(default_factory=list)
    error: str = ""

@dataclass
class CollaborationState:
    session_id: str
    user_request: str
    mode: str
    team_id: str
    tasks: list[TaskNode] = field(default_factory=list)
    artifacts: list[Artifact] = field(default_factory=list)
    final_artifact_id: str | None = None
```

验收：

- 后端所有协作模式都能创建 `CollaborationState`。
- 每个 agent 执行后至少写入一个 `Artifact`。
- 最终必须有 `final_artifact_id`。

### 2. 强制输出协议

新增 `backend/app/orchestration/output_contracts.py`。

定义每类 agent 的输出要求。

示例：

```python
OUTPUT_CONTRACTS = {
    "requirements": {
        "artifact_type": "requirements",
        "required_sections": ["目标", "用户故事", "范围", "约束", "验收标准"],
    },
    "design": {
        "artifact_type": "design_spec",
        "required_sections": ["信息架构", "关键界面", "交互流程", "视觉约束"],
    },
    "frontend": {
        "artifact_type": "implementation_plan",
        "required_sections": ["文件变更", "组件设计", "状态管理", "风险"],
    },
    "testing": {
        "artifact_type": "test_report",
        "required_sections": ["测试范围", "测试用例", "结果", "遗留风险"],
    },
    "review": {
        "artifact_type": "review_report",
        "required_sections": ["发现问题", "严重级别", "建议修复", "是否通过"],
    },
}
```

agent prompt 必须包含：

- 当前任务。
- 期望输出。
- 上游 artifact 摘要和全文。
- 必须按指定章节输出。
- 不允许只发表泛泛建议。

验收：

- 每个 agent 回复能被包装为指定 artifact。
- 缺少必要章节时，后端自动发起一次修正 prompt。

### 3. Manager 任务拆解

新增 `TaskPlanner`。

位置建议：

- `backend/app/orchestration/planner.py`

职责：

- 输入用户需求、团队成员、模式。
- 输出 `TaskNode[]`。
- 对于简单需求也至少生成 2 个任务：
  - 分析任务
  - 最终交付任务

Planner 输出 JSON schema：

```json
{
  "tasks": [
    {
      "id": "requirements",
      "name": "需求分析",
      "description": "澄清用户目标、范围和验收标准",
      "expected_output": "结构化需求说明",
      "agent_id": "product_manager",
      "dependencies": []
    }
  ]
}
```

兜底逻辑：

- 如果 LLM 返回非法 JSON，使用规则生成默认 DAG。
- 默认 DAG：
  - `analysis`
  - `solution`
  - `review`
  - `final`

验收：

- `/teams/{id}/graph` 不依赖前端传 tasks 时也能自动拆任务。
- 前端可立刻看到任务图。

### 4. 统一 DAG 执行器

新增 `GraphCollaborationEngine`。

位置建议：

- `backend/app/orchestration/graph_engine.py`

职责：

1. 初始化 `CollaborationState`。
2. 广播 `graph_snapshot`。
3. 找出 `ready` 节点。
4. 调用对应 agent。
5. 将输出写为 artifact。
6. 广播 `artifact_created` 和 `whiteboard_snapshot`。
7. 更新任务状态。
8. 所有任务完成后调用 finalizer。

伪代码：

```python
async def run_graph(state, team, llm):
    mark_ready_tasks(state)
    yield graph_snapshot(state)

    while has_unfinished_tasks(state):
        ready = get_ready_tasks(state)
        if can_parallel:
            run ready tasks concurrently
        else:
            run first ready task

        for result in results:
            create_artifact(result)
            mark_done(result.task)
            yield artifact_created(...)
            yield graph_snapshot(...)

    final = await synthesize_final_artifact(state)
    state.final_artifact_id = final.id
    yield final_deliverable(final)
    yield chat_done(...)
```

验收：

- 任意任务失败时，状态变为 `failed`，前端显示失败原因。
- 下游任务必须等依赖任务 `done`。
- finalizer 必须消费所有 artifact。

### 5. Artifact Store / Whiteboard 改造

当前 whiteboard 可以保留，但要升级为唯一事实来源。

建议接口：

- `GET /api/v1/collaboration/{session_id}/state`
- `GET /api/v1/collaboration/{session_id}/artifacts`
- `GET /api/v1/collaboration/{session_id}/artifacts/{artifact_id}`

短期可以先用内存存储：

```python
COLLAB_SESSIONS: dict[str, CollaborationState] = {}
```

中期再落库：

- `collaboration_sessions`
- `collaboration_tasks`
- `collaboration_artifacts`

验收：

- 刷新页面后至少能通过 session_id 拉到当前 whiteboard。
- 导出时可以导出 artifact，而不是只导出聊天消息。

### 6. Finalizer 最终交付

新增 `Finalizer`。

位置建议：

- `backend/app/orchestration/finalizer.py`

职责：

- 输入所有 artifact。
- 输出一个 `final_report` artifact。
- 格式必须适合用户直接使用。

最终报告结构：

```markdown
# 最终成果

## 结论

## 关键产物

## 执行过程摘要

## 具体方案 / 内容 / 代码建议

## 风险与后续动作
```

验收：

- 每次协作结束都出现“最终成果”。
- 用户不需要翻所有 agent 回复，也能拿到完整结论。

### 7. 前端 Workspace 改造

重点文件：

- `frontend/src/pages/WorkspacePage.tsx`
- `frontend/src/lib/teamApi.ts`

新增事件处理：

- `task_plan_created`
- `task_started`
- `task_completed`
- `artifact_created`
- `final_deliverable`

消息区行为：

- agent 聊天可以继续显示，但弱化为“过程日志”。
- 任务图和最终成果应该更突出。

建议 UI：

- 左侧或上方：任务进度。
- 右侧：白板产物列表。
- 主区：最终成果卡片 + 当前 agent 输出。

不要做成营销页。
这是工作台，应保持密集、清晰、可扫描。

验收：

- 用户发起任务后 1 秒内看到任务图。
- 每个任务完成后白板出现一个 artifact。
- 协作完成后主区出现“最终成果”。
- 导出按钮默认导出最终成果和全部 artifact。

## 分阶段实施步骤

### 阶段 1：补强 graph 模式

目标：先让 `graph` 模式真正产出成果。

步骤：

1. 新增 `collaboration_state.py`。
2. 新增 `planner.py`，支持自动任务拆解。
3. 新增 `graph_engine.py`。
4. 修改 `backend/app/api/teams.py` 的 `_stream_graph`，改用 `GraphCollaborationEngine`。
5. 前端处理 `artifact_created` 和 `final_deliverable`。

验收：

- 在状态图模式下输入“帮我策划一个大学生创业项目推广方案”。
- 系统自动生成至少 3 个任务。
- 每个任务有状态变化。
- 白板出现多个产物。
- 最后出现完整最终方案。

### 阶段 2：master 模式复用 graph 内核

目标：让“管家模式”真正像 orchestrator-workers。

步骤：

1. manager 先调用 `TaskPlanner`。
2. workers 执行 DAG。
3. manager 或 finalizer 汇总。
4. 保留 manager 的自然语言说明，但实际执行基于任务节点。

验收：

- 管家模式不再只是“主管说一段 + worker 各说一段”。
- 每个 worker 的输出对应一个 artifact。
- manager 的最终回复引用 worker 产物。

### 阶段 3：pipeline / parallel / group 统一语义

目标：所有模式都能产出最终成果。

改造规则：

- `pipeline`：线性 DAG，每个节点依赖前一个节点。
- `parallel`：多个 worker 节点并行，最后 final 节点汇总。
- `group`：先讨论，再生成 decision artifact，再 final。
- `consensus`：多轮讨论后必须生成 consensus artifact。
- `handoff`：handoff 链路必须写入 task trace 和 artifact。

验收：

- 所有模式结束后都有 `final_deliverable`。
- 所有模式都有 artifact。

### 阶段 4：持久化和历史记录

目标：协作成果可回看。

步骤：

1. 新增数据库表。
2. 保存 session、tasks、artifacts。
3. History 页面支持查看最终成果和白板。
4. 导出支持 artifact。

验收：

- 刷新页面后不会丢失成果。
- 历史记录能展示最终报告。

### 阶段 5：质量控制

目标：减少“水话”和无效输出。

步骤：

1. 给每个输出 contract 添加必填章节检查。
2. 输出太短时自动要求 agent 补充。
3. finalizer 检查是否引用所有关键 artifact。
4. review agent 给最终成果打分。

验收：

- agent 输出少于 200 字或缺章节时会自动修正。
- 最终报告包含“依据哪些产物得出结论”。

## 后端事件协议

SSE 事件建议统一如下：

```json
{
  "type": "task_plan_created",
  "data": {
    "session_id": "xxx",
    "tasks": []
  }
}
```

```json
{
  "type": "task_started",
  "data": {
    "task_id": "requirements",
    "agent_id": "product_manager"
  }
}
```

```json
{
  "type": "artifact_created",
  "data": {
    "artifact": {
      "id": "art_xxx",
      "task_id": "requirements",
      "type": "requirements",
      "title": "需求分析",
      "summary": "..."
    }
  }
}
```

```json
{
  "type": "final_deliverable",
  "data": {
    "artifact": {
      "id": "art_final",
      "type": "final_report",
      "title": "最终成果",
      "content": "..."
    }
  }
}
```

保留现有事件：

- `agent_thinking`
- `agent_chunk`
- `agent_done`
- `graph_snapshot`
- `whiteboard_snapshot`
- `agent_trace`
- `chat_done`
- `error`

## Prompt 模板建议

### Worker Prompt

```text
你是团队中的 {agent_name}。

你的角色：
{role}

你的目标：
{goal}

用户需求：
{user_request}

当前任务：
{task_name}

任务说明：
{task_description}

期望输出：
{expected_output}

上游产物：
{dependency_artifacts}

请只完成当前任务，不要重复其他 agent 的职责。
必须输出以下章节：
{required_sections}

输出要具体、可执行、能被下游 agent 直接使用。
```

### Finalizer Prompt

```text
你是最终整合者。

用户原始需求：
{user_request}

以下是所有 agent 产物：
{artifacts}

请生成用户可以直接使用的最终成果。
要求：
1. 不要简单复述过程。
2. 合并重复内容。
3. 明确结论和下一步。
4. 保留关键细节。
5. 如果有风险，单独列出。
```

## 测试用例

### 用例 1：内容策划

输入：

```text
帮我策划一个大学生创业项目的推广方案
```

期望：

- 任务图至少包含市场分析、方案设计、执行计划、风险评审、最终方案。
- 最终成果包含渠道、节奏、预算、人群、KPI。

### 用例 2：技术实现

输入：

```text
给现有系统增加用户反馈入口，并能提交到 GitHub Issue
```

期望：

- 需求 agent 输出验收标准。
- 设计 agent 输出交互方案。
- 前端 agent 输出文件改动方案。
- 测试 agent 输出测试点。
- finalizer 输出完整实现计划。

### 用例 3：研究报告

输入：

```text
分析 AI Agent 在企业内部知识库中的应用价值
```

期望：

- 研究、战略、风险、最终报告分工清晰。
- 最终报告有结构，不是多段聊天拼接。

## 不要做的事

- 不要只增加更多 agent 回复。
- 不要让每个 agent 都回答完整问题。
- 不要把 whiteboard 当可选装饰。
- 不要让前端只展示聊天流。
- 不要依赖前端传 tasks 才能运行 graph。
- 不要把最终成果藏在最后一个普通 agent 消息里。

## 最小可交付版本

如果时间有限，先完成这 6 件事：

1. `TaskPlanner` 自动拆任务。
2. `CollaborationState` 存任务和产物。
3. `GraphCollaborationEngine` 按依赖执行任务。
4. 每个任务输出一个 artifact。
5. `Finalizer` 输出最终报告。
6. Workspace 显示最终报告和 artifact 列表。

完成这 6 件事后，用户对“协作有关联、能产出成果”的感知会明显改善。
