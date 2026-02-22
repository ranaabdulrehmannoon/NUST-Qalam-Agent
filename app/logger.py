"""Logging utilities for the Qalam monitoring agent."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """Format logs as structured JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_payload, ensure_ascii=False)


class SecurityRedactionFilter(logging.Filter):
    """Redact sensitive values from log records."""

    _value_patterns = [
        re.compile(
            r"(?i)(password|pass|token|secret|api[_\s-]?key|key|app[_\s-]?password|cookie)(\s*[:=]\s*)([^,\s;]+)"
        ),
        re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)([^,\s;]+)"),
    ]

    _key_patterns = re.compile(r"(?i)password|pass|token|secret|api[_\s-]?key|key|app[_\s-]?password|cookie")

    @staticmethod
    def _mask(value: str) -> str:
        if not value:
            return "***"
        return "***REDACTED***"

    def _redact_text(self, text: str) -> str:
        if not text:
            return text

        redacted = text.replace(".env", "[redacted-env-file]")
        if self._value_patterns:
            redacted = self._value_patterns[0].sub(
                lambda m: f"{m.group(1)}{m.group(2)}{self._mask(m.group(3))}",
                redacted,
            )
            redacted = self._value_patterns[1].sub(
                lambda m: f"{m.group(1)}{self._mask(m.group(2))}",
                redacted,
            )
        return redacted

    def _redact_mapping(self, payload: dict) -> dict:
        safe_payload: dict = {}
        for key, value in payload.items():
            if self._key_patterns.search(str(key)):
                safe_payload[key] = self._mask(str(value))
            elif isinstance(value, str):
                safe_payload[key] = self._redact_text(value)
            else:
                safe_payload[key] = value
        return safe_payload

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self._redact_text(record.msg)

        if isinstance(record.args, dict):
            record.args = self._redact_mapping(record.args)
        elif isinstance(record.args, tuple):
            record.args = tuple(self._redact_text(str(arg)) for arg in record.args)

        for attr, value in list(record.__dict__.items()):
            if attr in {"msg", "args", "name", "levelname", "levelno", "pathname", "filename", "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName", "created", "msecs", "relativeCreated", "thread", "threadName", "processName", "process", "message", "asctime"}:
                continue

            if self._key_patterns.search(attr):
                record.__dict__[attr] = self._mask(str(value))
            elif isinstance(value, str):
                record.__dict__[attr] = self._redact_text(value)

        return True


def mask_secret(secret: str) -> str:
    """Return a masked representation of sensitive values for safe logging."""
    if not secret:
        return "***"
    if len(secret) <= 2:
        return "*" * len(secret)
    return f"{secret[0]}{'*' * (len(secret) - 2)}{secret[-1]}"


def setup_logger(name: str = "qalam-agent") -> logging.Logger:
    """Create and configure a console logger with INFO and ERROR visibility."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if logger.handlers:
        return logger

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(JsonFormatter())
    console_handler.addFilter(SecurityRedactionFilter())

    logger.addHandler(console_handler)
    return logger
