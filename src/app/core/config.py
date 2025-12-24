from __future__ import annotations

from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    env: str = Field(default="local", validation_alias="APP_ENV")
    database_url: str = Field(default="postgresql://postgres:postgres@localhost:5432/renewaldesk")
    object_store_bucket: str = Field(default="renewal-desk")
    data_dir: str = Field(default=".data")
    examples_dir: str = Field(default="examples")
    prompt_version: str = Field(default="v0")
    max_tool_calls: int = 8
    max_tokens: int = 6000
    commit_sha: str = Field(default="dev")
    llm_provider: str = Field(default="mock")
    ollama_base_url: str = Field(default="http://host.docker.internal:11434")
    ollama_model: str = Field(default="llama3.1:8b")
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8080",
            "http://127.0.0.1:8080",
            "http://localhost:30081",
            "http://127.0.0.1:30081",
        ]
    )

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
