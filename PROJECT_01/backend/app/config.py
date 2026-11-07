from __future__ import annotations

import secrets
from functools import cached_property
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
DATA_DIR = PROJECT_DIR / "data"


class Settings(BaseSettings):
    """Runtime configuration, read from the environment and PROJECT_01/.env."""

    model_config = SettingsConfigDict(env_file=PROJECT_DIR / ".env", extra="ignore")

    database_url: str = f"sqlite:///{(DATA_DIR / 'dashboard.db').as_posix()}"
    # Used for session-independent encryption of stored third-party secrets.
    # If unset, a random key is generated once and kept in data/secret.key.
    app_secret_key: str = ""
    cookie_secure: bool = False
    session_days: int = 14

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-5-5"

    frontend_dist: Path = PROJECT_DIR / "frontend" / "dist"
    run_migrations: bool = True
    log_level: str = "INFO"

    @property
    def ai_enabled(self) -> bool:
        return bool(self.anthropic_api_key.strip())

    @cached_property
    def secret_key(self) -> str:
        if self.app_secret_key:
            return self.app_secret_key
        key_file = DATA_DIR / "secret.key"
        if key_file.exists():
            return key_file.read_text(encoding="utf-8").strip()
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        key = secrets.token_urlsafe(48)
        key_file.write_text(key, encoding="utf-8")
        return key
