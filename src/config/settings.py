"""Environment-sourced configuration.

Never hard-code secrets, database URLs, or environment-specific values in code —
everything here is sourced from environment variables / .env, per
.claude/rules/backend.md and .env.example.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    database_url: str = "postgresql+psycopg://banking:banking@localhost:5432/banking_ai"
    vector_database_url: str = "postgresql+psycopg://banking:banking@localhost:5432/banking_ai"

    # LLM_MODE=mock is a hard requirement (prompt.md § 52, .claude/rules/ai-agents.md) —
    # tests, CI, and demos must run without a paid API key.
    llm_mode: Literal["mock", "live"] = "mock"
    llm_provider: Literal["anthropic", "openai_compatible", "mock"] = "anthropic"
    llm_api_key: str = ""
    model_name: str = ""

    kafka_brokers: str = ""
    otel_endpoint: str = ""


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton — avoids re-reading/re-validating .env per call."""
    return Settings()
