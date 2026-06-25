"""Core data types for Agents - Context, Plan, Artifact.

Inspired by Claude Code's Task system and OpenHands's State management.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


class AgentRole(StrEnum):
    """Agent roles in the workflow."""

    REQUIREMENTS = "requirements"
    DESIGN = "design"
    FRONTEND = "frontend"
    BACKEND = "backend"
    TESTING = "testing"
    REVIEW = "review"
    DEPLOYMENT = "deployment"


class AgentStatus(StrEnum):
    """Execution status of an Agent."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TeamMessage:
    """Agent 间通信消息。

    用于 Agent 之间的协作通信，支持点对点和广播（to_role="all"）。
    """

    from_role: str  # 发送者 agent role
    to_role: str  # 接收者 agent role ("all" = 广播)
    message_type: str  # "question" | "suggestion" | "review" | "handoff"
    content: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Context:
    """Shared context passed between Agents in a workflow.

    Contains user requirement, project metadata, intermediate outputs,
    and experience hints.
    """

    session_id: str
    project_id: str
    user_requirement: str

    # Agent outputs keyed by role
    agent_outputs: dict[str, Any] = field(default_factory=dict)

    # Experience hints (used for error recovery)
    experience_hints: list[dict[str, str]] = field(default_factory=list)

    # General metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    # Agent 间通信消息
    team_messages: list[TeamMessage] = field(default_factory=list)

    def set_output(self, agent_role: str, output: Any) -> None:
        """Set output from an Agent."""
        self.agent_outputs[agent_role] = output

    def get_output(self, agent_role: str) -> Any | None:
        """Get output from a previous Agent."""
        return self.agent_outputs.get(agent_role)

    def add_hint(self, hint: str, source: str = "experience") -> None:
        """Add a hint/lesson for the current session."""
        self.experience_hints.append({"source": source, "content": hint})

    def send_message(
        self,
        from_role: str,
        to_role: str,
        message_type: str,
        content: str,
        **metadata: Any,
    ) -> TeamMessage:
        """发送一条 Agent 间通信消息。

        Args:
            from_role: 发送者 agent role
            to_role: 接收者 agent role ("all" = 广播)
            message_type: 消息类型 ("question" | "suggestion" | "review" | "handoff")
            content: 消息内容
            **metadata: 附加元数据

        Returns:
            创建的 TeamMessage
        """
        msg = TeamMessage(
            from_role=from_role,
            to_role=to_role,
            message_type=message_type,
            content=content,
            metadata=metadata,
        )
        self.team_messages.append(msg)
        return msg

    def get_messages(self, role: str | None = None) -> list[TeamMessage]:
        """获取消息列表。

        Args:
            role: 筛选角色。None=全部消息；
                  若提供则返回发给该 role 的消息（含广播 "all"）。

        Returns:
            匹配的 TeamMessage 列表
        """
        if role is None:
            return list(self.team_messages)
        return [
            m for m in self.team_messages if m.to_role == role or m.to_role == "all"
        ]

    def get_messages_from(self, role: str) -> list[TeamMessage]:
        """获取由指定 agent 发出的消息。"""
        return [m for m in self.team_messages if m.from_role == role]

    def get_messages_to(self, role: str) -> list[TeamMessage]:
        """获取发给指定 agent 的消息（含广播 "all"）。"""
        return [
            m for m in self.team_messages if m.to_role == role or m.to_role == "all"
        ]

    def to_dict(self) -> dict[str, Any]:
        """Serialize context for logging/frontend."""
        return {
            "session_id": self.session_id,
            "project_id": self.project_id,
            "user_requirement": self.user_requirement,
            "agent_outputs": list(self.agent_outputs.keys()),
            "hints_count": len(self.experience_hints),
            "team_messages_count": len(self.team_messages),
        }


@dataclass
class PlanStep:
    """A single step in an Agent's plan."""

    description: str
    tool: str  # Which tool to use
    parameters: dict[str, Any] = field(default_factory=dict)
    expected_output: str = ""


@dataclass
class Plan:
    """Plan created by an Agent before execution."""

    agent_role: str
    summary: str
    steps: list[PlanStep] = field(default_factory=list)

    def add_step(self, description: str, tool: str, parameters: dict[str, Any] = None) -> None:
        """Add a step to the plan."""
        self.steps.append(
            PlanStep(
                description=description,
                tool=tool,
                parameters=parameters or {},
            )
        )


@dataclass
class Artifact:
    """Output artifact generated by an Agent."""

    agent_role: str
    artifact_type: str  # e.g., "document", "code", "config"
    name: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize artifact for frontend/storage."""
        return {
            "agent_role": self.agent_role,
            "type": self.artifact_type,
            "name": self.name,
            "content": self.content,
            "metadata": self.metadata,
        }
