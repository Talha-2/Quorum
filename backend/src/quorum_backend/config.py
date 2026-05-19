from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[3]
BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # App
    app_name: str = "Quorum"
    debug: bool = False

    # Logging — "plain" (default) or "json" for structured logs.
    log_format: str = Field(default="plain", validation_alias="LOG_FORMAT")

    # LLM Provider
    llm_provider: str = "local"  # "local", "google", "claude", or "azure"

    # Google Gemini API (free tier available)
    google_api_key: Optional[str] = None
    google_model: str = "gemini-1.5-flash"

    # Claude API
    anthropic_api_key: Optional[str] = None
    claude_model: str = "claude-opus-4-6"

    # Azure AI Foundry / Azure OpenAI Service
    azure_resource_name: Optional[str] = None
    azure_api_key: Optional[str] = None
    azure_api_version: str = "2024-05-01-preview"
    azure_chat_model_kimi_25: Optional[str] = None
    azure_embedding_deployment: Optional[str] = None

    # Server
    server_host: str = "0.0.0.0"
    server_port: int = 8000

    # Persistence — SQL database.
    # Set DATABASE_URL to a PostgreSQL DSN in production, e.g.
    #   postgresql+psycopg2://user:pass@host:5432/quorum
    # When empty, the backend falls back to a local SQLite file so the app
    # runs with zero configuration for development and tests.
    database_url: str = Field(default="", validation_alias="DATABASE_URL")

    @property
    def resolved_database_url(self) -> str:
        if self.database_url.strip():
            return self.database_url.strip()
        return f"sqlite:///{(BACKEND_DIR / '.quorum_projects.db').as_posix()}"

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on", "debug", "development", "dev"}:
                return True
            if normalized in {"0", "false", "no", "off", "release", "production", "prod"}:
                return False
        return value

    model_config = SettingsConfigDict(
        env_file=(
            str(ROOT_DIR / ".env.local"),
            str(ROOT_DIR / ".env"),
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

