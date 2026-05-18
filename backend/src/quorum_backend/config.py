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

    # Persistence
    project_store_path: Path = Field(
        default_factory=lambda: (BACKEND_DIR / ".quorum_projects.pkl"),
        validation_alias="QUORUM_PROJECT_STORE_PATH",
    )

    @property
    def database_url(self) -> str:
        # Reserved for future persistent storage; keep for backward compatibility.
        postgres_host: str = getattr(self, "postgres_host", "postgres")
        postgres_user: str = getattr(self, "postgres_user", "genericswarm")
        postgres_password: str = getattr(self, "postgres_password", "genericswarm")
        postgres_db: str = getattr(self, "postgres_db", "genericswarm")
        return f"postgresql://{postgres_user}:{postgres_password}@{postgres_host}:5432/{postgres_db}"

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

