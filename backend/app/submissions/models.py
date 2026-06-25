"""Agent submission model — community-proposed agents awaiting review.

Reuses ``Base`` from :mod:`app.auth.database`.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.auth.database import Base


class AgentSubmission(Base):
    __tablename__ = "agent_submissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    username = Column(String(50), nullable=False)
    agent_id = Column(String(50), nullable=False)  # 提议的 agent id
    agent_name = Column(String(50), nullable=False)
    agent_role = Column(String(100), nullable=False)
    agent_avatar = Column(String(10), default="🌟")
    agent_color = Column(String(10), default="#ec4899")
    agent_category = Column(String(30), nullable=False)
    agent_tagline = Column(String(200), default="")
    agent_goal = Column(Text, default="")
    agent_backstory = Column(Text, default="")
    agent_skills = Column(Text, default="[]")  # JSON array
    status = Column(String(20), default="pending")  # pending / approved / rejected
    admin_notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    reviewed_at = Column(DateTime, nullable=True)
