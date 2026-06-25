"""JWT helpers for issuing and verifying access tokens."""

import os
from datetime import datetime, timedelta, timezone

import jwt

SECRET_KEY = os.environ.get("JWT_SECRET", "sakura-agent-team-secret-2026")
ALGORITHM = "HS256"
EXPIRE_DAYS = 7


def create_access_token(user_id: int, username: str, role: str) -> str:
    """Issue a JWT valid for ``EXPIRE_DAYS`` days."""
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "iat": now,
        "exp": now + timedelta(days=EXPIRE_DAYS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> dict | None:
    """Return the decoded payload, or ``None`` if the token is invalid/expired."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
