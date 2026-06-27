"""协作数据持久化模型 — 3 张表保存 session / tasks / artifacts。

借鉴 LangGraph 的 checkpoint 机制,让协作成果可回看、可导出。
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from app.auth.database import Base


class CollaborationSession(Base):
    """协作会话 — 一次完整的多 agent 协作。"""
    __tablename__ = "collaboration_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False, unique=True, index=True)  # collab-xxxx
    user_id = Column(Integer, nullable=False, index=True)
    user_request = Column(Text, nullable=False)
    mode = Column(String(32), nullable=False, default="graph")
    team_id = Column(String(100), nullable=False, default="")
    team_name = Column(String(200), nullable=False, default="")
    final_artifact_id = Column(String(64), nullable=True)
    task_count = Column(Integer, default=0)
    artifact_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CollaborationTask(Base):
    """协作任务节点。"""
    __tablename__ = "collaboration_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False, index=True)
    task_id = Column(String(64), nullable=False)  # task-1, task-2...
    name = Column(String(200), nullable=False)
    description = Column(Text, default="")
    expected_output = Column(Text, default="")
    agent_id = Column(String(64), nullable=False)
    agent_name = Column(String(100), default="")
    dependencies = Column(Text, default="[]")  # JSON list
    state = Column(String(16), default="pending")  # pending/ready/running/done/failed/skipped
    error = Column(Text, default="")
    started_at = Column(Float, default=0)
    finished_at = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class CollaborationArtifact(Base):
    """协作产物。"""
    __tablename__ = "collaboration_artifacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    artifact_id = Column(String(64), nullable=False, index=True)  # art-xxxx
    session_id = Column(String(64), nullable=False, index=True)
    task_id = Column(String(64), nullable=False)
    agent_id = Column(String(64), nullable=False)
    agent_name = Column(String(100), default="")
    type = Column(String(32), nullable=False)  # requirements/design_spec/final_report...
    title = Column(String(200), default="")
    content = Column(Text, default="")
    summary = Column(Text, default="")
    is_final = Column(Integer, default=0)  # 0=普通产物, 1=最终交付
    created_at = Column(DateTime, default=datetime.utcnow)
