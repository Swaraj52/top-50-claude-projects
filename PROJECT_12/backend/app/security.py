from __future__ import annotations

import secrets
import hashlib


def hash_password(password: str) -> str:
    """Hash a password using a secure one-way function."""
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        secrets.token_bytes(16),
        100000,
    ).hex()


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash."""
    return hash_password(password) == password_hash


def new_session_token() -> str:
    """Generate a new random session token."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Hash a token for secure storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()