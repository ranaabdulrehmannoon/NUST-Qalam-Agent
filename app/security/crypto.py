"""Symmetric encryption utilities using Fernet."""

from __future__ import annotations

import os

from cryptography.fernet import Fernet, InvalidToken


class CryptoError(RuntimeError):
    """Raised when cryptographic operations fail."""


def _get_fernet() -> Fernet:
    """Load and return configured Fernet instance from environment."""
    key = os.getenv("FERNET_KEY", "").strip()
    if not key:
        raise CryptoError("Missing required environment variable: FERNET_KEY")

    try:
        return Fernet(key.encode("utf-8"))
    except Exception as exc:
        raise CryptoError("Invalid FERNET_KEY format") from exc


def encrypt_string(value: str) -> str:
    """Encrypt a plaintext string and return a URL-safe token."""
    if not isinstance(value, str):
        raise CryptoError("encrypt_string expects a string value")

    fernet = _get_fernet()
    token = fernet.encrypt(value.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_string(token: str) -> str:
    """Decrypt a Fernet token and return plaintext."""
    if not isinstance(token, str):
        raise CryptoError("decrypt_string expects a string token")

    fernet = _get_fernet()
    try:
        decrypted = fernet.decrypt(token.encode("utf-8"))
        return decrypted.decode("utf-8")
    except InvalidToken as exc:
        raise CryptoError("Invalid or expired encrypted token") from exc
