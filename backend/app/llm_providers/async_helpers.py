"""异步辅助：构建用户的 LLM provider。

与 :mod:`app.orchestration.agent_team` 中的同步 :func:`build_llm_for_user`
互为补充 — 这个模块专为异步上下文（FastAPI 路由）设计。

借鉴 hermes-agent 的 ProviderProfile 设计：
- 用户的 LLM 配置是私有的，每用户独立
- 默认配置（is_default=True）优先，否则用最新的激活配置
- 用户的每一次对话都走自己配的 key/URL/model
- 没有配置时退回到开发者共享 key
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


def _infer_provider_name(base_url: str, model: str) -> str:
    """根据 base_url 和 model 推断 provider 类型。

    支持 openai / anthropic / litellm 三种内置类型。
    """
    if "anthropic" in base_url.lower():
        return "anthropic"
    # LiteLLM 用 "provider/model" 格式
    if "/" in model:
        return "litellm"
    return "openai"


async def build_llm_for_user_async(user_id: int) -> Any:
    """异步为指定用户构建 LLM provider。

    Args:
        user_id: 用户 ID

    Returns:
        LLMProvider 实例（带 MeteredLLMProvider 包装）或 None
    """
    try:
        from app.auth.database import async_session
        from app.llm_providers.models import CustomProvider
        from app.foundation.llm import LLMProviderFactory
        from app.foundation.llm.meter import MeteredLLMProvider
        from sqlalchemy import desc, select

        async with async_session() as session:
            # 1. 优先：is_default=True 且 is_active=True
            result = await session.execute(
                select(CustomProvider)
                .where(
                    CustomProvider.user_id == user_id,
                    CustomProvider.is_default == True,  # noqa: E712
                    CustomProvider.is_active == True,  # noqa: E712
                )
                .order_by(desc(CustomProvider.updated_at))
                .limit(1)
            )
            cfg = result.scalar_one_or_none()

            # 2. 退回到最新激活配置
            if cfg is None:
                result = await session.execute(
                    select(CustomProvider)
                    .where(
                        CustomProvider.user_id == user_id,
                        CustomProvider.is_active == True,  # noqa: E712
                    )
                    .order_by(desc(CustomProvider.updated_at))
                    .limit(1)
                )
                cfg = result.scalar_one_or_none()

        if cfg is None:
            logger.info("no_user_llm_config", user_id=user_id, fallback="shared_key")
            return _build_shared_llm()

        base_url = cfg.base_url
        api_key = cfg.api_key
        model = cfg.model or "gpt-4o-mini"
        provider_name = _infer_provider_name(base_url, model)

        inner = LLMProviderFactory.create(
            provider=provider_name,
            model=model,
            api_key=api_key,
            base_url=base_url,
        )
        metered = MeteredLLMProvider(inner)
        logger.info(
            "user_llm_built_async",
            user_id=user_id,
            config_id=cfg.id,
            provider_id=cfg.provider_id,
            provider=provider_name,
            model=model,
            base_url=base_url,
            has_key=bool(api_key),
        )
        return metered
    except Exception as exc:
        logger.error("build_user_llm_async_failed", user_id=user_id, error=str(exc))
        return _build_shared_llm()


def _build_shared_llm() -> Any:
    """构建开发者共享 key 的 LLM（兜底用）。"""
    try:
        from app.agents import _build_llm_provider
        return _build_llm_provider()
    except Exception as exc:
        logger.error("shared_llm_build_failed", error=str(exc))
        return None


async def get_user_default_config(user_id: int) -> dict | None:
    """异步获取用户的默认 LLM 配置（不含 key 实际值）。

    Returns:
        dict: 包含 id, display_name, base_url, has_api_key, model, models, is_default
        None: 用户没有任何配置
    """
    try:
        import json as _json
        from app.auth.database import async_session
        from app.llm_providers.models import CustomProvider
        from sqlalchemy import desc, select

        async with async_session() as session:
            result = await session.execute(
                select(CustomProvider)
                .where(
                    CustomProvider.user_id == user_id,
                    CustomProvider.is_active == True,  # noqa: E712
                )
                .order_by(desc(CustomProvider.is_default), desc(CustomProvider.updated_at))
                .limit(1)
            )
            cfg = result.scalar_one_or_none()
            if cfg is None:
                return None
            try:
                models = _json.loads(cfg.models) if cfg.models else []
            except (ValueError, TypeError):
                models = []
            return {
                "id": cfg.id,
                "provider_id": cfg.provider_id,
                "display_name": cfg.display_name,
                "base_url": cfg.base_url,
                "has_api_key": bool(cfg.api_key),
                "model": cfg.model or "",
                "models": models,
                "is_default": cfg.is_default,
            }
    except Exception as exc:
        logger.error("get_user_default_config_failed", user_id=user_id, error=str(exc))
        return None
