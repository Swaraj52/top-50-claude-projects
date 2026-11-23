from __future__ import annotations

import os
from dataclasses import dataclass

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo


@dataclass
class Settings:
    """Application settings loaded from environment or defaults."""

    debug: bool = os.environ.get("DEBUG", "0") not in ("0", "")
    """Whether to run in debug mode."""

    allowed_hosts: list[str] = None
    """Allowed hostnames for the application."""

    database_url: str = os.environ.get(
        "DATABASE_URL", "sqlite:///data/foundry.db"
    )
    """SQLAlchemy database URL."""

    secret_key: str = os.environ.get("SECRET_KEY", "foundry-dev-key-change-in-production")
    """Secret key for session signing."""

    session_days: int = int(os.environ.get("SESSION_DAYS", "30"))
    """Session duration in days."""

    ai_enabled: bool = os.environ.get("AI_ENABLED", "false") not in ("0", "")
    """Whether Claude AI features are enabled."""

    anthropic_model: str = os.environ.get("ANTHROPIC_MODEL", "claude-3-opus-20240229")
    """Claude model name when AI is enabled."""

    log_level: str = os.environ.get("LOG_LEVEL", "INFO")
    """Python logging level."""