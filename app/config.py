"""Central application configuration.

All settings are loaded from environment variables (see `.env.example`).
The defaults are chosen so the project runs end-to-end in a fully offline
"demo mode" (MOCK_LLM + mock embeddings) with no paid API keys.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings.

    Values come from environment variables / a local `.env` file.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- LLM ---
    mock_llm: bool = True
    openai_api_key: str = "sk-not-set"
    openai_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"

    # --- Vector store ---
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "novagrowth_kb"
    use_mock_embeddings: bool = True
    embedding_dim: int = 384

    # --- App ---
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    database_url: str = "sqlite:///./novagrowth.db"
    knowledge_base_dir: str = "knowledge_base"
    log_level: str = "INFO"
    escalation_confidence_threshold: float = 0.45

    # --- Telegram ---
    telegram_bot_token: str = ""
    api_base_url: str = "http://localhost:8000"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


settings = get_settings()
