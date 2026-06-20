"""M4-I2 部署 Agent 真实 docker-compose 语法验证测试。"""

import shutil
import sys

import pytest

sys.path.insert(0, "/Users/yangyazhou/SakuraAgentTeam/backend")


def _make_ctx(session_id: str = "test-m4-i2"):
    """构造最小可用的 Context（绕过 SessionContext 依赖）。"""
    from app.agents.types import Context

    return Context(
        session_id=session_id,
        project_id=session_id,
        user_requirement="todo app",
    )


def _make_plan(session_id: str = "test-m4-i2"):
    from app.agents.types import Plan, PlanStep

    return Plan(
        agent_role="deployment",
        summary="generate deployment config",
        steps=[PlanStep(description="step 1", tool="file_write")],
    )


@pytest.mark.asyncio
async def test_deployment_agent_validates_compose_syntax():
    """DeploymentAgent 应当对生成的 docker-compose 跑 `docker compose config` 验证。"""
    from app.agents.deployment_agent import DeploymentAgent
    from app.agents.types import Artifact

    agent = DeploymentAgent()
    ctx = _make_ctx("test-m4-i2-syntax")
    plan = _make_plan("test-m4-i2-syntax")

    artifact = await agent.execute(plan, ctx)

    assert isinstance(artifact, Artifact)
    assert artifact.metadata["deploy_method"] == "docker-compose"
    assert "build_verified" in artifact.metadata
    assert "build_verify_msg" in artifact.metadata
    # build_verified: True（docker 装了 + 语法对）/ None（docker 没装）/ False（语法错）
    assert artifact.metadata["build_verified"] in (True, False, None)

    if shutil.which("docker"):
        # 如果有 docker，verify_msg 应该是正常消息
        assert isinstance(artifact.metadata["build_verify_msg"], str)
        assert len(artifact.metadata["build_verify_msg"]) > 0


@pytest.mark.asyncio
async def test_deployment_agent_files_well_formed():
    """DeploymentAgent 应当生成 4 个文件并都在 metadata['files'] 中。"""
    from app.agents.deployment_agent import DeploymentAgent
    from app.agents.types import Artifact

    agent = DeploymentAgent()
    ctx = _make_ctx("test-m4-i2-files")
    plan = _make_plan("test-m4-i2-files")

    artifact = await agent.execute(plan, ctx)
    assert isinstance(artifact, Artifact)

    files = artifact.metadata["files"]
    assert len(files) == 4
    paths = {f["path"] for f in files}
    assert "backend/Dockerfile" in paths
    assert "frontend/Dockerfile" in paths
    assert "docker-compose.yml" in paths
    assert "DEPLOYMENT.md" in paths

    for f in files:
        assert f["content"].strip(), f"{f['path']} content is empty"

    for f in files:
        assert f["content"][:80] in artifact.content, f"{f['path']} not in combined content"
