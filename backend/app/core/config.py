"""Application settings (environment) and decision thresholds (YAML)."""
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://limber:limber@localhost:5432/limber"
    jwt_secret: str = "change-me-in-.env"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24
    thresholds_path: Path = BACKEND_DIR / "config" / "thresholds.yaml"
    cors_origins: list[str] = ["http://localhost:5173"]
    # AI planning (M5). Leave empty to always use the rule-based fallback.
    llm_provider: str = ""
    llm_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_thresholds() -> dict[str, Any]:
    """Load thresholds.yaml once. Rules read from this instead of hard-coding numbers."""
    with open(get_settings().thresholds_path, encoding="utf-8") as f:
        return yaml.safe_load(f)
