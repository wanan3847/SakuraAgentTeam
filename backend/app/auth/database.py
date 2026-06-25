"""Async database engine, session factory and table initialisation.

``init_db()`` is meant to be called once at application startup (from
``main.py``). All three modules share the same ``Base``/``engine``/``async_session``
defined here.

Startup also creates a default admin account from the
``ADMIN_USERNAME`` / ``ADMIN_PASSWORD`` / ``ADMIN_EMAIL`` environment
variables (with sensible defaults) if it does not already exist.
"""

import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.auth.models import Base, User
from app.core.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    """Create all tables registered on ``Base.metadata`` and seed the admin.

    Note: every module's models must be imported before this is called so
    their tables are present on the metadata. Importing the routers from
    ``main.py`` is sufficient.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # 创建预置管理员
    await _create_default_admin()


async def _create_default_admin() -> None:
    """Ensure a default admin account exists.

    Reads credentials from environment variables:
      - ADMIN_USERNAME (default: admin)
      - ADMIN_PASSWORD (default: sakura2026)
      - ADMIN_EMAIL    (default: admin@sakura.local)

    If a user with the given username already exists, this is a no-op.
    """
    from passlib.context import CryptContext

    admin_username = os.environ.get("ADMIN_USERNAME", "admin")
    admin_password = os.environ.get("ADMIN_PASSWORD", "sakura2026")
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@sakura.local")

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    async with async_session() as session:
        result = await session.execute(select(User).where(User.username == admin_username))
        if result.scalar_one_or_none():
            return

        user = User(
            username=admin_username,
            email=admin_email,
            password_hash=pwd_context.hash(admin_password),
            role="admin",
            avatar="🌸",
        )
        session.add(user)
        await session.commit()
