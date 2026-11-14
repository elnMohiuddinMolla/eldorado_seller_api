"""Secret masking for logs, terminal output, exceptions and the audit log."""

from __future__ import annotations

import logging
import re

REDACTED = "***REDACTED***"

# Values registered at runtime (Client secret, access tokens).
_secrets: set[str] = set()

_BEARER_RE = re.compile(r"(Bearer\s+)[^\s\"',;]+", re.IGNORECASE)
_JSON_SECRET_RE = re.compile(
    r"(\"(?:accessToken|access_token|clientSecret|client_secret)\"\s*:\s*\")[^\"]*(\")",
    re.IGNORECASE,
)
_AUTH_HEADER_RE = re.compile(r"(authorization['\"]?\s*[:=]\s*['\"]?)[^'\"\n,}]+", re.IGNORECASE)


def register_secret(value: str | None) -> None:
    """Remember a secret value so `redact` removes it from any text."""
    if value and len(value) >= 4:
        _secrets.add(value)


def redact(text: str) -> str:
    """Replace every known secret, bearer token and Authorization value with REDACTED."""
    for secret in sorted(_secrets, key=len, reverse=True):
        text = text.replace(secret, REDACTED)
    text = _JSON_SECRET_RE.sub(rf"\g<1>{REDACTED}\g<2>", text)
    text = _AUTH_HEADER_RE.sub(rf"\g<1>{REDACTED}", text)
    text = _BEARER_RE.sub(rf"\g<1>{REDACTED}", text)
    return text


class RedactingFilter(logging.Filter):
    """Logging filter that masks secrets in every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage())
        record.args = None
        return True


def setup_logging(level: int = logging.WARNING) -> None:
    handler = logging.StreamHandler()
    handler.addFilter(RedactingFilter())
    handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger("eldorado")
    root.handlers[:] = [handler]
    root.setLevel(level)
    root.propagate = False
