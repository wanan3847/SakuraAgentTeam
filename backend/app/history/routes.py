"""History API routes — list / get / save / update / delete conversations.

All endpoints require a valid Bearer token; users can only touch their own
records.
"""

import json

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import desc, func, select

from app.auth.database import async_session
from app.auth.dependency import get_current_user
from app.auth.models import User
from app.history.models import Conversation

router = APIRouter(prefix="/api/v1/history", tags=["history"])


def _conv_summary(c: Conversation) -> dict:
    return {
        "id": c.id,
        "user_id": c.user_id,
        "team_id": c.team_id,
        "team_name": c.team_name,
        "team_icon": c.team_icon,
        "title": c.title,
        "agent_count": c.agent_count,
        "message_count": c.message_count,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def _conv_detail(c: Conversation) -> dict:
    data = _conv_summary(c)
    try:
        data["messages"] = json.loads(c.messages) if c.messages else []
    except (json.JSONDecodeError, TypeError):
        data["messages"] = []
    return data


def _first_message_text(messages) -> str:
    """Extract the content of the first message for auto-titling."""
    if not isinstance(messages, list) or not messages:
        return ""
    first = messages[0]
    if isinstance(first, dict):
        return str(first.get("content", ""))
    return str(first)


@router.get("")
async def list_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
):
    """List the current user's conversations (summaries only, paginated)."""
    async with async_session() as session:
        total_result = await session.execute(
            select(func.count(Conversation.id)).where(Conversation.user_id == user.id)
        )
        total = total_result.scalar_one()

        result = await session.execute(
            select(Conversation)
            .where(Conversation.user_id == user.id)
            .order_by(desc(Conversation.updated_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = [_conv_summary(c) for c in result.scalars().all()]

        return {
            "success": True,
            "data": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }


@router.get("/{conv_id}")
async def get_history(conv_id: int, user: User = Depends(get_current_user)):
    """Get a single conversation with its full message list."""
    async with async_session() as session:
        result = await session.execute(
            select(Conversation).where(Conversation.id == conv_id)
        )
        conv = result.scalar_one_or_none()
        if conv is None or conv.user_id != user.id:
            return {"success": False, "error": "conversation not found"}
        return {"success": True, "data": _conv_detail(conv)}


@router.post("")
async def save_history(request: Request, user: User = Depends(get_current_user)):
    """Save a new conversation record."""
    body = await request.json()
    team_id = body.get("team_id")
    team_name = body.get("team_name")
    messages = body.get("messages") or []

    if not team_id or not team_name:
        return {"success": False, "error": "team_id and team_name are required"}

    title = body.get("title") or ""
    if not title:
        title = _first_message_text(messages)[:20]

    message_count = len(messages) if isinstance(messages, list) else 0

    async with async_session() as session:
        conv = Conversation(
            user_id=user.id,
            team_id=team_id,
            team_name=team_name,
            team_icon=body.get("team_icon", "🌸"),
            title=title,
            messages=json.dumps(messages, ensure_ascii=False),
            agent_count=body.get("agent_count", 0),
            message_count=message_count,
        )
        session.add(conv)
        await session.commit()
        await session.refresh(conv)
        return {"success": True, "data": _conv_detail(conv)}


@router.put("/{conv_id}")
async def update_history(conv_id: int, request: Request, user: User = Depends(get_current_user)):
    """Update a conversation (e.g. rename title or replace messages)."""
    body = await request.json()

    async with async_session() as session:
        result = await session.execute(
            select(Conversation).where(Conversation.id == conv_id)
        )
        conv = result.scalar_one_or_none()
        if conv is None or conv.user_id != user.id:
            return {"success": False, "error": "conversation not found"}

        if "title" in body:
            conv.title = body["title"]
        if "team_name" in body:
            conv.team_name = body["team_name"]
        if "team_icon" in body:
            conv.team_icon = body["team_icon"]
        if "agent_count" in body:
            conv.agent_count = body["agent_count"]
        if "messages" in body:
            messages = body["messages"] or []
            conv.messages = json.dumps(messages, ensure_ascii=False)
            conv.message_count = len(messages) if isinstance(messages, list) else 0

        await session.commit()
        await session.refresh(conv)
        return {"success": True, "data": _conv_detail(conv)}


@router.delete("/{conv_id}")
async def delete_history(conv_id: int, user: User = Depends(get_current_user)):
    """Delete a conversation owned by the current user."""
    async with async_session() as session:
        result = await session.execute(
            select(Conversation).where(Conversation.id == conv_id)
        )
        conv = result.scalar_one_or_none()
        if conv is None or conv.user_id != user.id:
            return {"success": False, "error": "conversation not found"}
        await session.delete(conv)
        await session.commit()
        return {"success": True, "id": conv_id}
