"""Agents module - exports all agent classes and registry."""

from app.agents.backend_agent import BackendAgent
from app.agents.base import Agent, ReviewResult
from app.agents.deployment_agent import DeploymentAgent
from app.agents.design_agent import DesignAgent
from app.agents.frontend_agent import FrontendAgent
from app.agents.requirements_agent import RequirementsAgent
from app.agents.review_agent import ReviewAgent
from app.agents.testing_agent import TestingAgent
from app.agents.types import AgentRole, AgentStatus, Artifact, Context, Plan, PlanStep

# Registry: role -> Agent class
AGENT_REGISTRY = {
    AgentRole.REQUIREMENTS: RequirementsAgent,
    AgentRole.DESIGN: DesignAgent,
    AgentRole.FRONTEND: FrontendAgent,
    AgentRole.BACKEND: BackendAgent,
    AgentRole.TESTING: TestingAgent,
    AgentRole.REVIEW: ReviewAgent,
    AgentRole.DEPLOYMENT: DeploymentAgent,
}


def create_all_agents() -> dict:
    """Instantiate one agent of each type."""
    return {role: agent_class() for role, agent_class in AGENT_REGISTRY.items()}


def list_available_roles() -> list:
    """List all available agent roles."""
    return [role.value for role in AGENT_REGISTRY.keys()]


def get_agent(role: str | AgentRole):
    """Return an instance of the agent for the given role.

    Accepts either a string (``"requirements"``) or an ``AgentRole`` enum.
    Raises ``KeyError`` if the role is unknown.
    """
    if isinstance(role, str):
        role = AgentRole(role)
    return AGENT_REGISTRY[role]()


__all__ = [
    "Agent",
    "ReviewResult",
    "AgentRole",
    "AgentStatus",
    "Artifact",
    "Context",
    "Plan",
    "PlanStep",
    "RequirementsAgent",
    "DesignAgent",
    "FrontendAgent",
    "BackendAgent",
    "TestingAgent",
    "ReviewAgent",
    "DeploymentAgent",
    "AGENT_REGISTRY",
    "create_all_agents",
    "get_agent",
    "list_available_roles",
]
