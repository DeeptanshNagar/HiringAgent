"""
Centralized application configuration using Pydantic BaseSettings.

All environment variables are validated at startup with type safety,
defaults, and clear error messages. This replaces scattered os.getenv()
calls across the codebase (12-Factor App compliance).
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide configuration loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM API Keys (at least one required) ──────────────────────────
    groq_api_key: Optional[str] = Field(default=None, description="Groq API key for Llama models")
    anthropic_api_key: Optional[str] = Field(default=None, description="Anthropic API key for Claude")
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key for GPT-4o / embeddings")

    # ── Model Selection ───────────────────────────────────────────────
    default_groq_model: str = "llama-3.3-70b-versatile"
    default_anthropic_model: str = "claude-sonnet-4-20250514"
    default_openai_model: str = "gpt-4o-2024-08-06"
    default_embedding_model: str = "text-embedding-3-small"
    llm_temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    llm_max_retries: int = Field(default=2, ge=0, le=5)

    # ── LinkedIn / RapidAPI ───────────────────────────────────────────
    rapidapi_key: Optional[str] = Field(default=None, description="RapidAPI key for LinkedIn scraping")

    # ── Observability ─────────────────────────────────────────────────
    langchain_api_key: Optional[str] = None
    langchain_tracing_v2: bool = False
    langchain_project: str = "hr-shortlisting-agent"

    # ── Application Security ──────────────────────────────────────────
    agent_api_key: str = Field(default="change-me-in-production", description="Internal API key for auth")
    allowed_origins: str = Field(default="*", description="Comma-separated CORS origins")
    rate_limit_max_requests: int = Field(default=10, ge=1)
    rate_limit_window_seconds: int = Field(default=60, ge=1)

    # ── File Processing ───────────────────────────────────────────────
    max_file_size_mb: int = Field(default=10, ge=1, le=100)
    max_candidates_per_run: int = Field(default=50, ge=1, le=200)

    # ── Cache ─────────────────────────────────────────────────────────
    enable_cache: bool = True
    cache_db_path: str = "./cache/langchain_cache.db"

    # ── Paths ─────────────────────────────────────────────────────────
    output_dir: str = "./output"
    logs_dir: str = "./logs"

    # ── Logging ───────────────────────────────────────────────────────
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="'json' for production, 'text' for development")

    # ── Computed helpers ──────────────────────────────────────────────

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def has_llm_key(self) -> bool:
        return bool(self.groq_api_key or self.anthropic_api_key or self.openai_api_key)

    @property
    def primary_llm_provider(self) -> str:
        """Return the name of the first available LLM provider."""
        if self.groq_api_key:
            return "groq"
        if self.anthropic_api_key:
            return "anthropic"
        if self.openai_api_key:
            return "openai"
        return "none"

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in valid:
            raise ValueError(f"log_level must be one of {valid}")
        return v_upper

    def validate_api_keys(self) -> None:
        """Raise RuntimeError if no LLM API key is configured."""
        if not self.has_llm_key:
            raise RuntimeError(
                "No LLM API key configured. "
                "Please set GROQ_API_KEY, ANTHROPIC_API_KEY, or OPENAI_API_KEY in your .env file. "
                "See .env.example for reference."
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()
