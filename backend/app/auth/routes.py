"""Auth API routes — register / login / me / change-password / stats / avatar."""

import base64
import os
import time
from pathlib import Path

from fastapi import APIRouter, Depends, Request, UploadFile, File
from passlib.context import CryptContext
from sqlalchemy import func, or_, select

from app.auth.database import async_session
from app.auth.dependency import get_current_user
from app.auth.jwt_utils import create_access_token
from app.auth.models import User
from app.submissions.models import AgentSubmission

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 头像上传目录
AVATAR_DIR = Path("data/avatars")
AVATAR_DIR.mkdir(parents=True, exist_ok=True)
MAX_AVATAR_SIZE = 2 * 1024 * 1024  # 2MB
ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}


def _user_to_dict(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "avatar": user.avatar,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "is_active": user.is_active,
    }


@router.post("/register")
async def register(request: Request):
    """Register a new user. Always creates a regular ``user`` role.

    The admin account is provisioned at startup via the
    ``ADMIN_USERNAME`` / ``ADMIN_PASSWORD`` environment variables — see
    :func:`app.auth.database._create_default_admin`.
    """
    body = await request.json()
    username = (body.get("username") or "").strip()
    email = (body.get("email") or "").strip()
    password = body.get("password") or ""

    if not username or not email or not password:
        return {"success": False, "error": "username, email and password are required"}

    async with async_session() as session:
        existing = await session.execute(
            select(User).where(or_(User.username == username, User.email == email))
        )
        if existing.scalar_one_or_none() is not None:
            return {"success": False, "error": "username or email already exists"}

        # 普通注册用户始终是 user 角色；管理员通过环境变量预置。
        role = "user"

        user = User(
            username=username,
            email=email,
            password_hash=pwd_context.hash(password),
            role=role,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        token = create_access_token(user.id, user.username, user.role)
        return {"success": True, "token": token, "user": _user_to_dict(user)}


@router.post("/login")
async def login(request: Request):
    """Login with username or email + password."""
    body = await request.json()
    account = (body.get("username") or body.get("email") or "").strip()
    password = body.get("password") or ""

    if not account or not password:
        return {"success": False, "error": "username/email and password are required"}

    async with async_session() as session:
        result = await session.execute(
            select(User).where(or_(User.username == account, User.email == account))
        )
        user = result.scalar_one_or_none()
        if user is None or not pwd_context.verify(password, user.password_hash):
            return {"success": False, "error": "invalid credentials"}
        if not user.is_active:
            return {"success": False, "error": "user is inactive"}

        token = create_access_token(user.id, user.username, user.role)
        return {"success": True, "token": token, "user": _user_to_dict(user)}


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    """Return the profile of the current user."""
    return {"success": True, "user": _user_to_dict(user)}


@router.put("/me")
async def update_me(request: Request, user: User = Depends(get_current_user)):
    """Update the current user's profile (avatar / username / email)."""
    body = await request.json()

    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == user.id))
        db_user = result.scalar_one_or_none()
        if db_user is None:
            return {"success": False, "error": "user not found"}

        if "avatar" in body and body["avatar"]:
            db_user.avatar = body["avatar"]

        if "username" in body:
            new_username = (body["username"] or "").strip()
            if new_username and new_username != db_user.username:
                clash = await session.execute(
                    select(User).where(User.username == new_username)
                )
                if clash.scalar_one_or_none() is not None:
                    return {"success": False, "error": "username already exists"}
                db_user.username = new_username

        if "email" in body:
            new_email = (body["email"] or "").strip()
            if new_email and new_email != db_user.email:
                clash = await session.execute(
                    select(User).where(User.email == new_email)
                )
                if clash.scalar_one_or_none() is not None:
                    return {"success": False, "error": "email already exists"}
                db_user.email = new_email

        await session.commit()
        await session.refresh(db_user)
        return {"success": True, "user": _user_to_dict(db_user)}


@router.post("/change-password")
async def change_password(request: Request, user: User = Depends(get_current_user)):
    """修改当前用户密码（需要登录）。

    请求体需包含 ``current_password`` 与 ``new_password``。
    """
    body = await request.json()
    current_password = body.get("current_password") or ""
    new_password = body.get("new_password") or ""

    if not current_password or not new_password:
        return {
            "success": False,
            "error": "current_password and new_password are required",
        }
    if len(new_password) < 6:
        return {"success": False, "error": "new_password must be at least 6 characters"}

    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == user.id))
        db_user = result.scalar_one_or_none()
        if db_user is None:
            return {"success": False, "error": "user not found"}

        if not pwd_context.verify(current_password, db_user.password_hash):
            return {"success": False, "error": "current password is incorrect"}

        db_user.password_hash = pwd_context.hash(new_password)
        await session.commit()
        return {"success": True}


@router.get("/stats")
async def user_stats(user: User = Depends(get_current_user)):
    """用户统计（对话数、提交数等，需要登录）。

    目前聚合该用户的 agent 提交计数；后续可扩展更多维度。
    """
    async with async_session() as session:
        result = await session.execute(
            select(AgentSubmission.status, func.count(AgentSubmission.id))
            .where(AgentSubmission.user_id == user.id)
            .group_by(AgentSubmission.status)
        )
        counts = {row[0]: row[1] for row in result.all()}
        total_submissions = sum(counts.values())

        return {
            "success": True,
            "data": {
                "user_id": user.id,
                "username": user.username,
                "role": user.role,
                "submissions": {
                    "total": total_submissions,
                    "pending": counts.get("pending", 0),
                    "approved": counts.get("approved", 0),
                    "rejected": counts.get("rejected", 0),
                },
            },
        }


@router.post("/me/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    """上传用户头像图片。

    接收 multipart/form-data,字段名 ``file``。
    限制:2MB,PNG/JPEG/WebP/GIF。
    存储:data/avatars/{user_id}_{timestamp}.{ext}
    返回:data: URL,前端直接 <img src> 显示。
    """
    # 校验文件类型
    content_type = file.content_type or ""
    if content_type not in ALLOWED_IMAGE_TYPES:
        return {
            "success": False,
            "error": f"unsupported image type: {content_type}. allowed: {', '.join(sorted(ALLOWED_IMAGE_TYPES))}",
        }

    # 读内容 + 校验大小
    raw = await file.read()
    if len(raw) > MAX_AVATAR_SIZE:
        return {
            "success": False,
            "error": f"avatar too large: {len(raw)} bytes (max {MAX_AVATAR_SIZE} bytes = 2MB)",
        }

    # 生成文件名 user_id_timestamp.ext
    ext_map = {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/webp": "webp",
        "image/gif": "gif",
    }
    ext = ext_map.get(content_type, "png")
    filename = f"{user.id}_{int(time.time())}.{ext}"
    filepath = AVATAR_DIR / filename

    # 写入磁盘
    filepath.write_bytes(raw)

    # 生成 data: URL 存到数据库(前端直接用,不用走 /static)
    b64 = base64.b64encode(raw).decode("ascii")
    data_url = f"data:{content_type};base64,{b64}"

    # 更新数据库
    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == user.id))
        db_user = result.scalar_one_or_none()
        if db_user is None:
            return {"success": False, "error": "user not found"}
        db_user.avatar = data_url
        await session.commit()
        await session.refresh(db_user)

    return {
        "success": True,
        "avatar": data_url,
        "user": _user_to_dict(db_user),
        "message": f"头像已更新({len(raw)} bytes, {content_type})",
    }
