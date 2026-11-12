"""Configuration and settings management for SENTINEL.

Uses Pydantic Settings for robust environment variable validation,
type-safety, and default values.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide settings loaded from environment variables and/or .env files."""

    model_config = SettingsConfigDict(
        env_prefix="SENTINEL_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core Application
    APP_NAME: str = Field(default="SENTINEL", description="Application name")
    APP_VERSION: str = Field(default="0.1.0", description="Application version")
    ENVIRONMENT: Literal["development", "testing", "staging", "production"] = Field(
        default="development", description="Operational environment"
    )
    DEBUG: bool = Field(default=False, description="Enable debug mode")
    LOG_LEVEL: str = Field(default="INFO", description="Log level (DEBUG, INFO, WARN, ERROR)")
    HOST: str = Field(default="127.0.0.1", description="API server host")
    PORT: int = Field(default=8000, description="API server port")

    # Storage Paths
    BASE_DIR: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent.parent
    )
    DATA_DIR: Path = Field(default=Path("./data"), description="Base data directory")
    VECTOR_DB_DIR: Path = Field(
        default=Path("./data/vector_store"), description="Vector store persistence path"
    )

    # Database
    DATABASE_URL: str = Field(
        default="sqlite:///./data/sentinel.db", description="Relational database connection URL"
    )

    # ML Anomaly Engine Defaults
    ANOMALY_ZSCORE_THRESHOLD: float = Field(
        default=3.0, ge=1.0, le=10.0, description="Standard deviations for statistical anomaly trigger"
    )
    ISOLATION_FOREST_CONTAMINATION: float = Field(
        default=0.05, ge=0.001, le=0.5, description="Expected proportion of outliers in dataset"
    )

    # Knowledge / RAG Engine Defaults
    EMBEDDING_MODEL: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2", description="Embedding model identifier"
    )
    RAG_TOP_K: int = Field(
        default=5, ge=1, le=20, description="Number of historical docs/runbooks to retrieve"
    )

    # Agent & LLM Configuration (Keys are masked via SecretStr)
    LLM_PROVIDER: str = Field(
        default="mock", description="LLM provider name: 'mock', 'openai', 'anthropic', 'gemini'"
    )
    LLM_MODEL: str = Field(default="mock-reasoning-v1", description="Model identifier")
    OPENAI_API_KEY: Optional[SecretStr] = Field(default=None, description="OpenAI API key")
    ANTHROPIC_API_KEY: Optional[SecretStr] = Field(default=None, description="Anthropic API key")
    GEMINI_API_KEY: Optional[SecretStr] = Field(default=None, description="Gemini API key")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached instance of application settings."""
    return Settings()
