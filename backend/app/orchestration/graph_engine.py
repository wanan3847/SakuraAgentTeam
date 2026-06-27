"""
GraphCollaborationEngine — 统一 DAG 执行器。

借鉴 LangGraph.StateGraph + Anthropic Orchestrator-Workers + MetaGPT SOP。

职责:
1. 用 TaskPlanner 拆任务
2. 初始化 CollaborationState
3. 广播 task_plan_created / graph_snapshot
4. 拓扑循环:找 ready 节点 → 调 agent → 写 artifact → 广播事件
5. 所有任务完成后,Finalizer 生成 final_deliverable
6. 支持并行执行无依赖的任务

产出的新 SSE 事件:
- task_plan_created
- task_started
- task_completed
- artifact_created
- final_deliverable
(同时保留兼容现有 graph_snapshot / agent_thinking / agent_chunk / agent_done / agent_trace)
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any, AsyncIterator

from app.agents.registry.base import AgentDef, Crew, build_agent_system_prompt
from app.foundation.llm.base import Message, MessageRole
from app.foundation.llm.meter import MeteredLLMProvider

from .collaboration_state import (
    Artifact,
    CollaborationState,
    CollabTaskNode,
    create_session,
    new_artifact_id,
)
from .finalizer import synthesize_final_artifact
from .output_contracts import (
    build_fix_prompt,
    build_worker_prompt,
    get_contract,
    validate_output,
)
from .planner import plan_tasks, plan_tasks_async, tasks_to_nodes

logger = logging.getLogger(__name__)


@dataclass
class GraphEvent:
    """SSE 事件载体 — 与 agent_team.py 的 ChatEvent 兼容。"""
    type: str
    data: dict[str, Any]


class GraphCollaborationEngine:
    """统一 DAG 执行器 — 所有协作模式的核心内核。

    当前先服务 graph 模式,后续 master / pipeline / parallel / group / consensus
    都可以复用这个内核(只需要不同的 plan_tasks 策略)。
    """

    def __init__(self, llm: MeteredLLMProvider | None = None):
        self.llm = llm

    async def run(
        self,
        crew: Crew,
        user_request: str,
        tasks: list[dict[str, Any]] | None = None,
        manager_id: str | None = None,
        session_id: str | None = None,
    ) -> AsyncIterator[GraphEvent]:
        """执行 DAG 协作。

        Args:
            crew: 团队定义
            user_request: 用户需求
            tasks: 前端传入的任务定义(可选,不传则 LLM 自动拆)
            manager_id: 主管 agent id(可选)
            session_id: 会话 id(可选)

        Yields:
            GraphEvent 流
        """
        # ===== 1. 拆任务 =====
        if not tasks:
            tasks = await plan_tasks_async(user_request, crew, self.llm, manager_id)
        else:
            # 前端传了 tasks,补全 expected_output(如果没填)
            for t in tasks:
                if not t.get("expected_output"):
                    agent_id = t.get("agent_id", "")
                    agent = next((a for a in crew.agents if a.id == agent_id), None)
                    if agent:
                        contract = get_contract(agent)
                        t["expected_output"] = f"按照 {contract['artifact_type']} 格式输出"

        task_nodes = tasks_to_nodes(tasks, list(crew.agents))

        # ===== 2. 初始化 CollaborationState =====
        state = create_session(
            user_request=user_request,
            mode="graph",
            team_id=crew.id,
            team_name=crew.name,
            session_id=session_id,
        )
        for node in task_nodes:
            state.add_task(node)

        # ===== 3. 广播任务计划 =====
        yield GraphEvent(
            type="task_plan_created",
            data={
                "session_id": state.session_id,
                "tasks": [t.to_dict() for t in state.tasks],
            },
        )
        yield GraphEvent(
            type="graph_snapshot",
            data=state.to_snapshot(),
        )

        # ===== 4. 拓扑循环执行 =====
        max_rounds = len(state.tasks) * 2 + 4  # 防止死循环
        round_num = 0

        while state.has_unfinished_tasks() and round_num < max_rounds:
            round_num += 1
            ready = state.get_ready_tasks()
            if not ready:
                # 没有 ready 任务但还有未完成的 — 可能是全部 failed
                logger.warning(f"round {round_num}: 无 ready 任务但仍有未完成任务,退出")
                break

            # 并行执行所有 ready 任务(无依赖的可以并行)
            if len(ready) == 1:
                async for evt in self._execute_task(state, crew, ready[0]):
                    yield evt
            else:
                # 多个 ready 任务并行,但事件要顺序 yield
                # 用 asyncio.gather 收集每个任务的事件列表,再按任务顺序 yield
                async def _collect(task: CollabTaskNode) -> list[GraphEvent]:
                    evts: list[GraphEvent] = []
                    async for e in self._execute_task(state, crew, task):
                        evts.append(e)
                    return evts

                results = await asyncio.gather(*[_collect(t) for t in ready], return_exceptions=True)
                for result in results:
                    if isinstance(result, Exception):
                        logger.error(f"并行任务执行异常: {result}")
                        yield GraphEvent(
                            type="error",
                            data={"message": f"任务执行异常: {result}"},
                        )
                        continue
                    for evt in result:
                        yield evt

            # 每轮结束广播 graph_snapshot
            yield GraphEvent(
                type="graph_snapshot",
                data=state.to_snapshot(),
            )

        # ===== 5. Finalizer 生成最终交付 =====
        try:
            final_artifact = await synthesize_final_artifact(state, self.llm)
            yield GraphEvent(
                type="artifact_created",
                data={
                    "artifact": final_artifact.to_dict(),
                    "is_final": True,
                },
            )
            yield GraphEvent(
                type="final_deliverable",
                data={
                    "artifact": final_artifact.to_dict(),
                    "session_id": state.session_id,
                },
            )
        except Exception as e:
            logger.error(f"finalizer 失败: {e}", exc_info=True)
            yield GraphEvent(
                type="error",
                data={"message": f"最终交付生成失败: {e}"},
            )

        # ===== 6. 结束 =====
        yield GraphEvent(
            type="chat_done",
            data={
                "crew_id": crew.id,
                "mode": "graph",
                "session_id": state.session_id,
                "final_artifact_id": state.final_artifact_id,
            },
        )

    async def _execute_task(
        self,
        state: CollaborationState,
        crew: Crew,
        task: CollabTaskNode,
    ) -> AsyncIterator[GraphEvent]:
        """执行单个任务节点。"""
        agent = next((a for a in crew.agents if a.id == task.agent_id), None)
        if not agent:
            state.mark_failed(task.id, f"未找到 agent: {task.agent_id}")
            yield GraphEvent(
                type="error",
                data={"message": f"任务 {task.name} 找不到 agent {task.agent_id}"},
            )
            return

        # 标记 running
        state.mark_running(task.id)

        # 广播 task_started
        yield GraphEvent(
            type="task_started",
            data={
                "task_id": task.id,
                "task_name": task.name,
                "agent_id": agent.id,
                "agent_name": agent.name,
                "agent_avatar": agent.avatar,
                "agent_color": agent.color,
                "dependencies": task.dependencies,
            },
        )
        yield GraphEvent(
            type="agent_thinking",
            data={
                "role": agent.role,
                "name": agent.name,
                "avatar": agent.avatar,
                "color": agent.color,
                "category": agent.category,
                "stage": task.name,
            },
        )

        # 组装 prompt
        dep_artifacts = state.get_dependency_artifacts(task.id)
        dep_text = self._format_dependency_artifacts(dep_artifacts) if dep_artifacts else ""
        prompt = build_worker_prompt(
            agent=agent,
            user_request=state.user_request,
            task_name=task.name,
            task_description=task.description,
            expected_output=task.expected_output,
            dependency_artifacts_text=dep_text,
        )

        # 调 LLM
        try:
            content = await self._call_agent_llm(agent, prompt, task.name)
        except Exception as e:
            logger.error(f"任务 {task.id} LLM 调用失败: {e}", exc_info=True)
            state.mark_failed(task.id, str(e))
            yield GraphEvent(
                type="task_completed",
                data={
                    "task_id": task.id,
                    "task_name": task.name,
                    "agent_id": agent.id,
                    "agent_name": agent.name,
                    "state": "failed",
                    "error": str(e),
                },
            )
            yield GraphEvent(
                type="graph_node_failed",
                data={"task_id": task.id, "error": str(e)},
            )
            return

        # 流式 chunk(模拟,因为这里已经拿到完整内容)
        yield GraphEvent(
            type="agent_chunk",
            data={
                "role": agent.role,
                "name": agent.name,
                "chunk": content[:200],
            },
        )

        # 校验输出章节,缺章节则修正一次
        is_valid, missing = validate_output(content, agent)
        if not is_valid and self.llm:
            try:
                fix_prompt = build_fix_prompt(agent, content, missing)
                fixed_content = await self._call_agent_llm(agent, fix_prompt, f"{task.name}-修正")
                if fixed_content and len(fixed_content) > len(content) * 0.5:
                    content = fixed_content
            except Exception as e:
                logger.warning(f"任务 {task.id} 输出修正失败: {e}")

        # 创建 artifact
        contract = get_contract(agent)
        artifact = Artifact(
            id=new_artifact_id(),
            task_id=task.id,
            agent_id=agent.id,
            agent_name=agent.name,
            type=contract["artifact_type"],
            title=task.name,
            content=content,
            summary=content[:200] if content else "",
        )
        state.add_artifact(artifact)

        # 标记任务完成
        state.mark_done(task.id)

        # 广播 agent_done
        yield GraphEvent(
            type="agent_done",
            data={
                "role": agent.role,
                "name": agent.name,
                "avatar": agent.avatar,
                "color": agent.color,
                "content": content,
                "stage": task.name,
                "task_id": task.id,
                "artifact_id": artifact.id,
            },
        )

        # 广播 artifact_created
        yield GraphEvent(
            type="artifact_created",
            data={
                "artifact": artifact.to_dict(),
                "task_id": task.id,
                "is_final": False,
            },
        )

        # 广播 task_completed
        yield GraphEvent(
            type="task_completed",
            data={
                "task_id": task.id,
                "task_name": task.name,
                "agent_id": agent.id,
                "agent_name": agent.name,
                "state": "done",
                "artifact_id": artifact.id,
            },
        )

    async def _call_agent_llm(
        self, agent: AgentDef, prompt: str, stage: str = ""
    ) -> str:
        """调用 agent LLM — 组装 system + user message。"""
        if not self.llm:
            return f"[{agent.name}] (LLM 未配置,无法执行任务「{stage}」)"

        system_prompt = build_agent_system_prompt(agent)
        messages = [
            Message(role=MessageRole.SYSTEM, content=system_prompt),
            Message(role=MessageRole.USER, content=prompt),
        ]

        if isinstance(self.llm, MeteredLLMProvider):
            resp = await self.llm.achat(
                messages, session_id="agent-team", agent_role=agent.role,
            )
        else:
            resp = await self.llm.achat(messages)
        return resp.content or ""

    def _format_dependency_artifacts(self, artifacts: list[Artifact]) -> str:
        """格式化上游 artifact 供 prompt 注入。"""
        lines = []
        for a in artifacts:
            lines.append(f"### 【{a.agent_name}】{a.title}")
            lines.append(f"类型:{a.type}")
            # 截断避免 prompt 过长
            content = a.content[:1500]
            if len(a.content) > 1500:
                content += "\n...(内容已截断)"
            lines.append(content)
            lines.append("")
        return "\n".join(lines)


# ===== 全局引擎实例 =====

_graph_engine: GraphCollaborationEngine | None = None


def get_graph_engine(llm: MeteredLLMProvider | None = None) -> GraphCollaborationEngine:
    """获取或创建 graph 引擎实例。"""
    global _graph_engine
    if _graph_engine is None or llm is not None:
        _graph_engine = GraphCollaborationEngine(llm=llm)
    return _graph_engine
