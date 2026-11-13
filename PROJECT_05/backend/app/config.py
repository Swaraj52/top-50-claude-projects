from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
DATA_DIR = PROJECT_DIR / "data"


class Settings(BaseSettings):
    """Runtime configuration from the environment and PROJECT_05/.env."""

    model_config = SettingsConfigDict(env_file=PROJECT_DIR / ".env", extra="ignore")

    database_url: str = f"sqlite:///{(DATA_DIR / 'cadence.db').as_posix()}"
    cookie_secure: bool = False
    session_days: int = 30

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-5-5"
    ai_timeout_seconds: float = 30.0

    run_migrations: bool = True
    log_level: str = "INFO"

    @property
    def ai_enabled(self) -> bool:
        return bool(self.anthropic_api_key.strip())
