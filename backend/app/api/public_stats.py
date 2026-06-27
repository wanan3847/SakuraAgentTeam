"""Public aggregate statistics for the home page."""

from datetime import datetime

from fastapi import APIRouter
from sqlalchemy import func, select

from app.agents import AGENT_REGISTRY
from app.auth.database import async_session
from app.auth.models import User
from app.history.models import Conversation
from app.llm_providers.registry import PROVIDERS
from app.submissions.models import AgentSubmission

router = APIRouter(prefix="/api/v1/public", tags=["public"])


def _percent(part: int, total: int) -> float:
    if total <= 0:
        return 0
    value = round((part / total) * 100, 1)
    return int(value) if value.is_integer() else value


def _quarter_start(now: datetime) -> datetime:
    month = ((now.month - 1) // 3) * 3 + 1
    return datetime(now.year, month, 1)


@router.get("/stats")
async def public_stats():
    """Return live public metrics backed by database and registries.

    The home page used to show seeded marketing numbers. This endpoint
    intentionally starts from real system data, so a fresh install returns
    small or zero values until users create conversations and submissions.
    """
    now = datetime.utcnow()
    quarter_start = _quarter_start(now)
    month_start = datetime(now.year, now.month, 1)

    async with async_session() as session:
        total_conversations_result = await session.execute(select(func.count(Conversation.id)))
        total_conversations = int(total_conversations_result.scalar() or 0)

        quarter_conversations_result = await session.execute(
            select(func.count(Conversation.id)).where(Conversation.created_at >= quarter_start)
        )
        quarter_conversations = int(quarter_conversations_result.scalar() or 0)

        total_messages_result = await session.execute(select(func.coalesce(func.sum(Conversation.message_count), 0)))
        total_messages = int(total_messages_result.scalar() or 0)

        users_result = await session.execute(select(func.count(User.id)).where(User.is_active == True))  # noqa: E712
        active_users = int(users_result.scalar() or 0)

        approved_submissions_result = await session.execute(
            select(func.count(AgentSubmission.id)).where(AgentSubmission.status == "approved")
        )
        approved_submissions = int(approved_submissions_result.scalar() or 0)

        month_submissions_result = await session.execute(
            select(func.count(AgentSubmission.id)).where(AgentSubmission.created_at >= month_start)
        )
        month_submissions = int(month_submissions_result.scalar() or 0)

    contributor_count = active_users + approved_submissions
    saved_hours = round(total_messages * 0.25, 1)
    saved_hours_value = int(saved_hours) if float(saved_hours).is_integer() else saved_hours

    return {
        "success": True,
        "data": [
            {
                "key": "completed_tasks",
                "value": total_conversations,
                "delta": _percent(quarter_conversations, total_conversations),
                "suffix": "",
                "label": "累计完成任务",
                "sub": "本季度",
            },
            {
                "key": "online_agents",
                "value": len(AGENT_REGISTRY),
                "delta": 0,
                "suffix": "",
                "label": "在线智能体",
                "sub": "可调用专家",
                "live": True,
            },
            {
                "key": "saved_hours",
                "value": saved_hours_value,
                "delta": _percent(quarter_conversations, total_conversations),
                "suffix": "",
                "label": "累计节省工时",
                "sub": "按消息量估算",
            },
            {
                "key": "contributors",
                "value": contributor_count,
                "delta": _percent(month_submissions, contributor_count),
                "suffix": "",
                "label": "社区贡献者",
                "sub": "用户+已通过投稿",
            },
            {
                "key": "llm_providers",
                "value": len(PROVIDERS),
                "delta": 0,
                "suffix": "",
                "label": "LLM 供应商",
                "sub": "后端注册表",
            },
        ],
    }
