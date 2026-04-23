from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = Path(__file__).resolve().parent

class Settings(BaseSettings):
    # App
    app_name: str = "Quorum"
    debug: bool = True

    # LLM Provider
    llm_provider: str = "local"  # "local", "google", "claude", or "azure"

    # Google Gemini API (FREE tier available)
    google_api_key: Optional[str] = None
    google_model: str = "gemini-1.5-flash"

    # Claude API (paid)
    anthropic_api_key: Optional[str] = None
    claude_model: str = "claude-opus-4-6"

    # Azure AI Foundry / Azure OpenAI Service
    # Endpoint pattern: https://{azure_resource_name}.services.ai.azure.com/models
    azure_resource_name: Optional[str] = None
    azure_api_key: Optional[str] = None
    azure_api_version: str = "2024-05-01-preview"
    # Chat deployment name as configured in Azure AI Foundry
    azure_chat_model_kimi_25: Optional[str] = None
    # Embedding deployment name (reserved for future GraphRAG use)
    azure_embedding_deployment: Optional[str] = None

    # Zep Memory Backend
    zep_api_key: Optional[str] = None
    zep_url: str = "http://zep:8000"  # Docker service name

    # PostgreSQL
    postgres_host: str = "postgres"
    postgres_user: str = "genericswarm"
    postgres_password: str = "genericswarm"
    postgres_db: str = "genericswarm"

    @property
    def database_url(self) -> str:
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:5432/{self.postgres_db}"

    # Redis
    redis_url: str = "redis://redis:6379"

    # Server
    server_host: str = "0.0.0.0"
    server_port: int = 8000

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
            str(BACKEND_DIR / ".env.local"),
            str(BACKEND_DIR / ".env"),
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )

settings = Settings()
