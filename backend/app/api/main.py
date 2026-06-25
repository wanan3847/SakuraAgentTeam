"""FastAPI application entry point for SakuraAgentTeam.

Provides:
- Multi-agent workflow orchestration
- SSE real-time event streaming
- Experience store (ChromaDB)
- Artifact management

Usage:
    cd backend
    python -m app.api.main
    # or
    uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import get_logger, setup_logging

# Initialize logging first
setup_logging()
logger = get_logger(__name__)

logger.info(
    "application_starting",
    app_name=settings.app_name,
    version=settings.app_version,
)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="多智能体可协同全栈 Agent 开发系统",
)

from app.api.connectors import router as connectors_router  # noqa: E402, F401
from app.api.routes import router as api_router  # noqa: E402
from app.api.teams import router as teams_router  # noqa: E402
from app.auth.routes import router as auth_router  # noqa: E402
from app.auth.database import init_db  # noqa: E402
from app.history.routes import router as history_router  # noqa: E402
from app.llm_providers.routes import router as llm_router  # noqa: E402
from app.submissions.routes import router as submissions_router  # noqa: E402

# CORS middleware - allow all for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(connectors_router)
app.include_router(teams_router)
app.include_router(auth_router)
app.include_router(history_router)
app.include_router(submissions_router)
app.include_router(llm_router)


@app.on_event("startup")
async def _startup():
    """Initialize database tables on startup."""
    await init_db()


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app_name": settings.app_name,
        "version": settings.app_version,
    }


@app.get("/")
async def root():
    """Root endpoint - returns API information."""
    return {
        "message": "SakuraAgentTeam - Multi-Agent Full-Stack Development System",
        "api_docs": "/docs",
        "health": "/health",
        "api_base": "/api/v1",
        "endpoints": {
            "sessions": "/api/v1/sessions",
            "session_stream": "/api/v1/sessions/{id}/stream",
            "experiences": "/api/v1/experiences",
            "workflows": "/api/v1/workflows",
            "agents": "/api/v1/agents",
            "connectors": {
                "github_issues": "/api/v1/connectors/github/issues",
                "github_pr": "/api/v1/connectors/github/pr",
                "im": "/api/v1/connectors/im",
                "upload": "/api/v1/connectors/upload",
                "url": "/api/v1/connectors/url",
            },
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )
