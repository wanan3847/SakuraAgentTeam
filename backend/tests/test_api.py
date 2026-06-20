"""Tests for API endpoints."""

from uuid import uuid4

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Test health check endpoint."""
    response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    """Test root endpoint."""
    response = await client.get("/")

    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "api_docs" in data


@pytest.mark.asyncio
async def test_agents_list(client: AsyncClient):
    """Test listing agents endpoint."""
    response = await client.get("/api/v1/agents")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "requirements" in data["roles"]


@pytest.mark.asyncio
async def test_workflows_list(client: AsyncClient):
    """Test listing workflows endpoint."""
    response = await client.get("/api/v1/workflows")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "full_greenfield" in data["workflows"]


@pytest.mark.asyncio
async def test_experiences_list_empty(client: AsyncClient):
    """Test listing experiences returns empty."""
    response = await client.get("/api/v1/experiences")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_workflow_select_dynamic(client: AsyncClient):
    """Test dynamic workflow selection."""
    response = await client.post(
        "/api/v1/workflows/select",
        json={"requirement": "做一个新的 todo 应用"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["workflow"]["name"] == "full_greenfield"


@pytest.mark.asyncio
async def test_create_and_get_session(client: AsyncClient):
    """Test creating a session and fetching it."""
    response = await client.post(
        "/api/v1/sessions",
        json={"requirement": "做一个简单博客", "auto_start": False},
    )
    assert response.status_code == 200
    data = response.json()
    session_id = data["data"]["id"]
    assert data["success"] is True

    # Fetch it
    response = await client.get(f"/api/v1/sessions/{session_id}")
    assert response.status_code == 200
    detail = response.json()
    assert detail["data"]["id"] == session_id


@pytest.mark.asyncio
async def test_session_not_found(client: AsyncClient):
    """Test that fetching a non-existent session returns 404."""
    response = await client.get("/api/v1/sessions/nonexistent_id_123")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_project_and_list_commits(client: AsyncClient):
    """Test creating a project, adding a file, and viewing commits."""
    project_id = f"test-proj-{uuid4().hex[:8]}"

    # Create project
    response = await client.post(
        "/api/v1/projects",
        json={"project_id": project_id, "name": "Test Project"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["id"] == project_id

    # List commits (should have at least the initial one)
    response = await client.get(f"/api/v1/projects/{project_id}/commits")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] >= 1
    assert data["data"][0]["message"]  # commit has a message

    # List files
    response = await client.get(f"/api/v1/projects/{project_id}/files")
    assert response.status_code == 200
    assert response.json()["count"] >= 1  # README.md

    # Read a file
    response = await client.get(f"/api/v1/projects/{project_id}/files/README.md")
    assert response.status_code == 200
    assert "Test Project" in response.json()["data"]["content"]


@pytest.mark.asyncio
async def test_rollback_project(client: AsyncClient):
    """Test that rollback changes HEAD and history shrinks."""
    project_id = f"rollback-proj-{uuid4().hex[:8]}"
    await client.post(
        "/api/v1/projects",
        json={"project_id": project_id, "name": "Rollback Test"},
    )

    # Get initial commit
    r1 = await client.get(f"/api/v1/projects/{project_id}/commits")
    initial = r1.json()["data"]
    assert len(initial) == 1
    initial_hash = initial[0]["hash"]

    # Rollback to initial (no-op)
    response = await client.post(
        f"/api/v1/projects/{project_id}/rollback",
        json={"commit_hash": initial_hash},
    )
    assert response.status_code == 200
    assert response.json()["success"] is True
