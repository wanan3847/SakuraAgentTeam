"""Orchestration module — Session / Engine / Workflow / EventBus.

统一导出多 Agent 编排所需的核心组件。
"""

from app.orchestration.dynamic import (
    ProjectAnalysis,
    ProjectAnalyzer,
    ProjectState,
    WorkflowSelector,
    workflow_selector,
)
from app.orchestration.engine import WorkflowEngine, create_default_engine
from app.orchestration.eventbus import Event, EventBus, EventType, event_bus
from app.orchestration.session import (
    AgentProgress,
    Session,
    SessionManager,
    SessionStatus,
    session_manager,
)
from app.orchestration.workflows import (
    Workflow,
    WorkflowStep,
    get_default_workflow,
    get_workflow,
    list_workflow_names,
)

__all__ = [
    # session
    "AgentProgress",
    "Session",
    "SessionManager",
    "SessionStatus",
    "session_manager",
    # engine
    "WorkflowEngine",
    "create_default_engine",
    # eventbus
    "Event",
    "EventBus",
    "EventType",
    "event_bus",
    # workflows
    "Workflow",
    "WorkflowStep",
    "get_default_workflow",
    "get_workflow",
    "list_workflow_names",
    # dynamic
    "ProjectAnalysis",
    "ProjectAnalyzer",
    "ProjectState",
    "WorkflowSelector",
    "workflow_selector",
]
