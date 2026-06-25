"""User model for the auth module.

All modules (auth, history, submissions) share the same ``Base`` declared
here so that ``Base.metadata.create_all`` can create every table at once.
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base for all modules."""

    pass


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(200), nullable=False)
    role = Column(String(20), default="user")  # user / admin
    # avatar 可以是颜色 hex (#C97B8A) 或 data: URL(上传的图片)或 emoji
    avatar = Column(Text, default="🌸")
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
