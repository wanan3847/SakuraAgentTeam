"""Workflow DAG definitions - defines execution order of Agents.

Three workflow types:
1. FULL_GREENFIELD  - New project from scratch (all agents)
2. BROWNFIELD       - Existing code, selective agents
3. INCREMENTAL      - Small feature add, minimal agents
"""

from dataclasses import dataclass, field
from typing import List, Optional

from app.agents.types import AgentRole


@dataclass
class WorkflowStep:
    """A single step in the workflow DAG."""

    agent_role: AgentRole
    depends_on: List[AgentRole] = field(default_factory=list)
    optional: bool = False


@dataclass
class Workflow:
    """A named workflow - an ordered DAG of agent steps."""

    name: str
    description: str
    steps: List[WorkflowStep]


# ---------------------------------------------------------------------------
# 1. FULL_GREENFIELD: Start from scratch - full workflow
# ---------------------------------------------------------------------------
FULL_GREENFIELD = Workflow(
    name="full_greenfield",
    description="Full development workflow for new projects from scratch",
    steps=[
        WorkflowStep(
            agent_role=AgentRole.REQUIREMENTS,
            depends_on=[],
        ),
        WorkflowStep(
            agent_role=AgentRole.DESIGN,
            depends_on=[AgentRole.REQUIREMENTS],
        ),
        # Frontend and Backend run in parallel, both depending on DESIGN
        WorkflowStep(
            agent_role=AgentRole.FRONTEND,
            depends_on=[AgentRole.DESIGN],
        ),
        WorkflowStep(
            agent_role=AgentRole.BACKEND,
            depends_on=[AgentRole.DESIGN],
        ),
        # Testing depends on both frontend + backend
        WorkflowStep(
            agent_role=AgentRole.TESTING,
            depends_on=[AgentRole.FRONTEND, AgentRole.BACKEND],
        ),
        # Review checks everything
        WorkflowStep(
            agent_role=AgentRole.REVIEW,
            depends_on=[AgentRole.FRONTEND, AgentRole.BACKEND, AgentRole.TESTING],
        ),
        # Deployment finalizes
        WorkflowStep(
            agent_role=AgentRole.DEPLOYMENT,
            depends_on=[AgentRole.REVIEW],
        ),
    ],
)

# ---------------------------------------------------------------------------
# 2. BROWNFIELD: Existing project - analyze + selective codegen
# ---------------------------------------------------------------------------
BROWNFIELD = Workflow(
    name="brownfield",
    description="Workflow for extending existing projects",
    steps=[
        WorkflowStep(
            agent_role=AgentRole.REQUIREMENTS,
            depends_on=[],
        ),
        WorkflowStep(
            agent_role=AgentRole.DESIGN,
            depends_on=[AgentRole.REQUIREMENTS],
        ),
        WorkflowStep(
            agent_role=AgentRole.BACKEND,
            depends_on=[AgentRole.DESIGN],
        ),
        WorkflowStep(
            agent_role=AgentRole.TESTING,
            depends_on=[AgentRole.BACKEND],
        ),
        WorkflowStep(
            agent_role=AgentRole.REVIEW,
            depends_on=[AgentRole.BACKEND, AgentRole.TESTING],
            optional=True,
        ),
    ],
)

# ---------------------------------------------------------------------------
# 3. INCREMENTAL: Minimal workflow for small feature additions
# ---------------------------------------------------------------------------
INCREMENTAL = Workflow(
    name="incremental",
    description="Minimal workflow for small feature additions",
    steps=[
        WorkflowStep(
            agent_role=AgentRole.REQUIREMENTS,
            depends_on=[],
        ),
        WorkflowStep(
            agent_role=AgentRole.BACKEND,
            depends_on=[AgentRole.REQUIREMENTS],
        ),
        WorkflowStep(
            agent_role=AgentRole.REVIEW,
            depends_on=[AgentRole.BACKEND],
            optional=True,
        ),
    ],
)

# Registry of all workflows
WORKFLOWS = {
    FULL_GREENFIELD.name: FULL_GREENFIELD,
    BROWNFIELD.name: BROWNFIELD,
    INCREMENTAL.name: INCREMENTAL,
}


def get_workflow(name: str) -> Optional[Workflow]:
    """Get workflow by name."""
    return WORKFLOWS.get(name)


def list_workflow_names() -> List[str]:
    """List all available workflow names."""
    return list(WORKFLOWS.keys())


def get_default_workflow() -> Workflow:
    """Get the default (full greenfield) workflow."""
    return FULL_GREENFIELD
