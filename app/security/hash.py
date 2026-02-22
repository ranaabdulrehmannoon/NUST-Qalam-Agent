"""Password hashing utilities using bcrypt."""

from __future__ import annotations

import bcrypt


def hash_password(password: str) -> str:
    """Hash a raw password using bcrypt."""
    if not isinstance(password, str) or not password:
        raise ValueError("Password must be a non-empty string")

    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Verify a raw password against a bcrypt hash."""
    if not isinstance(password, str) or not isinstance(hashed, str):
        return False

    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False
