"""Configuration loading and validation for the Qalam agent."""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import quote_plus

from dotenv import load_dotenv

from .security.validation import ValidationError, validate_email


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


REQUIRED_ENV_VARS = (
    "FERNET_KEY",
    "QALAM_USERNAME",
    "QALAM_PASSWORD",
    "DB_HOST",
    "DB_PORT",
    "DB_NAME",
    "DB_USER",
    "DB_PASSWORD",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",
    "SMTP_FROM",
    "SMTP_TO",
)


@dataclass(frozen=True)
class Settings:
    """Runtime settings loaded from environment variables."""

    qalam_username: str
    qalam_password: str
    qalam_login_url: str
    headless: bool
    login_timeout_ms: int
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    smtp_from: str
    smtp_to: str

    @property
    def database_url(self) -> str:
        """Build SQLAlchemy database URL for MySQL."""
        encoded_password = quote_plus(self.db_password)
        return (
            f"mysql+pymysql://{self.db_user}:{encoded_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


def _parse_bool(raw_value: str | None, default: bool = True) -> bool:
    """Parse a string environment value into a boolean."""
    if raw_value is None:
        return default

    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigError("Invalid configuration detected. Please review your .env values.")


def _validate_https(url: str) -> str:
    """Ensure URLs are HTTPS-only for secure transport."""
    if not url.lower().startswith("https://"):
        raise ConfigError("Invalid configuration detected. Please review your .env values.")
    return url


def _get_required_env_value(key: str) -> str:
    """Get required environment variable and fail fast if missing."""
    value = os.getenv(key)
    if value is None or not value.strip():
        raise ConfigError(f"Missing required configuration variable: {key}")
    return value.strip()


def validate_configuration(settings: Settings) -> None:
    """Validate cross-field runtime configuration constraints."""
    if settings.db_port <= 0 or settings.db_port > 65535:
        raise ConfigError("Invalid DB_PORT range")

    if settings.smtp_port <= 0 or settings.smtp_port > 65535:
        raise ConfigError("Invalid SMTP_PORT range")

    try:
        validate_email(settings.smtp_from)
        validate_email(settings.smtp_to)
    except ValidationError as exc:
        raise ConfigError(str(exc)) from exc


def get_settings() -> Settings:
    """Load and validate settings from environment variables."""
    load_dotenv()

    for key in REQUIRED_ENV_VARS:
        _get_required_env_value(key)

    username = _get_required_env_value("QALAM_USERNAME")
    password = _get_required_env_value("QALAM_PASSWORD")
    login_url = os.getenv("QALAM_LOGIN_URL", "https://qalam.nust.edu.pk/").strip()
    headless = _parse_bool(os.getenv("QALAM_HEADLESS"), default=True)

    timeout_raw = os.getenv("QALAM_LOGIN_TIMEOUT_MS", "30000").strip()
    if not timeout_raw.isdigit():
        raise ConfigError("Invalid configuration detected. Please review your .env values.")

    db_host = _get_required_env_value("DB_HOST")
    db_port_raw = _get_required_env_value("DB_PORT")
    db_name = _get_required_env_value("DB_NAME")
    db_user = _get_required_env_value("DB_USER")
    db_password = _get_required_env_value("DB_PASSWORD")

    smtp_host = _get_required_env_value("SMTP_HOST")
    smtp_port_raw = _get_required_env_value("SMTP_PORT")
    smtp_username = _get_required_env_value("SMTP_USERNAME")
    smtp_password = _get_required_env_value("SMTP_PASSWORD")
    smtp_from = _get_required_env_value("SMTP_FROM")
    smtp_to = _get_required_env_value("SMTP_TO")

    if not db_port_raw.isdigit():
        raise ConfigError("Invalid configuration detected. Please review your .env values.")

    if not smtp_port_raw.isdigit():
        raise ConfigError("Invalid SMTP port. Must be a number.")

    settings = Settings(
        qalam_username=username,
        qalam_password=password,
        qalam_login_url=_validate_https(login_url),
        headless=headless,
        login_timeout_ms=int(timeout_raw),
        db_host=db_host,
        db_port=int(db_port_raw),
        db_name=db_name,
        db_user=db_user,
        db_password=db_password,
        smtp_host=smtp_host,
        smtp_port=int(smtp_port_raw),
        smtp_username=smtp_username,
        smtp_password=smtp_password,
        smtp_from=smtp_from,
        smtp_to=smtp_to,
    )

    validate_configuration(settings)
    return settings
