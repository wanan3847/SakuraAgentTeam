"""协作数据落库 + 查询 — 把内存里的 CollaborationState 持久化到 DB。

用同步 sqlite3 直连同一个 SQLite 文件,避免 async session 的复杂性。
表结构定义在 models.py(注册在 Base.metadata 上,由 init_db 统一建表)。
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


def _db_path() -> str:
    """从 database_url 提取 SQLite 文件路径。"""
    url = settings.database_url
    # sqlite+aiosqlite:///./data/sakura.db -> ./data/sakura.db
    if ":///" in url:
        path = url.split(":///", 1)[1]
    elif "://" in url:
        path = url.split("://", 1)[1].lstrip("/")
    else:
        path = url
    # 确保目录存在
    d = os.path.dirname(path)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)
    return path


def _get_db() -> sqlite3.Connection:
    """获取同步 sqlite 连接。"""
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_tables(conn: sqlite3.Connection) -> None:
    """确保表存在(幂等)。"""
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS collaboration_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL UNIQUE,
        user_id INTEGER NOT NULL,
        user_request TEXT NOT NULL,
        mode TEXT NOT NULL DEFAULT 'graph',
        team_id TEXT NOT NULL DEFAULT '',
        team_name TEXT NOT NULL DEFAULT '',
        final_artifact_id TEXT,
        task_count INTEGER DEFAULT 0,
        artifact_count INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_collab_sessions_user ON collaboration_sessions(user_id);

    CREATE TABLE IF NOT EXISTS collaboration_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        task_id TEXT NOT NULL,
        name TEXT NOT NULL,
        description TEXT DEFAULT '',
        expected_output TEXT DEFAULT '',
        agent_id TEXT NOT NULL,
        agent_name TEXT DEFAULT '',
        dependencies TEXT DEFAULT '[]',
        state TEXT DEFAULT 'pending',
        error TEXT DEFAULT '',
        started_at REAL DEFAULT 0,
        finished_at REAL DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_collab_tasks_session ON collaboration_tasks(session_id);

    CREATE TABLE IF NOT EXISTS collaboration_artifacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        artifact_id TEXT NOT NULL,
        session_id TEXT NOT NULL,
        task_id TEXT NOT NULL,
        agent_id TEXT NOT NULL,
        agent_name TEXT DEFAULT '',
        type TEXT NOT NULL,
        title TEXT DEFAULT '',
        content TEXT DEFAULT '',
        summary TEXT DEFAULT '',
        is_final INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_collab_art_session ON collaboration_artifacts(session_id);
    CREATE INDEX IF NOT EXISTS idx_collab_art_id ON collaboration_artifacts(artifact_id);
    """)


def save_session(
    session_id: str,
    user_id: int,
    user_request: str,
    mode: str,
    team_id: str,
    team_name: str,
    task_count: int = 0,
    artifact_count: int = 0,
    final_artifact_id: str | None = None,
) -> None:
    """保存或更新协作会话。"""
    db = _get_db()
    try:
        _ensure_tables(db)
        existing = db.execute("SELECT id FROM collaboration_sessions WHERE session_id=?", (session_id,)).fetchone()
        if existing:
            db.execute(
                "UPDATE collaboration_sessions SET user_request=?, mode=?, team_id=?, team_name=?, "
                "task_count=?, artifact_count=?, final_artifact_id=?, updated_at=CURRENT_TIMESTAMP "
                "WHERE session_id=?",
                (user_request, mode, team_id, team_name, task_count, artifact_count,
                 final_artifact_id, session_id),
            )
        else:
            db.execute(
                "INSERT INTO collaboration_sessions (session_id, user_id, user_request, mode, "
                "team_id, team_name, task_count, artifact_count, final_artifact_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (session_id, user_id, user_request, mode, team_id, team_name,
                 task_count, artifact_count, final_artifact_id),
            )
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"save_session 失败: {e}")
    finally:
        db.close()


def save_task(
    session_id: str,
    task_id: str,
    name: str,
    description: str,
    expected_output: str,
    agent_id: str,
    agent_name: str,
    dependencies: list[str],
    state: str,
    error: str = "",
    started_at: float = 0,
    finished_at: float = 0,
) -> None:
    """保存任务节点。"""
    db = _get_db()
    try:
        _ensure_tables(db)
        existing = db.execute(
            "SELECT id FROM collaboration_tasks WHERE session_id=? AND task_id=?",
            (session_id, task_id),
        ).fetchone()
        deps_json = json.dumps(dependencies, ensure_ascii=False)
        if existing:
            db.execute(
                "UPDATE collaboration_tasks SET name=?, description=?, expected_output=?, "
                "agent_id=?, agent_name=?, dependencies=?, state=?, error=?, "
                "started_at=?, finished_at=? WHERE session_id=? AND task_id=?",
                (name, description, expected_output, agent_id, agent_name,
                 deps_json, state, error, started_at, finished_at, session_id, task_id),
            )
        else:
            db.execute(
                "INSERT INTO collaboration_tasks (session_id, task_id, name, description, "
                "expected_output, agent_id, agent_name, dependencies, state, error, "
                "started_at, finished_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (session_id, task_id, name, description, expected_output,
                 agent_id, agent_name, deps_json, state, error, started_at, finished_at),
            )
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"save_task 失败: {e}")
    finally:
        db.close()


def save_artifact(
    artifact_id: str,
    session_id: str,
    task_id: str,
    agent_id: str,
    agent_name: str,
    type: str,
    title: str,
    content: str,
    summary: str,
    is_final: bool = False,
) -> None:
    """保存产物。"""
    db = _get_db()
    try:
        _ensure_tables(db)
        existing = db.execute(
            "SELECT id FROM collaboration_artifacts WHERE artifact_id=?", (artifact_id,)
        ).fetchone()
        is_final_int = 1 if is_final else 0
        if existing:
            db.execute(
                "UPDATE collaboration_artifacts SET task_id=?, agent_id=?, agent_name=?, "
                "type=?, title=?, content=?, summary=?, is_final=? WHERE artifact_id=?",
                (task_id, agent_id, agent_name, type, title, content, summary,
                 is_final_int, artifact_id),
            )
        else:
            db.execute(
                "INSERT INTO collaboration_artifacts (artifact_id, session_id, task_id, "
                "agent_id, agent_name, type, title, content, summary, is_final) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (artifact_id, session_id, task_id, agent_id, agent_name,
                 type, title, content, summary, is_final_int),
            )
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"save_artifact 失败: {e}")
    finally:
        db.close()


def get_session_with_details(session_id: str) -> dict[str, Any] | None:
    """获取会话完整详情(含 tasks + artifacts)。"""
    db = _get_db()
    try:
        _ensure_tables(db)
        session = db.execute(
            "SELECT * FROM collaboration_sessions WHERE session_id=?", (session_id,)
        ).fetchone()
        if not session:
            return None

        tasks = db.execute(
            "SELECT * FROM collaboration_tasks WHERE session_id=? ORDER BY id", (session_id,)
        ).fetchall()
        artifacts = db.execute(
            "SELECT * FROM collaboration_artifacts WHERE session_id=? ORDER BY id", (session_id,)
        ).fetchall()

        return {
            "session_id": session["session_id"],
            "user_id": session["user_id"],
            "user_request": session["user_request"],
            "mode": session["mode"],
            "team_id": session["team_id"],
            "team_name": session["team_name"],
            "final_artifact_id": session["final_artifact_id"],
            "task_count": session["task_count"],
            "artifact_count": session["artifact_count"],
            "created_at": str(session["created_at"]) if session["created_at"] else "",
            "updated_at": str(session["updated_at"]) if session["updated_at"] else "",
            "tasks": [
                {
                    "task_id": t["task_id"],
                    "name": t["name"],
                    "description": t["description"],
                    "expected_output": t["expected_output"],
                    "agent_id": t["agent_id"],
                    "agent_name": t["agent_name"],
                    "dependencies": json.loads(t["dependencies"]) if t["dependencies"] else [],
                    "state": t["state"],
                    "error": t["error"],
                    "started_at": t["started_at"],
                    "finished_at": t["finished_at"],
                }
                for t in tasks
            ],
            "artifacts": [
                {
                    "artifact_id": a["artifact_id"],
                    "session_id": a["session_id"],
                    "task_id": a["task_id"],
                    "agent_id": a["agent_id"],
                    "agent_name": a["agent_name"],
                    "type": a["type"],
                    "title": a["title"],
                    "content": a["content"],
                    "summary": a["summary"],
                    "is_final": bool(a["is_final"]),
                    "created_at": str(a["created_at"]) if a["created_at"] else "",
                }
                for a in artifacts
            ],
        }
    except Exception as e:
        logger.warning(f"get_session_with_details 失败: {e}")
        return None
    finally:
        db.close()


def list_user_sessions(user_id: int, limit: int = 50) -> list[dict[str, Any]]:
    """列出用户的所有协作会话。"""
    db = _get_db()
    try:
        _ensure_tables(db)
        sessions = db.execute(
            "SELECT * FROM collaboration_sessions WHERE user_id=? "
            "ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [
            {
                "session_id": s["session_id"],
                "user_request": (s["user_request"] or "")[:100],
                "mode": s["mode"],
                "team_name": s["team_name"],
                "task_count": s["task_count"],
                "artifact_count": s["artifact_count"],
                "has_final": bool(s["final_artifact_id"]),
                "created_at": str(s["created_at"]) if s["created_at"] else "",
            }
            for s in sessions
        ]
    except Exception as e:
        logger.warning(f"list_user_sessions 失败: {e}")
        return []
    finally:
        db.close()


def delete_session(session_id: str) -> bool:
    """删除会话及其所有 tasks 和 artifacts。"""
    db = _get_db()
    try:
        _ensure_tables(db)
        db.execute("DELETE FROM collaboration_tasks WHERE session_id=?", (session_id,))
        db.execute("DELETE FROM collaboration_artifacts WHERE session_id=?", (session_id,))
        cursor = db.execute("DELETE FROM collaboration_sessions WHERE session_id=?", (session_id,))
        db.commit()
        return cursor.rowcount > 0
    except Exception as e:
        db.rollback()
        logger.warning(f"delete_session 失败: {e}")
        return False
    finally:
        db.close()
