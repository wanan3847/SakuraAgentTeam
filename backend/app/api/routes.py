"""API routes for the SakuraAgentTeam system.

Connects the orchestration engine to HTTP clients.
Provides Session creation, workflow execution, SSE streaming, artifact retrieval,
experience store, and workflow selection.
"""

import asyncio
import json
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.agents import AGENT_REGISTRY, create_all_agents, list_available_roles
from app.core.logging import get_logger
from app.foundation.experience import experience_store
from app.foundation.project import project_store
from app.orchestration import (
    Event,
    EventType,
    SessionStatus,
    create_default_engine,
    event_bus,
    session_manager,
    workflow_selector,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["sessions"])

# Create global workflow engine
_engine = None


def get_engine():
    """Get or create the workflow engine with all agents registered."""
    global _engine
    if _engine is None:
        _engine = create_default_engine()
        # Register all agents
        agents = create_all_agents()
        for role, agent in agents.items():
            if not _engine.has_agent(role):
                _engine.register_agent(role, agent)
        logger.info("workflow_engine_initialized", agents_count=len(AGENT_REGISTRY))
    return _engine


# ---------- Session APIs ----------


@router.get("/sessions")
def list_sessions():
    """List all sessions."""
    sessions = session_manager.list_sessions()
    return {
        "success": True,
        "data": [
            {
                "id": s.id,
                "requirement": s.requirement,
                "status": s.status.value,
                "created_at": s.created_at,
                "updated_at": s.updated_at,
                "agent_progress": {
                    role: {
                        "status": p.status.value,
                        "started_at": p.started_at,
                        "completed_at": p.completed_at,
                    }
                    for role, p in s.agent_progress.items()
                },
                "artifacts_count": len(s.artifacts),
                "error": s.error_message,
            }
            for s in sessions
        ],
    }


@router.post("/sessions")
async def create_session(request: Request, background_tasks: BackgroundTasks):
    """Create a new session and optionally start execution.

    Body: { "requirement": "...", "project_id": "...", "workflow": "full_greenfield|brownfield|incremental" }
    """
    body = await request.json()
    requirement = body.get("requirement", "").strip()
    if not requirement:
        raise HTTPException(status_code=400, detail="requirement is required")

    project_id = body.get("project_id")
    auto_start = body.get("auto_start", True)
    workflow_name = body.get("workflow")

    # Create session
    session = session_manager.create_session(requirement, project_id)

    logger.info("session_created", session_id=session.id)

    # Optionally start execution in background
    if auto_start:
        background_tasks.add_task(
            _execute_workflow,
            session.id,
            requirement,
            workflow_name,
        )

    return {
        "success": True,
        "data": {
            "id": session.id,
            "requirement": session.requirement,
            "status": session.status.value,
            "created_at": session.created_at,
        },
    }


@router.get("/sessions/{session_id}")
def get_session(session_id: str):
    """Get a session by ID."""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "success": True,
        "data": {
            "id": session.id,
            "requirement": session.requirement,
            "project_id": session.project_id,
            "status": session.status.value,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "agent_progress": {
                role: {
                    "status": p.status.value,
                    "started_at": p.started_at,
                    "completed_at": p.completed_at,
                    "error": p.error,
                }
                for role, p in session.agent_progress.items()
            },
            "artifacts": [
                {
                    "agent_role": str(a.agent_role),
                    "type": a.artifact_type,
                    "name": a.name,
                    "content_preview": a.content[:200] if isinstance(a.content, str) else "",
                    "metadata": a.metadata,
                }
                for a in session.artifacts
            ],
            "error": session.error_message,
        },
    }


@router.get("/sessions/{session_id}/artifacts")
def get_session_artifacts(session_id: str):
    """Get all artifacts for a session."""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "success": True,
        "data": [
            {
                "agent_role": str(a.agent_role),
                "type": a.artifact_type,
                "name": a.name,
                "content": a.content,
                "metadata": a.metadata,
            }
            for a in session.artifacts
        ],
    }


@router.post("/sessions/{session_id}/cancel")
async def cancel_session(session_id: str):
    """Cancel a running session."""
    result = await session_manager.cancel_session(session_id)
    return {"success": result, "message": "Cancelled" if result else "Session not found"}


@router.post("/sessions/{session_id}/execute")
async def execute_session(session_id: str, request: Request, background_tasks: BackgroundTasks):
    """Execute or re-execute a session's workflow."""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    body = await request.json()
    workflow_name = body.get("workflow") if body else None

    background_tasks.add_task(
        _execute_workflow,
        session.id,
        session.requirement,
        workflow_name,
    )

    return {"success": True, "message": "Execution started", "session_id": session.id}


# ---------- SSE Event Stream ----------


@router.get("/sessions/{session_id}/stream")
async def stream_session_events(session_id: str):
    """SSE stream of session events for real-time frontend updates."""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    async def event_generator():
        # Send initial state
        yield (
            f"event: initial_state\n"
            f"data: {json.dumps({'status': session.status.value, 'agents_count': len(session.agent_progress)})}\n\n"
        )

        # Send history
        history = event_bus.get_history(session_id)
        for evt in history:
            event_type_str = (
                evt.event_type if isinstance(evt.event_type, str) else evt.event_type.value
            )
            yield (
                f"event: {event_type_str}\n"
                f"data: {json.dumps({'timestamp': evt.timestamp, 'payload': evt.payload})}\n\n"
            )

        # Stream new events
        stream_queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        sentinel = object()

        # Create a simple listener callback
        async def listener(event):
            if event.session_id == session_id:
                try:
                    stream_queue.put_nowait(event)
                except asyncio.QueueFull:
                    pass

        # Register listener
        event_bus.subscribe_all(listener)

        # Also track for session completion or timeout
        max_wait = 600  # 10 min
        waited = 0
        poll_interval = 2  # 2 seconds polling check

        try:
            while waited < max_wait:
                try:
                    # Try to get next event within poll_interval
                    event = await asyncio.wait_for(stream_queue.get(), timeout=poll_interval)
                    if event is sentinel:
                        break

                    event_type_str = (
                        event.event_type
                        if isinstance(event.event_type, str)
                        else event.event_type.value
                    )
                    yield (
                        f"event: {event_type_str}\n"
                        f"data: {json.dumps({'timestamp': event.timestamp, 'payload': event.payload})}\n\n"
                    )
                except TimeoutError:
                    # Check session status
                    s = session_manager.get_session(session_id)
                    if s and s.status in {
                        SessionStatus.COMPLETED,
                        SessionStatus.FAILED,
                        SessionStatus.CANCELLED,
                    }:
                        yield (
                            f"event: session.ended\n"
                            f"data: {json.dumps({'status': s.status.value, 'error': s.error_message or ''})}\n\n"
                        )
                        break
                    # Heartbeat
                    current_status = s.status.value if s else "unknown"
                    yield (f"event: ping\ndata: {json.dumps({'status': current_status})}\n\n")

                waited += poll_interval

            yield 'event: stream_end\ndata: {"message": "Stream closed"}\n\n'

        except asyncio.CancelledError:
            logger.info("sse_stream_cancelled", session_id=session_id)
            raise
        except Exception as e:
            logger.exception("sse_stream_error", session_id=session_id, error=str(e))
            yield (f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "X-Accel-Buffering": "no",
        },
    )


# ---------- Experience Store APIs ----------


@router.get("/experiences")
def list_experiences(error_message: str | None = None, top_k: int = 5):
    """List experiences, optionally searching by error message similarity."""
    if error_message:
        exps = experience_store.search_similar(error_message, top_k=top_k)
    else:
        exps = experience_store._experiences

    return {
        "success": True,
        "count": len(exps),
        "data": [
            {
                "id": e.id,
                "error_type": e.error_type,
                "error_message": e.error_message,
                "context": e.context,
                "solution": e.final_solution,
                "success": e.success,
                "occurrences": e.occurrence_count,
                "status": e.status,
                "rating": e.user_rating,
                "created_at": e.created_at,
            }
            for e in exps
        ],
    }


@router.post("/experiences")
async def create_experience(request: Request):
    """Record a new experience."""
    body = await request.json()
    exp_id = experience_store.add_experience(
        error_message=body.get("error_message", ""),
        error_type=body.get("error_type", "Unknown"),
        context=body.get("context", {}),
        final_solution=body.get("solution", ""),
        success=body.get("success", True),
    )
    return {"success": True, "exp_id": exp_id}


@router.post("/experiences/{exp_id}/rate")
async def rate_experience(exp_id: str, request: Request):
    """Rate an experience (1-5)."""
    body = await request.json()
    rating = body.get("rating", 3)
    success = experience_store.mark_rating(exp_id, int(rating))
    return {"success": success, "exp_id": exp_id, "rating": rating}


@router.get("/experiences/stats")
def experience_stats():
    """Get experience store statistics."""
    return {"success": True, "data": experience_store.count()}


# ---------- Workflow Selection APIs ----------


@router.get("/workflows")
def list_workflows():
    """List all available workflow names."""
    from app.orchestration.workflows import list_workflow_names

    return {"success": True, "workflows": list_workflow_names()}


@router.post("/workflows/select")
async def select_workflow(request: Request):
    """Dynamically select a workflow based on requirement/project state."""
    body = await request.json()
    requirement = body.get("requirement", "")
    project_id = body.get("project_id")

    analysis = workflow_selector.analyzer.analyze(project_id, requirement)
    workflow = workflow_selector.select(project_id, requirement)

    return {
        "success": True,
        "analysis": {
            "state": analysis.state.value,
            "has_code": analysis.has_code,
            "has_git": analysis.has_git,
            "has_database": analysis.has_database,
            "file_count": analysis.file_count,
            "confidence": analysis.confidence,
            "recommendation": analysis.recommendation,
        },
        "workflow": {
            "name": workflow.name,
            "description": workflow.description,
            "steps": [
                s.agent_role.value if hasattr(s.agent_role, "value") else str(s.agent_role)
                for s in workflow.steps
            ],
        },
    }


# ---------- Project / Git APIs ----------


@router.post("/projects")
async def create_project(request: Request):
    """Create a new project (Git repository)."""
    body = await request.json()
    project_id = body.get("project_id") or body.get("id") or f"proj-{uuid4().hex[:8]}"
    name = body.get("name", project_id)

    project_path = project_store.create_project(project_id, name)
    return {
        "success": True,
        "data": {
            "id": project_id,
            "name": name,
            "path": str(project_path),
        },
    }


@router.get("/projects/{project_id}/commits")
def get_project_commits(project_id: str, limit: int = 20):
    """Get commit history for a project (used for version history UI)."""
    commits = project_store.get_commit_history(project_id, limit=limit)
    return {"success": True, "data": commits, "count": len(commits)}


@router.get("/projects/{project_id}/files")
def list_project_files(project_id: str, directory: str = ""):
    """List files in a project directory."""
    files = project_store.list_files(project_id, directory=directory)
    return {"success": True, "data": files, "count": len(files)}


@router.get("/projects/{project_id}/files/{file_path:path}")
def read_project_file(project_id: str, file_path: str):
    """Read a file from a project."""
    content = project_store.read_file(project_id, file_path)
    if content is None:
        raise HTTPException(status_code=404, detail="File not found")
    return {"success": True, "data": {"path": file_path, "content": content}}


@router.post("/projects/{project_id}/rollback")
async def rollback_project(project_id: str, request: Request):
    """Rollback a project to a specific commit hash."""
    body = await request.json()
    commit_hash = body.get("commit_hash")
    if not commit_hash:
        raise HTTPException(status_code=400, detail="commit_hash is required")
    ok = project_store.rollback(project_id, commit_hash)
    return {"success": ok}


# ---------- Info APIs ----------


@router.get("/agents")
def list_agents():
    """List all available agent roles.

    注意: 这是旧的 7-role legacy 端点,仅供向后兼容。
    新的 100 位专家库请用 GET /api/v1/experts。
    """
    # 返回完整 100 位专家,与 /experts 一致,避免用户误以为只有 7 个
    try:
        from app.orchestration.agent_team import list_agents as _list_experts
        items = _list_experts()
        return {"success": True, "roles": list_available_roles(), "agents": items, "total": len(items)}
    except Exception:
        return {"success": True, "roles": list_available_roles()}


@router.get("/projects")
def list_projects():
    """List all projects in the project store."""
    projects = project_store.list_projects()
    return {"success": True, "data": projects}


# ---------- Internal Helpers ----------


async def _execute_workflow(
    session_id: str,
    requirement: str,
    workflow_name: str | None,
):
    """Execute workflow in background (for async non-blocking response)."""
    try:
        await session_manager.update_status(session_id, SessionStatus.RUNNING)

        # Select workflow (dynamic selection or explicit)
        if workflow_name:
            from app.orchestration.workflows import get_workflow

            workflow = get_workflow(workflow_name)
        else:
            workflow = workflow_selector.select(session_id, requirement)

        if workflow is None:
            from app.orchestration.workflows import get_default_workflow

            workflow = get_default_workflow()

        logger.info(
            "workflow_selected",
            session_id=session_id,
            workflow=workflow.name,
        )

        # Publish start event
        await event_bus.publish(
            Event(
                event_type=EventType.SESSION_STARTED.value,
                session_id=session_id,
                payload={
                    "workflow": workflow.name,
                    "steps": [
                        s.agent_role.value if hasattr(s.agent_role, "value") else str(s.agent_role)
                        for s in workflow.steps
                    ],
                },
            )
        )

        # Run the engine with project git repo config so agents can commit artifacts
        engine = get_engine()
        from app.core.config import settings

        projects_root = settings.projects_root
        project_id = session_id
        result = await engine.run(
            session_id,
            requirement,
            workflow,
            projects_root=projects_root,
            project_id=project_id,
        )

        logger.info(
            "workflow_execution_complete",
            session_id=session_id,
            success=result,
        )

    except Exception as e:
        logger.exception("workflow_execution_error", session_id=session_id, error=str(e))
        await session_manager.set_error(session_id, str(e))
