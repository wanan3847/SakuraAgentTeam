"""Submissions API routes — propose / list / review / stats for agents.

Regular users can submit and view their own submissions; admins can view
all submissions and approve/reject them.
"""

import json
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy import desc, func, select

from app.auth.database import async_session
from app.auth.dependency import get_current_user, require_admin
from app.auth.models import User
from app.submissions.models import AgentSubmission

router = APIRouter(prefix="/api/v1/submissions", tags=["submissions"])


def _sub_to_dict(s: AgentSubmission) -> dict:
    try:
        skills = json.loads(s.agent_skills) if s.agent_skills else []
    except (json.JSONDecodeError, TypeError):
        skills = []
    return {
        "id": s.id,
        "user_id": s.user_id,
        "username": s.username,
        "agent_id": s.agent_id,
        "agent_name": s.agent_name,
        "agent_role": s.agent_role,
        "agent_avatar": s.agent_avatar,
        "agent_color": s.agent_color,
        "agent_category": s.agent_category,
        "agent_tagline": s.agent_tagline,
        "agent_goal": s.agent_goal,
        "agent_backstory": s.agent_backstory,
        "agent_skills": skills,
        "status": s.status,
        "admin_notes": s.admin_notes,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "reviewed_at": s.reviewed_at.isoformat() if s.reviewed_at else None,
    }


@router.post("")
async def create_submission(request: Request, user: User = Depends(get_current_user)):
    """Submit a new agent proposal (requires login)."""
    body = await request.json()
    agent_id = (body.get("agent_id") or "").strip()
    agent_name = (body.get("agent_name") or "").strip()
    agent_role = (body.get("agent_role") or "").strip()
    agent_category = (body.get("agent_category") or "").strip()

    if not agent_id or not agent_name or not agent_role or not agent_category:
        return {
            "success": False,
            "error": "agent_id, agent_name, agent_role and agent_category are required",
        }

    skills = body.get("agent_skills") or []
    sub = AgentSubmission(
        user_id=user.id,
        username=user.username,
        agent_id=agent_id,
        agent_name=agent_name,
        agent_role=agent_role,
        agent_avatar=body.get("agent_avatar", "🌟"),
        agent_color=body.get("agent_color", "#ec4899"),
        agent_category=agent_category,
        agent_tagline=body.get("agent_tagline", ""),
        agent_goal=body.get("agent_goal", ""),
        agent_backstory=body.get("agent_backstory", ""),
        agent_skills=json.dumps(skills, ensure_ascii=False),
    )

    async with async_session() as session:
        session.add(sub)
        await session.commit()
        await session.refresh(sub)
        return {"success": True, "data": _sub_to_dict(sub)}


@router.get("")
async def list_my_submissions(user: User = Depends(get_current_user)):
    """List the current user's submissions (requires login)."""
    async with async_session() as session:
        result = await session.execute(
            select(AgentSubmission)
            .where(AgentSubmission.user_id == user.id)
            .order_by(desc(AgentSubmission.created_at))
        )
        items = [_sub_to_dict(s) for s in result.scalars().all()]
        return {"success": True, "data": items, "total": len(items)}


@router.get("/all")
async def list_all_submissions(user: User = Depends(require_admin)):
    """List every submission across all users (admin only)."""
    async with async_session() as session:
        result = await session.execute(
            select(AgentSubmission).order_by(desc(AgentSubmission.created_at))
        )
        items = [_sub_to_dict(s) for s in result.scalars().all()]
        return {"success": True, "data": items, "total": len(items)}


@router.get("/public")
async def list_public_submissions():
    """List all approved submissions — public, no login required."""
    async with async_session() as session:
        result = await session.execute(
            select(AgentSubmission)
            .where(AgentSubmission.status == "approved")
            .order_by(desc(AgentSubmission.created_at))
        )
        items = [_sub_to_dict(s) for s in result.scalars().all()]
        return {"success": True, "data": items, "total": len(items)}


@router.get("/stats")
async def submission_stats(user: User = Depends(get_current_user)):
    """Aggregate counts for the current user's submissions."""
    async with async_session() as session:
        result = await session.execute(
            select(AgentSubmission.status, func.count(AgentSubmission.id))
            .where(AgentSubmission.user_id == user.id)
            .group_by(AgentSubmission.status)
        )
        counts = {row[0]: row[1] for row in result.all()}
        total = sum(counts.values())
        return {
            "success": True,
            "data": {
                "total": total,
                "pending": counts.get("pending", 0),
                "approved": counts.get("approved", 0),
                "rejected": counts.get("rejected", 0),
            },
        }


@router.put("/{sub_id}/review")
async def review_submission(
    sub_id: int, request: Request, user: User = Depends(require_admin)
):
    """Approve or reject a submission (admin only)."""
    body = await request.json()
    new_status = (body.get("status") or "").strip()
    if new_status not in ("approved", "rejected"):
        return {"success": False, "error": "status must be approved or rejected"}

    admin_notes = body.get("admin_notes", "")

    async with async_session() as session:
        result = await session.execute(
            select(AgentSubmission).where(AgentSubmission.id == sub_id)
        )
        sub = result.scalar_one_or_none()
        if sub is None:
            return {"success": False, "error": "submission not found"}

        sub.status = new_status
        sub.admin_notes = admin_notes
        sub.reviewed_at = datetime.utcnow()
        await session.commit()
        await session.refresh(sub)
        return {"success": True, "data": _sub_to_dict(sub)}
