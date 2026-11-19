"""Application settings (environment) and decision thresholds (YAML)."""
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR.parent / ".env", extra="ignore")

    database_url: str = "postgresql+psycopg://limber:limber@localhost:5432/limber"
    jwt_secret: str = "change-me-in-.env"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24
    # Secret for patient pseudonyms on the clinician dashboard. Falls back to jwt_secret.
    pseudonym_secret: str = ""
    thresholds_path: Path = BACKEND_DIR / "config" / "thresholds.yaml"
    cors_origins: list[str] = ["http://localhost:5173"]
    # AI planning (M5). Leave empty to always use the rule-based fallback.
    # Set LLM_PROVIDER=gemini and LLM_API_KEY in .env. Never put a real key here.
    llm_provider: str = ""
    llm_api_key: str = ""
    llm_model: str = "gemini-3.5-flash"
    llm_timeout_s: int = 60
    # Optional Gmail/SMTP reminders. Keep disabled until credentials are configured.
    email_reminders_enabled: bool = False
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: SecretStr = SecretStr("")
    smtp_from: str = ""
    app_base_url: str = "http://localhost:5173"
    email_reminder_poll_seconds: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def load_default_thresholds() -> dict[str, Any]:
    """thresholds.yaml, read once. It seeds config version 1 and is the fallback with no versions."""
    with open(get_settings().thresholds_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_thresholds() -> dict[str, Any]:
    """Thresholds from the active model config version (clinician-editable), else thresholds.yaml.

    Request handlers that write records should call model_config.service.get_active_config()
    once and pass its thresholds down, so a whole request uses one version and can record its id.
    """
    from app.modules.model_config.service import get_active_config  # avoid import cycle

    return get_active_config().thresholds
