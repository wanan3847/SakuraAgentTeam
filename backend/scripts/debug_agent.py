#!/usr/bin/env python3
"""Debug a single Agent end-to-end without starting the API server.

Usage:
    # Default: run RequirementsAgent on a sample requirement
    python scripts/debug_agent.py

    # Specify agent role
    python scripts/debug_agent.py --role design

    # Custom requirement
    python scripts/debug_agent.py --role frontend --requirement "做一个 todo 应用"

    # Disable LLM (use mock data)
    python scripts/debug_agent.py --no-llm
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from uuid import uuid4

# Ensure backend/ is on sys.path so `app.*` imports work
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _bootstrap_llm() -> None:
    """Register LLM providers if API keys are available."""
    from app.foundation.llm import LLMProviderFactory  # noqa: F401

    # Real providers self-register on import when their SDK is present.
    # If no key is set the factory will return a stub at call time.
    if os.environ.get("OPENAI_API_KEY"):
        print("[ok] OPENAI_API_KEY detected")
    elif os.environ.get("ANTHROPIC_API_KEY"):
        print("[ok] ANTHROPIC_API_KEY detected")
    else:
        print("[info] No LLM API key set — will use mock / template output")


def build_context(requirement: str, role: str) -> object:
    """Build a minimal Context for the chosen agent role."""
    from app.agents.types import AgentRole, Context

    AgentRole(role)

    return Context(
        session_id=f"debug-{uuid4().hex[:8]}",
        user_requirement=requirement,
        project_id="debug-project",
        metadata={
            "projects_root": str(ROOT / "data" / "debug_projects"),
            "project_id": "debug-project",
            "no_llm": os.environ.get("Sakura_NO_LLM") == "1",
        },
        agent_outputs={},
    )


async def run_agent(role: str, requirement: str) -> None:
    """Run a single agent and print the resulting artifact."""
    from app.agents import get_agent
    from app.agents.types import AgentRole

    if role not in {r.value for r in AgentRole}:
        print(f"[err] unknown role '{role}'. valid: {[r.value for r in AgentRole]}")
        return

    agent = get_agent(role)
    ctx = build_context(requirement, role)

    print(f"\n=== Running {role} agent ===")
    print(f"requirement: {requirement}\n")

    artifact = await agent.run(ctx)

    print("\n=== Artifact ===")
    print(
        json.dumps(
            artifact.to_dict()
            if hasattr(artifact, "to_dict")
            else {
                "name": artifact.name,
                "type": artifact.artifact_type,
                "summary": artifact.summary,
                "path": artifact.path,
            },
            indent=2,
            ensure_ascii=False,
        )
    )

    if artifact.content:
        preview = str(artifact.content)
        if len(preview) > 1200:
            preview = preview[:1200] + f"\n... ({len(preview) - 1200} more chars)"
        print("\n=== Content preview ===")
        print(preview)

    print(f"\n[done] review passed: {agent.status.value}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--role",
        default="requirements",
        choices=[
            "requirements",
            "design",
            "frontend",
            "backend",
            "testing",
            "review",
            "deployment",
        ],
        help="Which agent to run (default: requirements)",
    )
    parser.add_argument(
        "--requirement",
        default="帮我做一个简单的 todo 应用，支持添加、删除、标记完成",
        help="User requirement string",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Force mock LLM output (sets Sakura_NO_LLM=1)",
    )
    args = parser.parse_args()

    if args.no_llm:
        os.environ["Sakura_NO_LLM"] = "1"

    _bootstrap_llm()
    asyncio.run(run_agent(args.role, args.requirement))


if __name__ == "__main__":
    main()
