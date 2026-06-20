"""Workflow Engine - orchestrates multi-Agent execution based on DAG.

Handles:
- DAG scheduling (dependency resolution)
- Parallel agent execution (frontend/backend run in parallel)
- Failure propagation (mark downstream as failed/skipped)
- Event emission (EventBus) for real-time frontend updates
- Context sharing between agents (shared state)
"""

import asyncio
from typing import Dict, List, Optional, Set

from app.core.logging import get_logger
from app.agents.base import Agent
from app.agents.types import AgentRole, AgentStatus, Context
from app.agents import create_all_agents
from app.orchestration.eventbus import Event, EventType, event_bus
from app.orchestration.session import SessionManager, SessionStatus, session_manager
from app.orchestration.workflows import Workflow, WorkflowStep, get_default_workflow

logger = get_logger(__name__)


class WorkflowEngine:
    """Executes a workflow DAG by scheduling agents in the correct order.

    Usage:
        engine = WorkflowEngine(agents_map)
        await engine.run(session_id, requirement, workflow=WORKFLOW)
    """

    def __init__(
        self,
        agent_registry: Optional[Dict[AgentRole, Agent]] = None,
        session_manager_instance: Optional[SessionManager] = None,
        event_bus_instance=None,
    ):
        """Initialize the workflow engine.

        Args:
            agent_registry: Mapping of AgentRole -> Agent instance
            session_manager_instance: Session manager for persistence
            event_bus_instance: Event bus for progress events
        """
        self._agents: Dict[AgentRole, Agent] = agent_registry or {}
        self._session_mgr = session_manager_instance or session_manager
        self._event_bus = event_bus_instance or event_bus
        self._active_sessions: Set[str] = set()

    def register_agent(self, role: AgentRole, agent: Agent) -> None:
        """Register an agent for a role."""
        self._agents[role] = agent

    def has_agent(self, role: AgentRole) -> bool:
        """Check if an agent is registered for the role."""
        return role in self._agents

    async def run(
        self,
        session_id: str,
        requirement: str,
        workflow: Optional[Workflow] = None,
        projects_root: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> bool:
        """Run a full workflow.

        Args:
            session_id: The session to execute (created by caller)
            requirement: User's natural language requirement
            workflow: DAG to execute (default: FULL_GREENFIELD)
            projects_root: Optional base directory for project git repos
            project_id: Optional project ID; defaults to session_id

        Returns:
            True if workflow completed successfully
        """
        if session_id in self._active_sessions:
            logger.warning("session_already_active", session_id=session_id)
            return False

        self._active_sessions.add(session_id)

        # Use default workflow if none specified
        workflow = workflow or get_default_workflow()

        logger.info(
            "workflow_starting",
            session_id=session_id,
            workflow=workflow.name,
            steps_count=len(workflow.steps),
        )

        # Update session status
        await self._session_mgr.update_status(session_id, SessionStatus.RUNNING)
        await self._event_bus.publish(
            Event(
                event_type=EventType.SESSION_STARTED.value,
                session_id=session_id,
                payload={
                    "workflow": workflow.name,
                    "steps_count": len(workflow.steps),
                },
            )
        )

        # Create shared context
        effective_project_id = project_id or session_id
        ctx = Context(
            session_id=session_id,
            project_id=effective_project_id,
            user_requirement=requirement,
            metadata={
                "projects_root": projects_root or "",
                "project_id": effective_project_id,
            },
        )

        # Track completed steps (so we can check dependencies)
        completed: Set[AgentRole] = set()
        failed: Set[AgentRole] = set()

        try:
            # Main scheduling loop - keep running until all steps are processed
            remaining_steps = list(workflow.steps)

            while remaining_steps:
                # Find all steps that have their dependencies satisfied
                ready_steps: List[WorkflowStep] = []
                still_waiting: List[WorkflowStep] = []

                for step in remaining_steps:
                    deps_satisfied = all(dep in completed for dep in step.depends_on)
                    deps_failed = any(dep in failed for dep in step.depends_on)

                    if deps_failed and not step.optional:
                        # Dependency failed -> this step can't run
                        logger.warning(
                            "step_skipped_due_to_failed_dep",
                            agent_role=step.agent_role.value,
                            session_id=session_id,
                        )
                        await self._session_mgr.update_agent_progress(
                            session_id,
                            step.agent_role.value,
                            AgentStatus.SKIPPED,
                            "Dependency failed",
                        )
                        failed.add(step.agent_role)
                        continue

                    if deps_satisfied:
                        ready_steps.append(step)
                    else:
                        still_waiting.append(step)

                if not ready_steps:
                    # Deadlock - no steps can run
                    logger.error(
                        "workflow_deadlock",
                        session_id=session_id,
                        remaining=[s.agent_role.value for s in remaining_steps],
                    )
                    break

                # Execute all ready steps (possibly in parallel)
                parallel_roles = [s.agent_role for s in ready_steps]

                logger.info(
                    "steps_executing",
                    session_id=session_id,
                    roles=[r.value for r in parallel_roles],
                )

                if len(parallel_roles) == 1:
                    # Single step (most common)
                    success = await self._execute_agent(
                        parallel_roles[0],
                        ctx,
                        session_id,
                    )
                    role = parallel_roles[0]
                    if success:
                        completed.add(role)
                    else:
                        failed.add(role)
                else:
                    # Parallel execution (e.g., frontend + backend)
                    tasks = [
                        self._execute_agent(role, ctx, session_id)
                        for role in parallel_roles
                    ]
                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    for role, result in zip(parallel_roles, results):
                        success = isinstance(result, bool) and result
                        if success:
                            completed.add(role)
                        else:
                            failed.add(role)

                # Remove completed/failed from remaining
                remaining_steps = still_waiting

            # Determine overall status
            overall_success = len(failed) == 0

            if overall_success:
                await self._session_mgr.update_status(session_id, SessionStatus.COMPLETED)
                await self._event_bus.publish(
                    Event(
                        event_type=EventType.SESSION_COMPLETED.value,
                        session_id=session_id,
                        payload={
                            "steps_completed": len(completed),
                            "artifacts_count": len(ctx.agent_outputs),
                        },
                    )
                )
                logger.info("workflow_completed", session_id=session_id)
            else:
                await self._session_mgr.set_error(
                    session_id,
                    f"Agents failed: {[r.value for r in failed]}",
                )
                await self._event_bus.publish(
                    Event(
                        event_type=EventType.SESSION_FAILED.value,
                        session_id=session_id,
                        payload={"failed_agents": [r.value for r in failed]},
                    )
                )
                logger.warning(
                    "workflow_completed_with_errors",
                    session_id=session_id,
                    failed=[r.value for r in failed],
                )

            return overall_success

        except Exception as e:
            logger.exception("workflow_fatal_error", error=str(e), session_id=session_id)
            await self._session_mgr.set_error(session_id, f"Fatal error: {e}")
            await self._event_bus.publish(
                Event(
                    event_type=EventType.SESSION_FAILED.value,
                    session_id=session_id,
                    payload={"error": str(e)},
                )
            )
            return False
        finally:
            self._active_sessions.discard(session_id)

    async def _execute_agent(
        self, role: AgentRole, ctx: Context, session_id: str
    ) -> bool:
        """Execute a single Agent step.

        Args:
            role: Agent role to execute
            ctx: Shared context
            session_id: Session ID

        Returns:
            True if the agent completed successfully
        """
        if not self.has_agent(role):
            # No agent registered for this role -> skip gracefully
            logger.warning("agent_not_registered", role=role.value)
            await self._session_mgr.update_agent_progress(
                session_id, role.value, AgentStatus.SKIPPED, "Agent not implemented yet"
            )
            await self._event_bus.publish_log(
                session_id,
                role.value,
                "Agent not implemented in this build, skipping",
                "warn",
            )
            return True  # Not a hard failure - we continue the workflow

        await self._session_mgr.update_agent_progress(
            session_id, role.value, AgentStatus.RUNNING
        )
        await self._event_bus.publish(
            Event(
                event_type=EventType.AGENT_STARTED.value,
                session_id=session_id,
                payload={"agent_role": role.value},
            )
        )
        await self._event_bus.publish_log(session_id, role.value, f"{role.value} agent started")

        try:
            agent = self._agents[role]
            artifact = await agent.run(ctx)

            # Mark agent as completed in session progress
            await self._session_mgr.update_agent_progress(
                session_id, role.value, AgentStatus.COMPLETED
            )

            # Store artifact in session
            await self._session_mgr.add_artifact(session_id, artifact)
            await self._event_bus.publish(
                Event(
                    event_type=EventType.ARTIFACT_CREATED.value,
                    session_id=session_id,
                    payload={
                        "agent_role": role.value,
                        "artifact_type": artifact.artifact_type,
                        "name": artifact.name,
                        "size": len(artifact.content) if isinstance(artifact.content, str) else 0,
                    },
                )
            )
            await self._event_bus.publish(
                Event(
                    event_type=EventType.AGENT_COMPLETED.value,
                    session_id=session_id,
                    payload={"agent_role": role.value, "artifact": artifact.name},
                )
            )
            await self._event_bus.publish_log(
                session_id,
                role.value,
                f"{role.value} agent completed: {artifact.name}",
                "info",
            )
            return True

        except Exception as e:
            logger.exception("agent_execution_error", role=role.value, error=str(e))
            await self._session_mgr.update_agent_progress(
                session_id, role.value, AgentStatus.FAILED, str(e)
            )
            await self._event_bus.publish(
                Event(
                    event_type=EventType.AGENT_FAILED.value,
                    session_id=session_id,
                    payload={"agent_role": role.value, "error": str(e)},
                )
            )
            await self._event_bus.publish_log(
                session_id,
                role.value,
                f"Error: {e}",
                "error",
            )
            return False


# Convenience: Create a default engine with registered agents
def create_default_engine() -> WorkflowEngine:
    """Create a WorkflowEngine with all registered agents (those that are implemented)."""
    engine = WorkflowEngine()

    # Register all available agents
    agents = create_all_agents()
    for role, agent in agents.items():
        engine.register_agent(role, agent)

    logger.info("default_engine_created", agents_count=len(agents))
    return engine
