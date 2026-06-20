"""Testing Agent - generates tests for the generated code.

Produces:
- Backend unit tests (pytest)
- API integration tests
"""

from typing import List

from app.core.logging import get_logger
from app.agents.base import Agent, PlanStep
from app.agents.types import AgentRole, Artifact, Context, Plan

logger = get_logger(__name__)


class TestingAgent(Agent):
    """Testing Agent - generates test files."""

    role = AgentRole.TESTING
    description = "Generate unit tests and integration tests"

    def _default_plan_summary(self, ctx: Context) -> str:
        return "Generate pytest test files for backend API"

    def _default_plan_steps(self, ctx: Context) -> List[PlanStep]:
        return [
            PlanStep(description="Generate API endpoint tests", tool="file_write"),
            PlanStep(description="Generate CRUD operation tests", tool="file_write"),
            PlanStep(description="Generate error handling tests", tool="file_write"),
        ]

    async def execute(self, plan: Plan, ctx: Context) -> Artifact:
        """Generate test files."""
        logger.info("testing_agent_execute", session_id=ctx.session_id)

        features = self._extract_features(ctx)

        tests_content = self._generate_tests(features)

        artifact = Artifact(
            agent_role=self.role.value,
            artifact_type="code",
            name="tests.py",
            content=tests_content,
            metadata={
                "features": [f["title"] for f in features],
                "test_count": len(features) * 6,
                "files": [
                    {"path": "backend/tests/test_api.py", "content": tests_content},
                ],
            },
        )

        logger.info("testing_agent_done", session_id=ctx.session_id)
        return artifact

    def _extract_features(self, ctx: Context) -> List[dict]:
        """Extract features from context."""
        backend_output = ctx.get_output(AgentRole.BACKEND.value)
        if backend_output and hasattr(backend_output, "metadata"):
            fs = backend_output.metadata.get("features", [])
            return [{"title": f, "description": f"Manage {f}"} for f in fs]

        return [{"title": "items", "description": "Core items"}]

    def _generate_tests(self, features: List[dict]) -> str:
        """Generate comprehensive pytest tests."""
        parts = [
            '"""Auto-generated tests for Sakura API."""',
            "",
            "import pytest",
            "from fastapi.testclient import TestClient",
            "",
            "# Tests use TestClient to call the API",
            "# In a real setup, you would import the app from main.py",
            "",
        ]

        for feature in features:
            resource = feature["title"].lower().replace(" ", "_")
            name = feature["title"].replace(" ", "")

            parts.append(f'''class Test{name}API:
    """Test cases for {feature["title"]} API."""

    def test_list_endpoint(self, client):
        """Test GET /api/v1/{resource} returns a list."""
        response = client.get("/api/v1/{resource}")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)

    def test_create_item(self, client):
        """Test POST /api/v1/{resource} creates an item."""
        response = client.post(
            "/api/v1/{resource}",
            json={{"title": "Test {feature["title"].lower()}", "description": "A test item"}},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["title"] == "Test {feature["title"].lower()}"

    def test_get_item(self, client):
        """Test GET /api/v1/{resource}/{{id}} returns single item."""
        # First create an item
        create_response = client.post(
            "/api/v1/{resource}",
            json={{"title": "Get test"}},
        )
        item_id = create_response.json()["data"]["id"]

        # Then fetch it
        response = client.get(f"/api/v1/{resource}/{{item_id}}")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["id"] == item_id

    def test_update_item(self, client):
        """Test PUT /api/v1/{resource}/{{id}} updates an item."""
        # Create
        create_response = client.post(
            "/api/v1/{resource}",
            json={{"title": "Before update"}},
        )
        item_id = create_response.json()["data"]["id"]

        # Update
        response = client.put(
            f"/api/v1/{resource}/{{item_id}}",
            json={{"title": "After update", "status": "inactive"}},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["title"] == "After update"
        assert data["data"]["status"] == "inactive"

    def test_delete_item(self, client):
        """Test DELETE /api/v1/{resource}/{{id}} removes an item."""
        # Create
        create_response = client.post(
            "/api/v1/{resource}",
            json={{"title": "To be deleted"}},
        )
        item_id = create_response.json()["data"]["id"]

        # Delete
        delete_response = client.delete(f"/api/v1/{resource}/{{item_id}}")
        assert delete_response.status_code == 200

    def test_get_nonexistent_returns_404(self, client):
        """Test GET /api/v1/{resource}/9999 returns 404."""
        response = client.get("/api/v1/{resource}/99999")
        assert response.status_code == 404

''')

        return "\n".join(parts)
