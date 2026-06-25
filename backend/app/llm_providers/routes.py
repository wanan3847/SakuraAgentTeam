"""LLM Provider API routes — 内置厂商列表 + 用户自己的 LLM 配置。

借鉴 hermes-agent 的设计：
- 内置厂商：共享元数据（name/base_url/docs），不含 key
- 用户配置：私有 key + url + model，每个用户独立
- 两种模式：从内置厂商选 / 完全自定义
- 测试连接：用用户自己的 key 调 /models 或 /chat/completions
"""

import json
import os
from datetime import datetime
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Request
from sqlalchemy import desc, select, update

from app.auth.database import async_session
from app.auth.dependency import get_current_user
from app.auth.models import User
from app.llm_providers.models import CustomProvider
from app.llm_providers.registry import (
    PROVIDERS,
    get_free_providers,
    get_provider_by_id,
    provider_to_dict,
)

router = APIRouter(prefix="/api/v1/llm", tags=["llm_providers"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _custom_to_dict(c: CustomProvider, include_key: bool = False) -> dict:
    """把 CustomProvider 记录转为 dict。默认不返回 api_key 实际值。"""
    try:
        models = json.loads(c.models) if c.models else []
    except (json.JSONDecodeError, TypeError):
        models = []
    return {
        "id": c.id,
        "user_id": c.user_id,
        "provider_id": c.provider_id,
        "display_name": c.display_name,
        "base_url": c.base_url,
        "api_key": c.api_key if include_key else ("***" if c.api_key else ""),
        "has_api_key": bool(c.api_key),
        "model": c.model or "",
        "models": models,
        "is_active": c.is_active,
        "is_default": c.is_default,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


async def _fetch_models_from_endpoint(base_url: str, api_key: str) -> dict:
    """用用户自己的 key 调 /models 端点拉取模型列表。

    返回 {"success": bool, "models": [...], "error": str?}
    """
    url = base_url.rstrip("/")
    if not url.endswith("/models"):
        # 有些 base_url 已经带 /v1，有些没有
        if "/v1" in url or "/api" in url:
            url = url + "/models"
        else:
            url = url + "/v1/models"

    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                return {
                    "success": False,
                    "error": f"HTTP {resp.status_code}: {resp.text[:200]}",
                }
            data = resp.json()
            # OpenAI 格式: {"data": [{"id": "gpt-4o", ...}, ...]}
            if isinstance(data, dict) and "data" in data:
                models = [m.get("id", "") for m in data["data"] if m.get("id")]
            elif isinstance(data, list):
                models = [m.get("id", m.get("name", "")) for m in data if m]
            else:
                models = []
            return {"success": True, "models": sorted(models)}
    except httpx.ConnectError as e:
        return {"success": False, "error": f"连接失败: {e}"}
    except httpx.TimeoutException:
        return {"success": False, "error": "请求超时（15 秒）"}
    except Exception as e:
        return {"success": False, "error": f"未知错误: {e}"}


async def _test_chat_completion(base_url: str, api_key: str, model: str) -> dict:
    """用用户自己的 key 发一个最小请求测试连接。

    返回 {"success": bool, "reply": str, "error": str?}
    """
    url = base_url.rstrip("/")
    if not (url.endswith("/chat/completions") or url.endswith("/v1/chat/completions")):
        if "/v1" in url:
            url = url + "/chat/completions"
        else:
            url = url + "/v1/chat/completions"

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    body = {
        "model": model,
        "messages": [{"role": "user", "content": "说'你好'两个字"}],
        "max_tokens": 10,
        "stream": False,
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=body, headers=headers)
            if resp.status_code != 200:
                return {
                    "success": False,
                    "error": f"HTTP {resp.status_code}: {resp.text[:300]}",
                }
            data = resp.json()
            choices = data.get("choices", [])
            if choices:
                reply = choices[0].get("message", {}).get("content", "")
            else:
                reply = ""
            return {"success": True, "reply": reply}
    except httpx.ConnectError as e:
        return {"success": False, "error": f"连接失败: {e}"}
    except httpx.TimeoutException:
        return {"success": False, "error": "请求超时（30 秒）"}
    except Exception as e:
        return {"success": False, "error": f"未知错误: {e}"}


# ---------------------------------------------------------------------------
# Built-in providers — 内置厂商元数据（不含 key）
# ---------------------------------------------------------------------------

@router.get("/providers")
async def list_providers():
    """列出所有内置厂商（只返回元数据，不含 key）。"""
    return {
        "success": True,
        "data": [provider_to_dict(p) for p in PROVIDERS],
        "total": len(PROVIDERS),
    }


@router.get("/providers/free")
async def list_free_providers():
    """只列出有免费额度的厂商。"""
    free = get_free_providers()
    return {
        "success": True,
        "data": [provider_to_dict(p) for p in free],
        "total": len(free),
    }


@router.get("/providers/{provider_id}")
async def get_provider(provider_id: str):
    """获取单个内置厂商详情。"""
    p = get_provider_by_id(provider_id)
    if p is None:
        return {"success": False, "error": "provider not found"}
    return {"success": True, "data": provider_to_dict(p)}


# ---------------------------------------------------------------------------
# 用户自己的 LLM 配置（CRUD）— 需要登录
# ---------------------------------------------------------------------------

@router.get("/configs")
async def list_my_configs(user: User = Depends(get_current_user)):
    """列出当前用户的所有 LLM 配置。"""
    async with async_session() as session:
        result = await session.execute(
            select(CustomProvider)
            .where(CustomProvider.user_id == user.id)
            .order_by(desc(CustomProvider.is_default), desc(CustomProvider.created_at))
        )
        items = [_custom_to_dict(c) for c in result.scalars().all()]
        return {"success": True, "data": items, "total": len(items)}


@router.post("/configs")
async def create_config(request: Request, user: User = Depends(get_current_user)):
    """保存一条新的 LLM 配置（用户自己的 key + url + model）。

    两种模式：
    1. 从内置厂商选：传 provider_id（如 deepseek），自动填充 base_url
    2. 完全自定义：provider_id 传 "custom"，必须传 base_url
    """
    body = await request.json()
    provider_id = (body.get("provider_id") or "custom").strip()
    display_name = (body.get("display_name") or "").strip()
    base_url = (body.get("base_url") or "").strip()
    api_key = body.get("api_key") or ""
    model = (body.get("model") or "").strip()
    models = body.get("models") or []
    is_default = bool(body.get("is_default", False))

    # 如果选了内置厂商，自动填充 base_url
    if provider_id != "custom":
        builtin = get_provider_by_id(provider_id)
        if builtin is None:
            return {"success": False, "error": f"未知的内置厂商: {provider_id}"}
        if not base_url:
            base_url = builtin.base_url
        if not display_name:
            display_name = builtin.name
        if not models and builtin.models:
            models = builtin.models
        if not model and builtin.models:
            model = builtin.models[0]
    else:
        # 完全自定义必须提供 base_url
        if not base_url:
            return {"success": False, "error": "base_url 是必填项"}
        if not display_name:
            display_name = "自定义端点"

    if not model:
        return {"success": False, "error": "model 是必填项（可先调 /fetch-models 拉取可用模型）"}

    async with async_session() as session:
        # 如果设为默认，先取消其他默认
        if is_default:
            await session.execute(
                update(CustomProvider)
                .where(CustomProvider.user_id == user.id)
                .values(is_default=False)
            )

        custom = CustomProvider(
            user_id=user.id,
            provider_id=provider_id,
            display_name=display_name,
            base_url=base_url,
            api_key=api_key,
            model=model,
            models=json.dumps(models, ensure_ascii=False),
            is_active=True,
            is_default=is_default,
        )
        session.add(custom)
        await session.commit()
        await session.refresh(custom)
        return {"success": True, "data": _custom_to_dict(custom)}


@router.put("/configs/{config_id}")
async def update_config(
    config_id: int, request: Request, user: User = Depends(get_current_user)
):
    """更新一条 LLM 配置。"""
    body = await request.json()

    async with async_session() as session:
        result = await session.execute(
            select(CustomProvider).where(
                CustomProvider.id == config_id,
                CustomProvider.user_id == user.id,
            )
        )
        custom = result.scalar_one_or_none()
        if custom is None:
            return {"success": False, "error": "配置不存在"}

        if "display_name" in body and body["display_name"]:
            custom.display_name = body["display_name"]
        if "base_url" in body and body["base_url"]:
            custom.base_url = body["base_url"]
        if "api_key" in body:
            custom.api_key = body["api_key"] or ""
        if "model" in body and body["model"]:
            custom.model = body["model"]
        if "models" in body and isinstance(body["models"], list):
            custom.models = json.dumps(body["models"], ensure_ascii=False)
        if "is_active" in body:
            custom.is_active = bool(body["is_active"])
        if "is_default" in body:
            new_default = bool(body["is_default"])
            if new_default:
                # 先取消其他默认
                await session.execute(
                    update(CustomProvider)
                    .where(CustomProvider.user_id == user.id)
                    .values(is_default=False)
                )
            custom.is_default = new_default

        custom.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(custom)
        return {"success": True, "data": _custom_to_dict(custom)}


@router.delete("/configs/{config_id}")
async def delete_config(config_id: int, user: User = Depends(get_current_user)):
    """删除一条 LLM 配置。"""
    async with async_session() as session:
        result = await session.execute(
            select(CustomProvider).where(
                CustomProvider.id == config_id,
                CustomProvider.user_id == user.id,
            )
        )
        custom = result.scalar_one_or_none()
        if custom is None:
            return {"success": False, "error": "配置不存在"}

        await session.delete(custom)
        await session.commit()
        return {"success": True}


# ---------------------------------------------------------------------------
# 测试连接 + 拉取模型 — 用用户自己的 key
# ---------------------------------------------------------------------------

@router.post("/fetch-models")
async def fetch_models(request: Request):
    """用给定的 base_url + api_key 拉取可用模型列表。

    不需要登录（key 只在请求体里传，不保存）。
    请求体: {"base_url": "...", "api_key": "..."}
    """
    body = await request.json()
    base_url = (body.get("base_url") or "").strip()
    api_key = body.get("api_key") or ""

    if not base_url:
        return {"success": False, "error": "base_url 是必填项"}

    result = await _fetch_models_from_endpoint(base_url, api_key)
    return result


@router.post("/test-connection")
async def test_connection(request: Request):
    """用给定的 base_url + api_key + model 测试连接（发一个最小请求）。

    不需要登录。请求体: {"base_url": "...", "api_key": "...", "model": "..."}
    """
    body = await request.json()
    base_url = (body.get("base_url") or "").strip()
    api_key = body.get("api_key") or ""
    model = (body.get("model") or "").strip()

    if not base_url or not model:
        return {"success": False, "error": "base_url 和 model 是必填项"}

    result = await _test_chat_completion(base_url, api_key, model)
    return result


@router.post("/configs/{config_id}/test")
async def test_my_config(config_id: int, user: User = Depends(get_current_user)):
    """测试已保存的某条配置的连接。"""
    async with async_session() as session:
        result = await session.execute(
            select(CustomProvider).where(
                CustomProvider.id == config_id,
                CustomProvider.user_id == user.id,
            )
        )
        custom = result.scalar_one_or_none()
        if custom is None:
            return {"success": False, "error": "配置不存在"}

        if not custom.model:
            return {"success": False, "error": "该配置未设置默认 model"}
        if not custom.base_url:
            return {"success": False, "error": "该配置未设置 base_url"}

        result = await _test_chat_completion(custom.base_url, custom.api_key, custom.model)
        return result


@router.post("/configs/{config_id}/refresh-models")
async def refresh_my_models(config_id: int, user: User = Depends(get_current_user)):
    """用已保存的配置重新拉取模型列表并更新。"""
    async with async_session() as session:
        result = await session.execute(
            select(CustomProvider).where(
                CustomProvider.id == config_id,
                CustomProvider.user_id == user.id,
            )
        )
        custom = result.scalar_one_or_none()
        if custom is None:
            return {"success": False, "error": "配置不存在"}

        fetch = await _fetch_models_from_endpoint(custom.base_url, custom.api_key)
        if fetch["success"]:
            custom.models = json.dumps(fetch["models"], ensure_ascii=False)
            custom.updated_at = datetime.utcnow()
            await session.commit()
            await session.refresh(custom)
            return {"success": True, "models": fetch["models"], "data": _custom_to_dict(custom)}
        return fetch


# ---------------------------------------------------------------------------
# 兼容旧接口（custom providers）— 保持向后兼容
# ---------------------------------------------------------------------------

@router.get("/providers/custom")
async def list_custom_providers(user: User = Depends(get_current_user)):
    """[已废弃] 列出自定义供应商 — 请用 GET /configs。"""
    return await list_my_configs(user)


@router.post("/providers/custom")
async def create_custom_provider(request: Request, user: User = Depends(get_current_user)):
    """[已废弃] 添加自定义供应商 — 请用 POST /configs。"""
    return await create_config(request, user)


@router.put("/providers/custom/{provider_id}")
async def update_custom_provider(
    provider_id: str, request: Request, user: User = Depends(get_current_user)
):
    """[已废弃] 更新自定义供应商配置。"""
    body = await request.json()
    async with async_session() as session:
        result = await session.execute(
            select(CustomProvider).where(
                CustomProvider.user_id == user.id,
                CustomProvider.provider_id == provider_id,
            )
        )
        custom = result.scalar_one_or_none()
        if custom is None:
            return {"success": False, "error": "custom provider not found"}

        if body.get("provider_name"):
            custom.display_name = body["provider_name"]
        if body.get("base_url"):
            custom.base_url = body["base_url"]
        if "api_key" in body:
            custom.api_key = body["api_key"] or ""
        if body.get("models") and isinstance(body["models"], list):
            custom.models = json.dumps(body["models"], ensure_ascii=False)
        if "is_active" in body:
            custom.is_active = bool(body["is_active"])

        custom.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(custom)
        return {"success": True, "data": _custom_to_dict(custom)}


@router.delete("/providers/custom/{provider_id}")
async def delete_custom_provider(provider_id: str, user: User = Depends(get_current_user)):
    """[已废弃] 删除自定义供应商。"""
    async with async_session() as session:
        result = await session.execute(
            select(CustomProvider).where(
                CustomProvider.user_id == user.id,
                CustomProvider.provider_id == provider_id,
            )
        )
        custom = result.scalar_one_or_none()
        if custom is None:
            return {"success": False, "error": "custom provider not found"}

        await session.delete(custom)
        await session.commit()
        return {"success": True}


# ---------------------------------------------------------------------------
# 环境变量检测 — 检查哪些内置厂商的 key 已在环境变量中配置
# ---------------------------------------------------------------------------

@router.get("/env-check")
async def check_env_keys():
    """检查哪些内置厂商的 API Key 已在环境变量中配置（用于后端共享 key 模式）。"""
    configured = []
    for p in PROVIDERS:
        if os.environ.get(p.api_key_env):
            configured.append({
                "provider_id": p.id,
                "provider_name": p.name,
                "api_key_env": p.api_key_env,
            })
    return {
        "success": True,
        "data": configured,
        "total": len(configured),
    }
