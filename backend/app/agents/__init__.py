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
from app.core.logging import get_logger

logger = get_logger(__name__)

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


def _build_llm_provider():
    """Build a metered LLM provider from environment configuration.

    Returns None if no API key is configured (agents will use template fallback).
    """
    from app.core.config import settings
    from app.foundation.llm import LLMProviderFactory
    from app.foundation.llm.meter import MeteredLLMProvider

    # 优先从 pydantic settings 读（.env 文件），回退到 os.environ
    # 因为有些启动路径不会自动把 settings 同步到 os.environ
    api_key = (
        settings.openai_api_key
        or settings.dashscope_api_key
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("DASHSCOPE_API_KEY")
    )
    if not api_key or "your-openai-key" in api_key or "your-dashscope" in api_key:
        return None

    api_base = (
        settings.openai_api_base
        or settings.dashscope_api_base
        or os.environ.get("OPENAI_API_BASE")
        or os.environ.get("DASHSCOPE_API_BASE")
    )
    model = settings.default_llm_model or os.environ.get("DEFAULT_LLM_MODEL", "gpt-4o")

    # Determine provider type
    provider_name = settings.default_llm_provider or os.environ.get("DEFAULT_LLM_PROVIDER", "openai")
    if provider_name == "litellm" or "/" in model:
        provider_name = "litellm"
    elif provider_name not in ("openai", "anthropic", "litellm"):
        provider_name = "openai"

    try:
        inner = LLMProviderFactory.create(
            provider=provider_name,
            model=model,
            api_key=api_key,
            base_url=api_base,
        )
        metered = MeteredLLMProvider(inner)
        logger.info(
            "llm_provider_built",
            provider=provider_name,
            model=model,
            base_url=api_base,
            key_prefix=api_key[:8] + "...",
        )
        return metered
    except Exception as exc:
        logger.warning("llm_provider_build_failed", error=str(exc))
        return None


def create_all_agents(llm_provider=None) -> dict:
    """Instantiate one agent of each type.

    Args:
        llm_provider: Optional LLM provider. If None, tries to build from env.
                      If env has no key, agents use template fallback.
    """
    if llm_provider is None:
        llm_provider = _build_llm_provider()

    agents = {}
    for role, agent_class in AGENT_REGISTRY.items():
        try:
            agent = agent_class(llm_provider=llm_provider)
        except TypeError:
            # Some agents might not accept llm_provider in __init__
            agent = agent_class()
        agents[role] = agent

    if llm_provider is not None:
        logger.info("agents_created_with_llm", count=len(agents), model=llm_provider.model)
    else:
        logger.info("agents_created_with_templates", count=len(agents))

    return agents


def list_available_roles() -> list:
    """List all available agent roles."""
    return [role.value for role in AGENT_REGISTRY.keys()]


def get_agent(role: str | AgentRole, llm_provider=None):
    """Return an instance of the agent for the given role.

    Accepts either a string (``"requirements"``) or an ``AgentRole`` enum.
    Raises ``KeyError`` if the role is unknown.
    """
    if isinstance(role, str):
        role = AgentRole(role)
    agent_class = AGENT_REGISTRY[role]
    try:
        return agent_class(llm_provider=llm_provider)
    except TypeError:
        return agent_class()


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
