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

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
