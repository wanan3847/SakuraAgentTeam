"""Testing Agent - generates tests for the generated code.

Produces:
- Backend unit tests (pytest)
- API integration tests
"""

from app.agents.base import Agent, PlanStep
from app.agents.types import AgentRole, Artifact, Context, Plan
from app.core.logging import get_logger

logger = get_logger(__name__)


class TestingAgent(Agent):
    """Testing Agent - generates test files."""

    role = AgentRole.TESTING
    description = "Generate unit tests and integration tests"

    def _default_plan_summary(self, ctx: Context) -> str:
        return "Generate pytest test files for backend API"

    def _default_plan_steps(self, ctx: Context) -> list[PlanStep]:
        return [
            PlanStep(description="Generate API endpoint tests", tool="file_write"),
            PlanStep(description="Generate CRUD operation tests", tool="file_write"),
            PlanStep(description="Generate error handling tests", tool="file_write"),
        ]

    async def execute(self, plan: Plan, ctx: Context) -> Artifact:
        """Generate test files.

        有 LLM provider 时调用 LLM 生成测试代码；
        无 LLM 或 LLM 调用失败时回退到模板逻辑。
        """
        logger.info("testing_agent_execute", session_id=ctx.session_id)

        features = self._extract_features(ctx)

        # 优先使用 LLM 生成测试代码
        tests_content: str | None = None
        if self.llm is not None:
            try:
                tests_content = await self._generate_with_llm(features, ctx)
            except Exception as exc:
                logger.warning(
                    "testing_agent_llm_fallback",
                    error=str(exc),
                )
                tests_content = None

        # 无 LLM 或 LLM 失败时使用模板
        if tests_content is None:
            tests_content = self._generate_tests(features)
            test_file_path = "backend/tests/test_api.py"
        else:
            test_file_path = "tests/test_api.py"

        artifact = Artifact(
            agent_role=self.role.value,
            artifact_type="code",
            name="tests.py",
            content=tests_content,
            metadata={
                "features": [f["title"] for f in features],
                "test_count": len(features) * 6,
                "files": [
                    {"path": test_file_path, "content": tests_content},
                ],
            },
        )

        logger.info("testing_agent_done", session_id=ctx.session_id)
        return artifact

    async def _generate_with_llm(
        self, features: list[dict], ctx: Context
    ) -> str:
        """使用 LLM 生成测试代码。

        将后端代码和 design agent 的 API 契约消息作为上下文传给 LLM，
        生成更准确的测试。返回测试文件内容字符串。解析失败时抛异常触发回退。
        """
        features_desc = "\n".join(
            f"- {f['title']}: {f.get('description', '')}" for f in features
        )

        # 读取后端 Agent 的输出作为上下文
        backend_content = ""
        backend_output = ctx.get_output(AgentRole.BACKEND.value)
        if backend_output and hasattr(backend_output, "content"):
            backend_content = backend_output.content

        # 从 design agent 的消息中获取 API 契约作为测试依据
        api_contract = ""
        design_messages = ctx.get_messages_from(AgentRole.DESIGN.value)
        if design_messages:
            api_contract = "\n".join(
                f"[{m.message_type}] {m.content}" for m in design_messages
            )

        prompt = f"""你是测试工程师。请根据后端 API 代码生成 pytest 测试代码。

## 用户需求
{ctx.user_requirement}

## 功能列表
{features_desc}

## API 契约（来自 design agent）
{api_contract if api_contract else "无"}

## 后端代码（节选）
{backend_content[:3000] if backend_content else "无"}

## 输出要求
生成 1 个文件，严格使用如下格式输出：

### FILE: tests/test_api.py
```python
# 测试代码
```

代码要求：
- 使用 pytest 和 fastapi.testclient.TestClient
- 为每个功能的 CRUD 操作编写测试用例
- 测试场景包括：列表查询、创建、获取单个、更新、删除、404 不存在
- 提供 client fixture（基于 TestClient，每个测试前后清理数据库）
- 代码要能直接 pytest 运行
"""
        response = await self.run_agentic_loop(
            prompt=prompt,
            ctx=ctx,
            system_prompt=self.build_system_prompt(ctx),
        )
        files_map = self.parse_files_block(response)

        if "tests/test_api.py" not in files_map or not files_map["tests/test_api.py"].strip():
            raise ValueError("LLM 未生成 tests/test_api.py 或内容为空")

        return files_map["tests/test_api.py"]

    def _extract_features(self, ctx: Context) -> list[dict]:
        """Extract features from context."""
        backend_output = ctx.get_output(AgentRole.BACKEND.value)
        if backend_output and hasattr(backend_output, "metadata"):
            fs = backend_output.metadata.get("features", [])
            return [{"title": f, "description": f"Manage {f}"} for f in fs]

        return [{"title": "items", "description": "Core items"}]

    def _generate_tests(self, features: list[dict]) -> str:
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
