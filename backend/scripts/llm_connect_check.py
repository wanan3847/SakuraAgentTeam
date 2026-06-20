#!/usr/bin/env python3
"""验证 LLM Provider 接入流程（不消耗 token）。

不发起真实 LLM 调用，只验证：
  1. 配置文件能加载
  2. OPENAI_API_KEY / ANTHROPIC_API_KEY 任一被设置（且不是占位符）
  3. 对应 Provider 能实例化
  4. 默认模型名可被 SDK 解析
  5. 不存在则给出明确的下一步指引

用法：
    cd backend
    python3 scripts/llm_connect_check.py

退出码：
    0 - 真实 LLM Provider 就绪
    1 - 未配置 key（将使用 mock）
    2 - key 已设置但 provider 加载失败
"""

import sys
from pathlib import Path

# 让脚本能 import app.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings  # noqa: E402
from app.core.logging import setup_logging  # noqa: E402

setup_logging()


def is_placeholder(key: str | None, marker: str) -> bool:
    """判断 key 是否为 .env.example 的占位符。"""
    if not key:
        return True
    return marker in key


def main() -> int:
    print("=" * 60)
    print("SakuraAgentTeam LLM Connect Check")
    print("=" * 60)

    openai_key = settings.openai_api_key
    anthropic_key = settings.anthropic_api_key
    default_provider = settings.default_llm_provider
    default_model = settings.default_llm_model

    openai_set = bool(openai_key) and not is_placeholder(openai_key, "your-openai-key")
    anthropic_set = bool(anthropic_key) and not is_placeholder(anthropic_key, "your-anthropic-key")

    print("\n📋 配置：")
    print(f"  DEFAULT_LLM_PROVIDER: {default_provider}")
    print(f"  DEFAULT_LLM_MODEL:    {default_model}")
    if openai_set:
        print(f"  OPENAI_API_KEY:       已设置 ({openai_key[:8]}...)")
    else:
        print("  OPENAI_API_KEY:       未设置（或为占位符）")
    if anthropic_set:
        print(f"  ANTHROPIC_API_KEY:    已设置 ({anthropic_key[:8]}...)")
    else:
        print("  ANTHROPIC_API_KEY:    未设置（或为占位符）")

    # 决策
    if not openai_set and not anthropic_set:
        print("\n⚠️  未设置任何 LLM Key")
        print("   系统将使用 mock 模式：所有 Agent 返回固定模板")
        print("\n🔧 下一步：")
        print("   1. 编辑 backend/.env")
        print("   2. 填入真实 key：")
        print("        OPENAI_API_KEY=sk-...")
        print("        ANTHROPIC_API_KEY=sk-ant-...")
        print("   3. 重启后端，再跑本脚本")
        return 1

    # 尝试加载 provider
    print("\n🔌 加载 Provider...")
    try:
        from app.foundation.llm import LLMProviderFactory

        factory = LLMProviderFactory()

        if default_provider == "openai":
            if not openai_set:
                print("❌ DEFAULT_LLM_PROVIDER=openai 但 OPENAI_API_KEY 未配置")
                return 2
            provider = factory.create(
                provider="openai",
                api_key=openai_key,
                model=default_model,
            )
        elif default_provider == "anthropic":
            if not anthropic_set:
                print("❌ DEFAULT_LLM_PROVIDER=anthropic 但 ANTHROPIC_API_KEY 未配置")
                return 2
            provider = factory.create(
                provider="anthropic",
                api_key=anthropic_key,
                model=default_model,
            )
        else:
            print(f"❌ 不支持的 provider: {default_provider}（仅支持 openai/anthropic）")
            return 2

        print(f"  ✅ {provider.__class__.__name__} 加载成功")
        print(f"     model={provider.model}")

    except Exception as e:
        print(f"\n❌ Provider 加载失败：{type(e).__name__}: {e}")
        print("\n🔧 排查：")
        print("   - key 格式是否正确（OpenAI: sk-..., Anthropic: sk-ant-...）")
        print("   - uv pip install --system -r backend/requirements.txt 装齐依赖")
        print(f"   - DEFAULT_LLM_MODEL={default_model} 是否被 SDK 支持")
        return 2

    print("\n✅ 真实 LLM Provider 就绪")
    print("   Agent 将在下次执行时调用真实模型")
    print("\n🚀 触发端到端：")
    print("   1. 启动后端: ./deploy.sh dev")
    print("   2. 浏览器打开 http://localhost:5173")
    print("   3. 新建任务 → 7 个 Agent 全部用真实 LLM")
    return 0


if __name__ == "__main__":
    sys.exit(main())
