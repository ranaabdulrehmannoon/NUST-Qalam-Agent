"""Input validation helpers for security and data integrity."""

from __future__ import annotations

import re


class ValidationError(ValueError):
    """Raised when a validation check fails."""


EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def validate_email(email: str) -> str:
    """Validate and normalize an email address."""
    if not isinstance(email, str):
        raise ValidationError("Email must be a string")

    normalized = email.strip()
    if not normalized:
        raise ValidationError("Email must not be empty")
    if "\n" in normalized or "\r" in normalized:
        raise ValidationError("Email contains invalid newline characters")
    if not EMAIL_PATTERN.fullmatch(normalized):
        raise ValidationError("Email format is invalid")
    return normalized


def validate_percentage(value: float) -> float:
    """Validate percentage value in inclusive range 0..100."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError("Percentage must be numeric")

    numeric = float(value)
    if numeric < 0.0 or numeric > 100.0:
        raise ValidationError("Percentage must be between 0 and 100")
    return numeric
