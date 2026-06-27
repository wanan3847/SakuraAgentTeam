"""Agent Team API — 团队协作平台的接口（v2 适配版）。

借鉴业界成熟框架：
- CrewAI: 4 件套 role/goal/backstory + ProcessType
- AG2: GroupChatManager 智能选择发言者
- Anthropic: Orchestrator-Workers 模式
- MetaGPT: 共享白板产物链
- OpenAI Swarm: Handoff 模式
- LangGraph: 任务状态机

路由：
- GET  /api/v1/experts              列出所有 agent（可按分类过滤）
- GET  /api/v1/experts/categories   列出所有分类
- GET  /api/v1/teams                列出所有预设团队
- POST /api/v1/teams                创建自定义团队
- POST /api/v1/teams/{id}/chat      团队协作（SSE 流式，用登录用户自己的 LLM key）
- POST /api/v1/teams/chat           临时团队协作（SSE 流式，用登录用户自己的 LLM key）
- POST /api/v1/teams/{id}/graph     状态图模式（LangGraph 风格）
- POST /api/v1/teams/{id}/handoff   Handoff 模式（Swarm 风格）
- POST /api/v1/whiteboard           读取共享白板
- POST /api/v1/export               导出对话
- GET  /api/v1/me/llm-config        获取当前用户正在使用的 LLM 配置（用于前端展示）
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.auth.dependency import get_current_user
from app.auth.models import User
from app.core.logging import get_logger
from app.foundation.llm.base import LLMProvider, Message, MessageRole
from app.orchestration.agent_team import (
    AGENTS,
    AGENT_MAP,
    CATEGORIES,
    CREWS,
    CREW_MAP,
    AgentDef,
    ChatEvent,
    CollaborationEngine,
    Crew,
    ProcessType,
    create_custom_team,
    get_engine_for_user_async,
    get_team,
    list_agents,
    list_teams,
)
from app.orchestration.collaboration_state import (
    COLLAB_SESSIONS,
    create_session,
    get_session,
)
from app.orchestration.graph_engine import GraphCollaborationEngine, get_graph_engine

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["agent-team"])


# ============================================================
# Agent
# ============================================================

@router.get("/experts")
def agents_list(category: str | None = None):
    """列出所有 agent，可按分类过滤。"""
    items = list_agents(category)
    return {"success": True, "agents": items, "total": len(items)}


@router.get("/experts/categories")
def agents_categories():
    """列出所有 agent 分类。"""
    return {"success": True, "categories": CATEGORIES}


# ============================================================
# Team
# ============================================================

@router.get("/teams")
def teams_list():
    """列出所有预设团队。"""
    teams = list_teams()
    return {"success": True, "teams": teams, "total": len(teams)}


@router.get("/teams/{team_id}")
def teams_get(team_id: str):
    """获取单个团队详情。"""
    team = get_team(team_id)
    if not team:
        return {"success": False, "error": f"team {team_id} not found"}
    return {"success": True, "team": _team_to_dict(team)}


@router.post("/teams")
async def teams_create(request: Request):
    """创建自定义团队（仅返回定义，不持久化）。"""
    body = await request.json()
    name = (body.get("name") or "").strip()
    member_ids = body.get("member_ids") or []
    mode = body.get("mode", "group")
    description = body.get("description", "")
    icon = body.get("icon", "🌟")
    color = body.get("color", "#ec4899")

    if not name:
        return {"success": False, "error": "name is required"}
    if not member_ids:
        return {"success": False, "error": "member_ids is required"}
    if mode not in ("group", "pipeline", "master", "consensus", "parallel", "handoff", "graph"):
        return {"success": False, "error": "mode must be one of group/pipeline/master/consensus/parallel/handoff/graph"}

    invalid = [mid for mid in member_ids if mid not in AGENT_MAP]
    if invalid:
        return {"success": False, "error": f"unknown agent ids: {invalid}"}

    team = create_custom_team(
        name=name, member_ids=member_ids, mode=mode,
        description=description, icon=icon, color=color,
    )
    return {"success": True, "team": _team_to_dict(team)}


# ============================================================
# Chat
# ============================================================

@router.post("/teams/{team_id}/chat")
async def team_chat(team_id: str, request: Request, user: User = Depends(get_current_user)):
    """让一个预设团队协作（SSE 流式）— 用登录用户自己的 LLM key/URL/model。"""
    team = get_team(team_id)
    if not team:
        return {"success": False, "error": f"team {team_id} not found"}
    return await _stream_chat(team, request, user)


@router.post("/teams/chat")
async def adhoc_team_chat(request: Request, user: User = Depends(get_current_user)):
    """临时团队协作（SSE 流式）— 用登录用户自己的 LLM key/URL/model。"""
    body = await request.json()
    name = body.get("name", "临时团队")
    member_ids = body.get("member_ids", [])
    mode = body.get("mode", "group")
    icon = body.get("icon", "🌟")
    color = body.get("color", "#ec4899")
    description = body.get("description", "")

    if not member_ids:
        return {"success": False, "error": "member_ids is required"}

    team = create_custom_team(
        name=name, member_ids=member_ids, mode=mode,
        description=description, icon=icon, color=color,
    )
    return await _stream_chat(team, request, user)


# ============================================================
# 状态图模式（LangGraph 风格）
# ============================================================

@router.post("/teams/{team_id}/graph")
async def team_graph(team_id: str, request: Request, user: User = Depends(get_current_user)):
    """状态图模式：把任务拆成 DAG 节点，按依赖关系执行（用登录用户自己的 LLM）。"""
    team = get_team(team_id)
    if not team:
        return {"success": False, "error": f"team {team_id} not found"}
    return await _stream_graph(team, request, user)


# ============================================================
# Handoff 模式（OpenAI Swarm 风格）
# ============================================================

@router.post("/teams/{team_id}/handoff")
async def team_handoff(team_id: str, request: Request, user: User = Depends(get_current_user)):
    """Handoff 模式：agent 之间能互相转交任务（用登录用户自己的 LLM）。"""
    team = get_team(team_id)
    if not team:
        return {"success": False, "error": f"team {team_id} not found"}
    return await _stream_handoff(team, request, user)


# ============================================================
# 共享白板（MetaGPT 风格）
# ============================================================

@router.get("/whiteboard/{session_id}")
def whiteboard_get(session_id: str):
    """读取某个 session 的共享白板。"""
    from app.orchestration.agent_team import whiteboard_get as _wb_get
    wb = _wb_get(session_id)
    return {"success": True, "session_id": session_id, "whiteboard": wb}


# ============================================================
# 协作状态(新)— Artifact / CollaborationState 查询接口
# ============================================================

@router.get("/collaboration/{session_id}/state")
def collaboration_get_state(session_id: str):
    """获取协作会话的完整状态(任务图 + 所有 artifact)。"""
    state = get_session(session_id)
    if not state:
        return {"success": False, "error": "session not found", "session_id": session_id}
    return {"success": True, "state": state.to_dict()}


@router.get("/collaboration/{session_id}/artifacts")
def collaboration_list_artifacts(session_id: str):
    """列出某个协作会话的所有 artifact。"""
    state = get_session(session_id)
    if not state:
        return {"success": False, "error": "session not found", "session_id": session_id}
    return {
        "success": True,
        "session_id": session_id,
        "artifacts": [a.to_dict() for a in state.artifacts],
        "total": len(state.artifacts),
    }


@router.get("/collaboration/{session_id}/artifacts/{artifact_id}")
def collaboration_get_artifact(session_id: str, artifact_id: str):
    """获取单个 artifact 详情。"""
    state = get_session(session_id)
    if not state:
        return {"success": False, "error": "session not found", "session_id": session_id}
    artifact = state.get_artifact(artifact_id)
    if not artifact:
        return {"success": False, "error": "artifact not found", "artifact_id": artifact_id}
    return {"success": True, "artifact": artifact.to_dict()}


@router.get("/collaboration/{session_id}/final")
def collaboration_get_final(session_id: str):
    """获取最终交付物。"""
    state = get_session(session_id)
    if not state:
        return {"success": False, "error": "session not found", "session_id": session_id}
    if not state.final_artifact_id:
        return {"success": False, "error": "final artifact not ready", "session_id": session_id}
    artifact = state.get_artifact(state.final_artifact_id)
    if not artifact:
        return {"success": False, "error": "final artifact missing", "session_id": session_id}
    return {"success": True, "artifact": artifact.to_dict()}


# ============================================================
# Export
# ============================================================

@router.post("/export")
async def export_chat(request: Request):
    """导出对话为 Markdown / JSON / 纯文本。"""
    body = await request.json()
    fmt = body.get("format", "markdown")
    messages = body.get("messages") or []
    title = body.get("title", "智汇协同 · 团队协作成果")
    team_name = body.get("team_name", "")

    if fmt == "json":
        return {
            "success": True,
            "content": json.dumps(messages, ensure_ascii=False, indent=2),
            "filename": "agent_team_chat.json",
        }

    if fmt == "text":
        lines = [title, "=" * 40, ""]
        if team_name:
            lines.append(f"团队：{team_name}")
            lines.append("")
        for m in messages:
            lines.append(f"【{m.get('name', m.get('role', '?'))}】")
            lines.append(m.get("content", ""))
            lines.append("")
        return {"success": True, "content": "\n".join(lines), "filename": "agent_team_chat.txt"}

    # markdown
    lines = [f"# {title}", ""]
    if team_name:
        lines.append(f"> 团队：{team_name}")
        lines.append("")
    for m in messages:
        avatar = m.get("avatar", "")
        name = m.get("name", m.get("role", "?"))
        lines.append(f"## {avatar} {name}")
        lines.append("")
        lines.append(m.get("content", ""))
        lines.append("")
    return {"success": True, "content": "\n".join(lines), "filename": "agent_team_chat.md"}


# ============================================================
# Helpers
# ============================================================

def _team_to_dict(team: Crew) -> dict:
    return {
        "id": team.id, "name": team.name, "description": team.description,
        "icon": team.icon, "color": team.color, "mode": team.mode,
        "process": team.process.value, "preset": team.preset, "tags": team.tags,
        "manager": team.manager_agent_id,
        "members": [
            {"id": m.id, "name": m.name, "avatar": m.avatar, "color": m.color,
             "role": m.role, "tagline": m.tagline, "category": m.category,
             "goal": m.goal, "backstory": m.backstory, "skills": m.skills,
             "allow_delegation": m.allow_delegation}
            for m in team.agents
        ],
    }


async def _stream_chat(team: Crew, request: Request, user: User):
    """通用 SSE 流式聊天（使用 mode 决定 process）— 用登录用户自己的 LLM。"""
    body = await request.json()
    message = (body.get("message") or "").strip()
    if not message:
        return {"success": False, "error": "message is required"}

    raw_history = body.get("history") or []
    history: list[dict] = []  # 简化为 dict
    for h in raw_history:
        history.append({
            "id": h.get("id", ""),
            "role": h.get("role", "user"),
            "name": h.get("name", ""),
            "content": h.get("content", ""),
            "avatar": h.get("avatar", ""),
            "color": h.get("color", "#6b7280"),
        })

    # 根据 mode 决定 process
    process_map = {
        "group": ProcessType.SEQUENTIAL,
        "pipeline": ProcessType.SEQUENTIAL,
        "master": ProcessType.HIERARCHICAL,
        "consensus": ProcessType.CONSENSUS,
        "parallel": ProcessType.PARALLEL,
    }
    if team.mode in process_map:
        actual_process = process_map[team.mode]
    else:
        actual_process = team.process

    # 用登录用户自己的 LLM
    engine = await get_engine_for_user_async(user.id)

    # 先发一个 llm 状态事件，让前端知道当前用的什么配置
    try:
        from app.llm_providers.async_helpers import get_user_default_config
        cfg = await get_user_default_config(user.id)
        if cfg:
            llm_info = {
                "source": "user",
                "display_name": cfg["display_name"],
                "provider_id": cfg["provider_id"],
                "model": cfg["model"],
                "base_url": cfg["base_url"],
                "has_key": cfg["has_api_key"],
            }
        else:
            llm_info = {"source": "shared_fallback", "reason": "no_user_config"}
    except Exception:
        llm_info = {"source": "shared_fallback", "reason": "lookup_failed"}

    async def event_stream():
        try:
            # 第一条事件告诉前端"用的是用户的 LLM"
            yield (
                f"event: llm_info\n"
                f"data: {json.dumps(llm_info, ensure_ascii=False)}\n\n"
            )
            async for evt in engine.run(team, message, history, process=actual_process):
                yield f"event: {evt.type}\ndata: {json.dumps(evt.data, ensure_ascii=False)}\n\n"
        except Exception as exc:
            logger.exception("chat_stream_error", error=str(exc), user_id=user.id)
            yield f"event: error\ndata: {json.dumps({'message': str(exc)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "X-Accel-Buffering": "no",
        },
    )


async def _stream_graph(team: Crew, request: Request, user: User):
    """状态图模式(LangGraph 风格)流式 — 用登录用户自己的 LLM。

    新版改用 GraphCollaborationEngine,产出 artifact / final_deliverable 等新事件。
    异常时 fallback 到老引擎。
    """
    body = await request.json()
    message = (body.get("message") or "").strip()
    if not message:
        return {"success": False, "error": "message is required"}

    tasks = body.get("tasks") or []
    manager_id = body.get("manager_id", team.manager_agent_id or team.agents[0].id)

    # 用登录用户的 LLM key 构建新引擎
    from app.orchestration.agent_team import build_llm_for_user
    user_llm = build_llm_for_user(user.id)
    graph_engine = get_graph_engine(llm=user_llm)

    async def event_stream():
        try:
            async for evt in graph_engine.run(
                crew=team,
                user_request=message,
                tasks=tasks if tasks else None,
                manager_id=manager_id,
            ):
                yield f"event: {evt.type}\ndata: {json.dumps(evt.data, ensure_ascii=False)}\n\n"
        except Exception as exc:
            logger.exception("graph_stream_error", error=str(exc), user_id=user.id)
            yield f"event: error\ndata: {json.dumps({'message': str(exc)}, ensure_ascii=False)}\n\n"
            # fallback 到老引擎
            try:
                engine = await get_engine_for_user_async(user.id)
                async for evt in engine.run_graph(team, message, tasks, manager_id):
                    yield f"event: {evt.type}\ndata: {json.dumps(evt.data, ensure_ascii=False)}\n\n"
            except Exception as fallback_exc:
                logger.exception("graph_fallback_error", error=str(fallback_exc))
                yield f"event: error\ndata: {json.dumps({'message': f'fallback 也失败: {fallback_exc}'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "X-Accel-Buffering": "no",
        },
    )


async def _stream_handoff(team: Crew, request: Request, user: User):
    """Handoff 模式（Swarm 风格）流式 — 用登录用户自己的 LLM。"""
    body = await request.json()
    message = (body.get("message") or "").strip()
    if not message:
        return {"success": False, "error": "message is required"}

    max_handoffs = int(body.get("max_handoffs", 5))
    starter_id = body.get("starter_id", team.agents[0].id)

    engine = await get_engine_for_user_async(user.id)

    async def event_stream():
        try:
            async for evt in engine.run_handoff(team, message, starter_id, max_handoffs):
                yield f"event: {evt.type}\ndata: {json.dumps(evt.data, ensure_ascii=False)}\n\n"
        except Exception as exc:
            logger.exception("handoff_stream_error", error=str(exc), user_id=user.id)
            yield f"event: error\ndata: {json.dumps({'message': str(exc)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "X-Accel-Buffering": "no",
        },
    )


# ============================================================
# 当前用户的 LLM 配置（前端展示用）
# ============================================================

@router.get("/me/llm-config")
async def get_my_llm_config(user: User = Depends(get_current_user)):
    """获取当前用户正在使用的 LLM 配置（用于前端展示 + 提示用户去设置）。"""
    try:
        from app.llm_providers.async_helpers import get_user_default_config
        cfg = await get_user_default_config(user.id)
        if cfg is None:
            return {
                "success": True,
                "data": {
                    "source": "shared_fallback",
                    "has_user_config": False,
                    "message": "未配置 LLM，使用开发者共享 Key。前往「供应商」页面添加你自己的 API Key。",
                },
            }
        return {
            "success": True,
            "data": {
                "source": "user",
                "has_user_config": True,
                "config": cfg,
            },
        }
    except Exception as exc:
        logger.error("get_my_llm_config_failed", user_id=user.id, error=str(exc))
        return {"success": False, "error": str(exc)}
