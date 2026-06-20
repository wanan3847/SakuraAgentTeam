"""Session Manager - manages lifecycle of user sessions.

A Session represents a single user request being processed by the Agent workflow.
It stores the current state, Agent progress, and all generated artifacts.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from app.agents.types import AgentRole, AgentStatus, Artifact, Context
from app.core.logging import get_logger

logger = get_logger(__name__)


def _utcnow_iso() -> str:
    """Return current UTC time as ISO 8601 string with timezone info."""
    return datetime.now(UTC).isoformat()


class SessionStatus(StrEnum):
    """Overall status of a Session."""

    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AgentProgress:
    """Progress of a single Agent within a Session."""

    role: str
    status: AgentStatus = AgentStatus.PENDING
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None


@dataclass
class Session:
    """A full session: user request + Agent workflow + artifacts."""

    id: str
    requirement: str
    project_id: str
    status: SessionStatus = SessionStatus.CREATED
    created_at: str = field(default_factory=_utcnow_iso)
    updated_at: str = field(default_factory=_utcnow_iso)
    agent_progress: dict[str, AgentProgress] = field(default_factory=dict)
    artifacts: list[Artifact] = field(default_factory=list)
    context: Context | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize session for frontend."""
        return {
            "id": self.id,
            "requirement": self.requirement,
            "project_id": self.project_id,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "agent_progress": {
                role: {
                    "status": p.status.value,
                    "started_at": p.started_at,
                    "completed_at": p.completed_at,
                }
                for role, p in self.agent_progress.items()
            },
            "artifacts_count": len(self.artifacts),
            "error": self.error_message,
        }


class SessionManager:
    """Manages the lifecycle of Sessions.

    Features:
    - Create/retrieve sessions
    - Persist session state (in-memory for MVP, Redis/DB later)
    - Cancel running sessions
    - List historical sessions
    """

    def __init__(self):
        """Initialize session storage."""
        self._sessions: dict[str, Session] = {}
        self._lock = asyncio.Lock()

    def create_session(self, requirement: str, project_id: str | None = None) -> Session:
        """Create a new session."""
        session_id = uuid4().hex[:16]
        pid = project_id or session_id

        session = Session(
            id=session_id,
            requirement=requirement,
            project_id=pid,
            status=SessionStatus.CREATED,
        )

        # Initialize agent progress for all expected roles
        for role in AgentRole:
            session.agent_progress[role.value] = AgentProgress(role=role.value)

        self._sessions[session_id] = session

        logger.info(
            "session_created",
            session_id=session_id,
            requirement_length=len(requirement),
        )

        return session

    def get_session(self, session_id: str) -> Session | None:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    def list_sessions(self) -> list[Session]:
        """List all sessions (most recent first)."""
        return sorted(
            self._sessions.values(),
            key=lambda s: s.created_at,
            reverse=True,
        )

    async def update_status(self, session_id: str, status: SessionStatus) -> None:
        """Update session status."""
        session = self._sessions.get(session_id)
        if not session:
            return

        session.status = status
        session.updated_at = _utcnow_iso()

        logger.info(
            "session_status_updated",
            session_id=session_id,
            status=status.value,
        )

    async def update_agent_progress(
        self,
        session_id: str,
        agent_role: str,
        status: AgentStatus,
        error: str | None = None,
    ) -> None:
        """Update progress for a specific Agent in a session."""
        session = self._sessions.get(session_id)
        if not session:
            return

        if agent_role not in session.agent_progress:
            session.agent_progress[agent_role] = AgentProgress(role=agent_role)

        progress = session.agent_progress[agent_role]
        progress.status = status
        session.updated_at = _utcnow_iso()

        if status == AgentStatus.RUNNING and not progress.started_at:
            progress.started_at = _utcnow_iso()
        if status in (AgentStatus.COMPLETED, AgentStatus.FAILED):
            progress.completed_at = _utcnow_iso()
        if error:
            progress.error = error

        logger.debug(
            "agent_progress_updated",
            session_id=session_id,
            agent_role=agent_role,
            status=status.value,
        )

    async def add_artifact(self, session_id: str, artifact: Artifact) -> None:
        """Register an artifact with a session."""
        session = self._sessions.get(session_id)
        if not session:
            return

        session.artifacts.append(artifact)
        session.updated_at = _utcnow_iso()

        logger.info(
            "artifact_added",
            session_id=session_id,
            agent_role=artifact.agent_role,
            artifact_type=artifact.artifact_type,
            name=artifact.name,
        )

    async def set_error(self, session_id: str, error: str) -> None:
        """Record an error on the session."""
        session = self._sessions.get(session_id)
        if not session:
            return

        session.error_message = error
        session.status = SessionStatus.FAILED
        session.updated_at = _utcnow_iso()

        logger.error(
            "session_error",
            session_id=session_id,
            error=error,
        )

    async def cancel_session(self, session_id: str) -> bool:
        """Cancel a running session."""
        session = self._sessions.get(session_id)
        if not session:
            return False

        session.status = SessionStatus.CANCELLED
        session.updated_at = _utcnow_iso()

        logger.info("session_cancelled", session_id=session_id)
        return True


# Global session manager instance
session_manager = SessionManager()
