"""Base HTTP client: auth header, retry rules and error mapping (AGENTS.md 4.3).

Reads may be retried. Writes are NEVER retried after a timeout, network error or 5xx,
because the change may already be applied on the live account.
"""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import httpx

from eldorado.core.exceptions import (
    AuthenticationError,
    EldoradoAPIError,
    RateLimitExceededError,
    ResourceNotFoundError,
    WriteOutcomeUnknownError,
)
from eldorado.core.logging import redact

if TYPE_CHECKING:
    from eldorado.client.auth import TokenManager

log = logging.getLogger("eldorado.client")

MAX_TRIES = 3
BACKOFF_FACTOR_SECONDS = 1.5
MAX_RETRY_AFTER_SECONDS = 60.0
ERROR_BODY_PREVIEW = 300

Sleep = Callable[[float], None]


def backoff_delay(attempt: int) -> float:
    """Exponential backoff with jitter. attempt starts at 1."""
    base = BACKOFF_FACTOR_SECONDS * (2 ** (attempt - 1))
    return base + random.uniform(0, BACKOFF_FACTOR_SECONDS)


def retry_after_seconds(response: httpx.Response, attempt: int) -> float:
    raw = response.headers.get("Retry-After")
    if raw:
        try:
            return min(max(float(raw), 0.0), MAX_RETRY_AFTER_SECONDS)
        except ValueError:
            pass
    return backoff_delay(attempt)


def error_preview(response: httpx.Response) -> str:
    text = response.text.strip().replace("\n", " ")
    return redact(text[:ERROR_BODY_PREVIEW])


class BaseClient:
    def __init__(
        self,
        http: httpx.Client,
        tokens: TokenManager,
        *,
        sleep: Sleep = time.sleep,
    ) -> None:
        self._http = http
        self._tokens = tokens
        self._sleep = sleep

    def read(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        return self._request(method, path, is_write=False, **kwargs)

    def write(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        return self._request(method, path, is_write=True, **kwargs)

    def check_token(self) -> float:
        """Make sure a valid token exists. Returns the seconds it has left."""
        self._tokens.authorization_header()
        return self._tokens.seconds_left()

    def close(self) -> None:
        self._http.close()

    def _request(self, method: str, path: str, *, is_write: bool, **kwargs: Any) -> httpx.Response:
        auth_renewed = False
        rate_tries = 0
        error_tries = 0

        while True:
            headers = {"Authorization": self._tokens.authorization_header()}
            try:
                response = self._http.request(method, path, headers=headers, **kwargs)
            except httpx.TransportError as exc:
                if is_write:
                    raise WriteOutcomeUnknownError(
                        f"{method} {path} failed with {type(exc).__name__}. The change may or may "
                        "not have been applied. It was NOT retried. Check the Eldorado dashboard."
                    ) from None
                error_tries += 1
                if error_tries >= MAX_TRIES:
                    raise EldoradoAPIError(
                        f"{method} {path} failed after {MAX_TRIES} tries: {type(exc).__name__}"
                    ) from None
                log.warning("Network error on %s %s, retrying", method, path)
                self._sleep(backoff_delay(error_tries))
                continue

            status = response.status_code

            if status == 401:
                if auth_renewed:
                    raise AuthenticationError(
                        f"{method} {path} was rejected (HTTP 401) even after renewing the token.",
                        http_status=status,
                    )
                auth_renewed = True
                self._tokens.force_refresh()
                continue

            if status == 429:
                rate_tries += 1
                if rate_tries >= MAX_TRIES:
                    raise RateLimitExceededError(
                        f"{method} {path} is still rate limited after {MAX_TRIES} tries.",
                        http_status=status,
                    )
                self._sleep(retry_after_seconds(response, rate_tries))
                continue

            if status >= 500:
                if is_write:
                    raise WriteOutcomeUnknownError(
                        f"{method} {path} returned HTTP {status}. The change may or may not have "
                        "been applied. It was NOT retried. Check the Eldorado dashboard.",
                        http_status=status,
                    )
                error_tries += 1
                if error_tries >= MAX_TRIES:
                    raise EldoradoAPIError(
                        f"{method} {path} returned HTTP {status} after {MAX_TRIES} tries: "
                        f"{error_preview(response)}",
                        http_status=status,
                    )
                self._sleep(backoff_delay(error_tries))
                continue

            if 300 <= status < 400:
                # Never follow: a redirected write could be replayed as a different method.
                raise EldoradoAPIError(
                    f"{method} {path} was redirected (HTTP {status}) to "
                    f"{response.headers.get('Location', '?')}. Check ELDORADO_BASE_URL.",
                    http_status=status,
                )

            if status == 404:
                raise ResourceNotFoundError(
                    f"{method} {path}: not found (HTTP 404). {error_preview(response)}",
                    http_status=status,
                )

            if status >= 400:
                raise EldoradoAPIError(
                    f"{method} {path} returned HTTP {status}: {error_preview(response)}",
                    http_status=status,
                )

            return response
