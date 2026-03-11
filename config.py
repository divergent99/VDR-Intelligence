# config.py
"""
Central configuration via pydantic-settings.
All env vars are read from the environment or a .env file.
Never hardcode credentials — use .env.example as the template.

Usage anywhere in the project:
    from config import settings
    print(settings.aws_region)
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── AWS / Bedrock ────────────────────────────────────────────
    aws_access_key_id:     str = ""
    aws_secret_access_key: str = ""
    aws_region:            str = "us-east-1"
    nova_model_id:         str = "us.amazon.nova-2-lite-v1:0"

    # ── Nova inference ───────────────────────────────────────────
    nova_max_tokens:            int   = 4096
    nova_temperature:           float = 0
    nova_thinking_max_tokens:   int   = 10000
    nova_thinking_effort:       str   = "medium"   # low | medium | high

    # ── Pipeline ─────────────────────────────────────────────────
    doc_char_limit:  int = 40_000   # max chars ingested from VDR folder
    node_char_limit: int = 8_000    # max chars sent to each node prompt

    # ── Cache (ChromaDB) ─────────────────────────────────────────
    chroma_path:       str  = "./vdr_cache"
    chroma_collection: str  = "diligence_results"
    cache_enabled:     bool = True

    # ── Database & Auth ──────────────────────────────────────────
    db_url: str = "sqlite:///./vdr_intelligence.db"
    secret_key: str = "super_secret_key_for_jwt_please_change_in_production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440 # 24 hours

    # ── API ──────────────────────────────────────────────────────
    api_host:     str = "0.0.0.0"
    api_port:     int = 8000
    api_prefix:   str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8050"]




@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Cached singleton — import this everywhere.
    lru_cache means .env is only parsed once per process.
    """
    return Settings()


# Convenience alias so callers can do:  from config import settings
settings = get_settings()