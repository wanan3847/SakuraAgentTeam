"""Conversation history model.

Reuses ``Base`` from :mod:`app.auth.database` so all tables live on the
same metadata.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.auth.database import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    team_id = Column(String(100), nullable=False)
    team_name = Column(String(100), nullable=False)
    team_icon = Column(String(10), default="🌸")
    title = Column(String(200), default="")  # 自动取第一条消息前 20 字
    messages = Column(Text, nullable=False)  # JSON string
    agent_count = Column(Integer, default=0)
    message_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
