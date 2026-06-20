"""Agent base class defining the unified lifecycle.

Inspired by Claude Code's Coordinator pattern + OpenHands's Agent abstraction.

Each Agent follows the same lifecycle:
  1. plan(ctx)    -> Plan      # Analyze context, create execution plan
  2. execute(plan, ctx) -> Artifact  # Execute plan steps
  3. review(artifact, ctx) -> ReviewResult  # Self-review output

Subclasses implement the specific logic for their role.
"""

from abc import ABC, abstractmethod
import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.core.logging import get_logger
from app.foundation.llm.base import LLMProvider, Message, MessageRole
from app.agents.types import (
    AgentRole,
    AgentStatus,
    Artifact,
    Context,
    Plan,
    PlanStep,
)

logger = get_logger(__name__)


@dataclass
class ReviewResult:
    """Result of an Agent's self-review."""

    passed: bool
    issues: List[str]
    suggestions: List[str]


class Agent(ABC):
    """Abstract base class for all Agents.

    Provides the unified lifecycle interface (plan -> execute -> review)
    and shared utilities (LLM calls, tool execution, logging).
    """

    role: AgentRole
    description: str = ""
    system_prompt: str = ""
    skills: List[str] = field(default_factory=list) if False else []

    def __init__(
        self,
        llm_provider: Optional[LLMProvider] = None,
        tools: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the Agent.

        Args:
            llm_provider: LLM provider for LLM-based reasoning
            tools: Available tools (inherited from registry)
        """
        self.llm = llm_provider
        self.tools = tools or {}
        self.status: AgentStatus = AgentStatus.PENDING
        self.current_plan: Optional[Plan] = None
        self.last_artifact: Optional[Artifact] = None

    async def plan(self, ctx: Context) -> Plan:
        """Create an execution plan based on the shared context.

        Default: Ask LLM to break the task into steps.
        Subclasses may override with role-specific planning logic.
        """
        self.status = AgentStatus.RUNNING
        logger.info("agent_planning", agent_role=self.role.value)

        # Build prompt for planning
        previous_outputs = []
        for role, output in ctx.agent_outputs.items():
            if isinstance(output, Artifact):
                previous_outputs.append(f"- {role}: {output.artifact_type} - {output.name}")
            else:
                previous_outputs.append(f"- {role}: {type(output).__name__}")

        planning_prompt = f"""You are the {self.role.value} agent in a multi-agent workflow.

## Your Role
{self.description or self._default_description()}

## User Requirement
{ctx.user_requirement}

## Previous Agent Outputs
{'No previous outputs yet (first agent in the chain)' if not previous_outputs else chr(10).join(previous_outputs)}

## Experience Hints (lessons from past)
{chr(10).join(f"- {h['content']}" for h in ctx.experience_hints) if ctx.experience_hints else "No past experiences"}

## Task
Create a plan with 2-5 steps to complete your part of the work.
Return your response as a JSON object:
{{
  "summary": "brief description of what you will do",
  "steps": [
    {{
      "description": "Step description",
      "tool": "name_of_tool",
      "parameters": {{ ... }}
    }}
  ]
}}"""

        plan = Plan(agent_role=self.role.value, summary="")

        # For now, provide a default plan if LLM not available
        # In production this uses the LLM planning prompt
        plan.summary = self._default_plan_summary(ctx)
        for step in self._default_plan_steps(ctx):
            plan.steps.append(step)

        self.current_plan = plan
        logger.info(
            "agent_plan_created",
            agent_role=self.role.value,
            steps_count=len(plan.steps),
        )

        return plan

    @abstractmethod
    async def execute(self, plan: Plan, ctx: Context) -> Artifact:
        """Execute the plan and produce an artifact.

        This method contains the role-specific logic.
        """
        ...

    async def review(self, artifact: Artifact, ctx: Context) -> ReviewResult:
        """Self-review the generated artifact.

        Default: Always passes. Subclasses should implement actual checks.
        """
        logger.info("agent_reviewing", agent_role=self.role.value)

        # Default checks: verify artifact has content
        issues = []
        suggestions = []

        if not artifact.content or len(str(artifact.content).strip()) < 50:
            issues.append("Content appears too short")

        # TODO: Use LLM for deeper review in production

        passed = len(issues) == 0

        if passed:
            self.status = AgentStatus.COMPLETED
        else:
            self.status = AgentStatus.FAILED

        logger.info(
            "agent_review_complete",
            agent_role=self.role.value,
            passed=passed,
            issues_count=len(issues),
        )

        return ReviewResult(
            passed=passed,
            issues=issues,
            suggestions=suggestions,
        )

    async def run(self, ctx: Context) -> Artifact:
        """Full agent lifecycle: plan -> execute -> review."""
        logger.info(
            "agent_starting",
            agent_role=self.role.value,
            session_id=ctx.session_id,
        )

        # 1. Plan
        plan = await self.plan(ctx)

        # 2. Execute
        artifact = await self.execute(plan, ctx)
        self.last_artifact = artifact

        # 3. Review
        review = await self.review(artifact, ctx)

        if not review.passed:
            logger.warning(
                "agent_review_failed",
                agent_role=self.role.value,
                issues=review.issues,
            )

        # Register output in shared context
        ctx.set_output(self.role.value, artifact)

        # Persist changes to the project git repo so users can roll back.
        await self._commit_to_project_repo(ctx, artifact)

        logger.info(
            "agent_completed",
            agent_role=self.role.value,
            status=self.status.value,
        )

        return artifact

    async def _commit_to_project_repo(self, ctx: Context, artifact: Artifact) -> None:
        """Commit the agent's output to the project's git repository.

        If GitPython is not installed or the project repo can't be opened,
        this is a silent no-op — agents should never fail just because we
        couldn't snapshot.
        """
        try:
            from app.foundation.git_repo import open_or_create

            projects_root = ctx.metadata.get("projects_root") if ctx.metadata else None
            project_id = ctx.metadata.get("project_id") if ctx.metadata else None
            if not projects_root or not project_id:
                return  # nothing to commit

            # Materialize the artifact to disk before committing.
            files_to_write: list[tuple[str, str]] = []

            files_meta = (
                artifact.metadata.get("files") if artifact.metadata else None
            )
            if isinstance(files_meta, list):
                for entry in files_meta:
                    if isinstance(entry, dict) and "path" in entry and "content" in entry:
                        files_to_write.append((entry["path"], entry["content"]))
            elif artifact.metadata and isinstance(artifact.metadata.get("path"), str):
                files_to_write.append(
                    (artifact.metadata["path"], str(artifact.content))
                )

            def _do_commit() -> Optional[str]:
                repo = open_or_create(projects_root, project_id)
                if files_to_write:
                    written_paths = []
                    for rel_path, content in files_to_write:
                        target = repo.path / rel_path
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_text(content, encoding="utf-8")
                        written_paths.append(rel_path)
                    return repo.commit(
                        message=f"[{self.role.value}] {artifact.name[:60]}",
                        paths=written_paths,
                    )
                return None  # nothing material to commit

            sha = await asyncio.to_thread(_do_commit)
            if sha:
                logger.debug(
                    "agent_git_committed",
                    sha=sha[:7],
                    file_count=len(files_to_write),
                )
        except Exception as exc:  # noqa: BLE001 — non-fatal
            logger.debug("agent_git_commit_skipped", error=str(exc))

    # --- Experience integration -----------------------------------------

    async def query_experience(
        self,
        error_message: str,
        error_type: str = "",
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        """Search the experience store for similar past errors.

        Returns a list of hint dicts: ``{content, error_type, solution}``.
        Empty list if nothing matches or the store is unavailable.
        """
        try:
            from app.foundation.experience import experience_store

            matches = experience_store.search_similar(
                error_message=error_message,
                context={"agent_role": self.role.value},
                top_k=top_k,
            )
            return [
                {
                    "content": m.final_solution or m.error_message,
                    "error_type": m.error_type,
                    "solution": m.final_solution,
                }
                for m in matches
            ]
        except Exception as exc:  # noqa: BLE001
            logger.debug("agent_query_experience_failed", error=str(exc))
            return []

    async def record_experience(
        self,
        error_message: str,
        error_type: str,
        solution: str,
        success: bool = True,
    ) -> Optional[str]:
        """Persist a new experience to the global store.

        Called by subclasses (or by the orchestrator) when an error has
        been successfully resolved so the next session can learn from it.
        """
        try:
            from app.foundation.experience import experience_store

            return experience_store.add_experience(
                error_message=error_message,
                error_type=error_type,
                context={"agent_role": self.role.value},
                final_solution=solution,
                success=success,
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("agent_record_experience_failed", error=str(exc))
            return None

    # --- Default implementations for subclasses to override ---

    def _default_description(self) -> str:
        """Default description for the Agent."""
        return {
            AgentRole.REQUIREMENTS: "Analyze user requirement and produce a PRD document",
            AgentRole.DESIGN: "Produce system design, API contracts, and architecture decisions",
            AgentRole.FRONTEND: "Generate React/Tailwind frontend code for the application",
            AgentRole.BACKEND: "Generate FastAPI backend code and API definitions",
            AgentRole.TESTING: "Generate unit tests and E2E tests",
            AgentRole.REVIEW: "Review all generated code, fix issues, ensure quality",
            AgentRole.DEPLOYMENT: "Build Docker config and start the application",
        }.get(self.role, "Generic agent")

    def _default_plan_summary(self, ctx: Context) -> str:
        """Default plan summary."""
        return f"Execute {self.role.value} tasks based on requirements"

    def _default_plan_steps(self, ctx: Context) -> List[PlanStep]:
        """Default plan steps - subclasses should override."""
        return [
            PlanStep(
                description=f"Analyze requirement for {self.role.value}",
                tool="llm_chat",
                parameters={"prompt": ctx.user_requirement},
            ),
            PlanStep(
                description=f"Generate output for {self.role.value}",
                tool="file_write",
                parameters={"path": f"output/{self.role.value}.txt"},
            ),
        ]
