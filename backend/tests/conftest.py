"""Test configuration for pytest."""

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def app():
    """Create test application."""
    from app.api.main import app

    return app


@pytest.fixture
async def client(app):
    """Create async test client using ASGI transport."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
