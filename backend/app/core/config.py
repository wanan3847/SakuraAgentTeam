"""Core configuration for SakuraAgentTeam backend."""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "SakuraAgentTeam"
    app_version: str = "0.1.0"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # LLM Providers
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    default_llm_provider: str = "openai"
    default_llm_model: str = "gpt-4o"

    # Local model support
    local_model_base_url: Optional[str] = None

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/sakura.db"

    # Experience store (ChromaDB)
    experience_db_path: str = "./data/experience_db"

    # Project store
    projects_root: str = "./data/projects"

    # Docker sandbox
    sandbox_image: str = "python:3.11-slim"
    sandbox_timeout: int = 300  # 5 minutes

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
