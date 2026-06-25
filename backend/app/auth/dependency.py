"""FastAPI dependencies for authentication and authorization.

Each dependency opens its own short-lived session from the shared
``async_session`` factory — there is no global request-scoped session.
"""

from fastapi import HTTPException, Request, status
from sqlalchemy import select

from app.auth.database import async_session
from app.auth.jwt_utils import verify_token
from app.auth.models import User


async def get_current_user(request: Request) -> User:
    """Resolve the current user from the ``Authorization: Bearer <token>`` header."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing or invalid authorization header",
        )
    token = auth_header[len("Bearer "):]
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired token",
        )

    user_id = payload.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid token payload",
        )

    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="user not found",
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="user is inactive",
            )
        return user


async def require_admin(request: Request) -> User:
    """Like :func:`get_current_user` but also requires the ``admin`` role."""
    user = await get_current_user(request)
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin privileges required",
        )
    return user
