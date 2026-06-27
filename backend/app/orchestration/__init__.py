"""Orchestration module — Session / Engine / Workflow / EventBus / Collaboration.

统一导出多 Agent 编排所需的核心组件。
"""

from app.orchestration.collaboration_state import (
    Artifact,
    CollabTaskNode,
    CollaborationState,
    COLLAB_SESSIONS,
    create_session,
    get_session,
)
from app.orchestration.dynamic import (
    ProjectAnalysis,
    ProjectAnalyzer,
    ProjectState,
    WorkflowSelector,
    workflow_selector,
)
from app.orchestration.engine import WorkflowEngine, create_default_engine
from app.orchestration.eventbus import Event, EventBus, EventType, event_bus
from app.orchestration.finalizer import synthesize_final_artifact
from app.orchestration.graph_engine import GraphCollaborationEngine, GraphEvent, get_graph_engine
from app.orchestration.output_contracts import (
    build_finalizer_prompt,
    build_worker_prompt,
    get_contract,
    validate_output,
)
from app.orchestration.planner import plan_tasks, plan_tasks_async, tasks_to_nodes
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
    # collaboration (new)
    "Artifact",
    "CollabTaskNode",
    "CollaborationState",
    "COLLAB_SESSIONS",
    "create_session",
    "get_session",
    "GraphCollaborationEngine",
    "GraphEvent",
    "get_graph_engine",
    "plan_tasks",
    "plan_tasks_async",
    "tasks_to_nodes",
    "synthesize_final_artifact",
    "build_worker_prompt",
    "build_finalizer_prompt",
    "get_contract",
    "validate_output",
]
