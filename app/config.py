"""Central application configuration.

All settings are loaded from environment variables (see `.env.example`).
The application is LLM-first by default: product chat should call the
configured OpenAI-compatible model. `MOCK_LLM=true` remains available for
tests and explicit offline demos only.
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
    # Works with any OpenAI-compatible endpoint. For DeepSeek, set
    # OPENAI_BASE_URL=https://api.deepseek.com and LLM_MODEL=deepseek-chat.
    mock_llm: bool = False
    openai_api_key: str = "sk-not-set"
    openai_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.3
    llm_timeout: int = 30  # seconds per request
    embedding_model: str = "text-embedding-3-small"

    # --- Vector store ---
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "assistant_kb"
    use_mock_embeddings: bool = True
    embedding_dim: int = 384

    # --- App ---
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    database_url: str = "sqlite:///./assistant.db"
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
