"""Platform settings (environment variables prefixed FAL_; .env is read for local development)."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FAL_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://fal:fal@127.0.0.1:5432/fal"
    temporal_address: str = "127.0.0.1:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "formal-lab-experiments"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"
    artifact_backend: str = "local"
    artifact_root: str = "./var/artifacts"
    deployment_profile: str = "local-single-user"
    sse_poll_seconds: float = 0.4
    log_level: str = "INFO"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
