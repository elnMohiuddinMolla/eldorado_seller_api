"""Token manager (F1). The access token lives in memory only."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

import httpx
from pydantic import ValidationError

from eldorado.client.base import MAX_TRIES, Sleep, backoff_delay, retry_after_seconds
from eldorado.core.config import Settings
from eldorado.core.exceptions import AuthenticationError, RateLimitExceededError
from eldorado.core.logging import register_secret
from eldorado.models.auth import TokenRequest, TokenResponse

log = logging.getLogger("eldorado.auth")

# [Confirmed] on the Seller API dashboard, see api-spec.md 3.1
TOKEN_PATH = "/api/authentication/seller/token"
REFRESH_MARGIN_SECONDS = 60


class TokenManager:
    def __init__(
        self,
        http: httpx.Client,
        settings: Settings,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Sleep = time.sleep,
    ) -> None:
        self._http = http
        self._request = TokenRequest(
            client_id=settings.client_id, client_secret=settings.client_secret
        )
        self._clock = clock
        self._sleep = sleep
        self._token: TokenResponse | None = None
        self._expires_at = 0.0
        # Parallel reads share one token; only one thread may fetch a new one at a time.
        self._lock = threading.RLock()

    def seconds_left(self) -> float:
        if self._token is None:
            return 0.0
        return max(self._expires_at - self._clock(), 0.0)

    def authorization_header(self) -> str:
        token = self._valid_token()
        return f"{token.token_type} {token.access_token.get_secret_value()}"

    def force_refresh(self) -> None:
        with self._lock:
            self._fetch()

    def _valid_token(self) -> TokenResponse:
        with self._lock:
            if self._token is None or self.seconds_left() <= REFRESH_MARGIN_SECONDS:
                self._fetch()
            assert self._token is not None
            return self._token

    def _fetch(self) -> None:
        body = self._request.to_body()
        for attempt in range(1, MAX_TRIES + 1):
            last = attempt == MAX_TRIES
            try:
                response = self._http.post(TOKEN_PATH, json=body)
            except httpx.TransportError as exc:
                if last:
                    raise AuthenticationError(
                        f"Could not reach the token endpoint after {MAX_TRIES} tries "
                        f"({type(exc).__name__})."
                    ) from None
                self._sleep(backoff_delay(attempt))
                continue

            status = response.status_code
            if status == 429:
                if last:
                    raise RateLimitExceededError(
                        "Token endpoint is still rate limited.", http_status=status
                    )
                self._sleep(retry_after_seconds(response, attempt))
                continue
            if status >= 500:
                if last:
                    raise AuthenticationError(
                        f"Token endpoint returned HTTP {status} after {MAX_TRIES} tries.",
                        http_status=status,
                    )
                self._sleep(backoff_delay(attempt))
                continue
            if 300 <= status < 400:
                raise AuthenticationError(
                    f"Token endpoint redirected (HTTP {status}) to "
                    f"{response.headers.get('Location', '?')}. Fix ELDORADO_BASE_URL.",
                    http_status=status,
                )
            if status >= 400:
                raise AuthenticationError(
                    f"Token request rejected (HTTP {status}). The credential is probably revoked "
                    "or expired. Generate a new one at Dashboard > Seller API and update .env.",
                    http_status=status,
                )

            try:
                token = TokenResponse.model_validate(response.json())
            except (ValueError, ValidationError):
                # Never include the body: it contains the token.
                raise AuthenticationError(
                    "Token response has an unexpected format (expected accessToken, expiresIn).",
                    http_status=status,
                ) from None

            register_secret(token.access_token.get_secret_value())
            self._token = token
            self._expires_at = self._clock() + token.expires_in
            log.debug("Got a new access token, valid for %s seconds", token.expires_in)
            return
