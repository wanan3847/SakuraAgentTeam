"""
统一协作数据模型 — 借鉴 CrewAI / LangGraph / MetaGPT。

定义 Artifact / TaskNode / CollaborationState,作为所有协作模式的统一数据底座。
与 agent_team.py 里现有的 TaskNode / WhiteboardArtifact 保持兼容,但增加:
- expected_output(强制每个任务声明期望产出)
- artifact_ids(任务产出的 artifact 列表)
- final_artifact_id(最终交付物)
- 全局 COLLAB_SESSIONS 存储,支持 session_id 查询
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal


# ===== 类型别名 =====

TaskState = Literal["pending", "ready", "running", "done", "failed", "skipped"]

# 借鉴 MetaGPT SOP + 通用协作场景
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
    "research",
    "strategy",
    "creative",
    "final_report",
    "text",  # 兜底类型
]


# ===== 核心数据结构 =====

@dataclass
class Artifact:
    """协作产物 — 每个 agent 执行后至少写入一个。

    借鉴 MetaGPT:产物比聊天更重要,下游 agent 直接引用上游 artifact。
    """

    id: str
    task_id: str
    agent_id: str
    agent_name: str
    type: ArtifactType
    title: str
    content: str
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "type": self.type,
            "title": self.title,
            "content": self.content,
            "summary": self.summary or self.content[:120],
            "metadata": self.metadata,
            "created_at": self.created_at,
        }


@dataclass
class CollabTaskNode:
    """任务节点 — 借鉴 LangGraph.StateGraph + CrewAI.Task。

    与 agent_team.py 的 TaskNode 区别:
    - 加 expected_output(强制声明)
    - artifact_ids 替代 artifacts(只存 id,实体在 CollaborationState.artifacts)
    """

    id: str
    name: str
    description: str
    expected_output: str = ""
    agent_id: str = ""
    agent_name: str = ""
    dependencies: list[str] = field(default_factory=list)
    state: TaskState = "pending"
    artifact_ids: list[str] = field(default_factory=list)
    error: str = ""
    started_at: float = 0.0
    finished_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "expected_output": self.expected_output,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "dependencies": self.dependencies,
            "state": self.state,
            "artifact_ids": list(self.artifact_ids),
            "error": self.error,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


@dataclass
class CollaborationState:
    """一次协作的完整状态 — 借鉴 LangGraph 的 StateGraph。

    所有协作模式(graph/master/pipeline/parallel/group/consensus/handoff)
    都应该创建并填充这个状态,最终产出 final_artifact_id。
    """

    session_id: str
    user_request: str
    mode: str = "graph"
    team_id: str = ""
    team_name: str = ""
    tasks: list[CollabTaskNode] = field(default_factory=list)
    artifacts: list[Artifact] = field(default_factory=list)
    final_artifact_id: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    # ===== 任务操作 =====

    def add_task(self, task: CollabTaskNode) -> None:
        self.tasks.append(task)
        self.updated_at = time.time()

    def get_task(self, task_id: str) -> CollabTaskNode | None:
        for t in self.tasks:
            if t.id == task_id:
                return t
        return None

    def get_ready_tasks(self) -> list[CollabTaskNode]:
        """找出依赖都已完成、可执行的任务。"""
        done_ids = {t.id for t in self.tasks if t.state == "done"}
        ready = []
        for t in self.tasks:
            if t.state == "pending" and all(dep in done_ids for dep in t.dependencies):
                t.state = "ready"
                ready.append(t)
        return ready

    def has_unfinished_tasks(self) -> bool:
        return any(t.state not in ("done", "failed", "skipped") for t in self.tasks)

    def mark_running(self, task_id: str) -> None:
        t = self.get_task(task_id)
        if t:
            t.state = "running"
            t.started_at = time.time()
            self.updated_at = time.time()

    def mark_done(self, task_id: str) -> None:
        t = self.get_task(task_id)
        if t:
            t.state = "done"
            t.finished_at = time.time()
            self.updated_at = time.time()

    def mark_failed(self, task_id: str, error: str = "") -> None:
        t = self.get_task(task_id)
        if t:
            t.state = "failed"
            t.error = error
            t.finished_at = time.time()
            # 依赖此任务的所有下游任务标记为 skipped
            for downstream in self.tasks:
                if task_id in downstream.dependencies and downstream.state == "pending":
                    downstream.state = "skipped"
                    downstream.error = f"上游任务 {task_id} 失败"
            self.updated_at = time.time()

    # ===== Artifact 操作 =====

    def add_artifact(self, artifact: Artifact) -> None:
        self.artifacts.append(artifact)
        # 关联到任务
        task = self.get_task(artifact.task_id)
        if task and artifact.id not in task.artifact_ids:
            task.artifact_ids.append(artifact.id)
        self.updated_at = time.time()

    def get_artifact(self, artifact_id: str) -> Artifact | None:
        for a in self.artifacts:
            if a.id == artifact_id:
                return a
        return None

    def get_artifacts_by_task(self, task_id: str) -> list[Artifact]:
        return [a for a in self.artifacts if a.task_id == task_id]

    def get_dependency_artifacts(self, task_id: str) -> list[Artifact]:
        """获取某任务的所有上游依赖任务的 artifact。"""
        task = self.get_task(task_id)
        if not task:
            return []
        dep_artifacts: list[Artifact] = []
        for dep_id in task.dependencies:
            dep_artifacts.extend(self.get_artifacts_by_task(dep_id))
        return dep_artifacts

    def set_final_artifact(self, artifact: Artifact) -> None:
        self.artifacts.append(artifact)
        self.final_artifact_id = artifact.id
        self.updated_at = time.time()

    # ===== 序列化 =====

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_request": self.user_request,
            "mode": self.mode,
            "team_id": self.team_id,
            "team_name": self.team_name,
            "tasks": [t.to_dict() for t in self.tasks],
            "artifacts": [a.to_dict() for a in self.artifacts],
            "final_artifact_id": self.final_artifact_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def to_snapshot(self) -> dict[str, Any]:
        """给前端 graph_snapshot 用的精简快照。"""
        return {
            "session_id": self.session_id,
            "tasks": [t.to_dict() for t in self.tasks],
            "is_finished": not self.has_unfinished_tasks(),
            "final_artifact_id": self.final_artifact_id,
        }


# ===== 全局存储(短期内存,中期落库) =====

COLLAB_SESSIONS: dict[str, CollaborationState] = {}


def create_session(
    user_request: str,
    mode: str = "graph",
    team_id: str = "",
    team_name: str = "",
    session_id: str | None = None,
) -> CollaborationState:
    """创建一个新的协作会话并存入全局存储。"""
    sid = session_id or f"collab-{uuid.uuid4().hex[:12]}"
    state = CollaborationState(
        session_id=sid,
        user_request=user_request,
        mode=mode,
        team_id=team_id,
        team_name=team_name,
    )
    COLLAB_SESSIONS[sid] = state
    return state


def get_session(session_id: str) -> CollaborationState | None:
    return COLLAB_SESSIONS.get(session_id)


def new_artifact_id() -> str:
    return f"art-{uuid.uuid4().hex[:10]}"


def new_task_id(prefix: str = "task") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"
