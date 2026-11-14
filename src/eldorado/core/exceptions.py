"""Domain exceptions. Every message is passed through `redact` so secrets never leak."""

from __future__ import annotations

from eldorado.core.logging import redact


class EldoradoError(Exception):
    """Base class for all errors raised by this tool."""

    def __init__(self, message: str, *, http_status: int | None = None) -> None:
        super().__init__(redact(message))
        self.http_status = http_status


class ConfigError(EldoradoError):
    """Missing or invalid settings in `.env`."""


class EldoradoAPIError(EldoradoError):
    """Any API error that has no more specific class."""


class AuthenticationError(EldoradoError):
    """Token request failed, or a request was still rejected after one token renewal."""


class RateLimitExceededError(EldoradoError):
    """Still rate limited after the maximum number of tries."""


class ResourceNotFoundError(EldoradoError):
    """Offer or order id not found."""


class WriteOutcomeUnknownError(EldoradoError):
    """A write timed out or got a network error or 5xx. It was NOT retried."""


class AuditLogError(EldoradoError):
    """The audit log could not be written."""


class EndpointNotConfirmedError(EldoradoError):
    """The operation needs a request detail that is not confirmed in api-spec.md yet."""


class PriceGuardError(EldoradoError):
    """A price change was blocked by a safety rule (50% guard, price <= 0)."""
