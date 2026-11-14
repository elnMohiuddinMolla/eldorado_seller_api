from __future__ import annotations

import json

import httpx
import pytest
import respx

from eldorado.client.auth import REFRESH_MARGIN_SECONDS, TOKEN_PATH, TokenManager
from eldorado.core.exceptions import AuthenticationError, RateLimitExceededError

from .conftest import ACCESS_TOKEN, CLIENT_ID, CLIENT_SECRET, FakeClock, token_json


def test_token_request_uses_confirmed_json_body(tokens: TokenManager, token_route: respx.Route) -> None:
    assert tokens.authorization_header() == f"Bearer {ACCESS_TOKEN}"
    request = token_route.calls.last.request
    assert request.method == "POST"
    assert request.url.path == TOKEN_PATH
    assert json.loads(request.content) == {"clientId": CLIENT_ID, "clientSecret": CLIENT_SECRET}


def test_token_is_cached(tokens: TokenManager, token_route: respx.Route) -> None:
    tokens.authorization_header()
    tokens.authorization_header()
    assert token_route.call_count == 1
    assert tokens.seconds_left() == 900


def test_token_renewed_when_60_seconds_left(
    tokens: TokenManager, token_route: respx.Route, clock: FakeClock
) -> None:
    tokens.authorization_header()
    clock.now += 900 - REFRESH_MARGIN_SECONDS - 1
    tokens.authorization_header()
    assert token_route.call_count == 1
    clock.now += 1
    tokens.authorization_header()
    assert token_route.call_count == 2


@pytest.mark.parametrize("status", [400, 401, 403])
def test_rejected_token_request_raises(
    tokens: TokenManager, api: respx.MockRouter, status: int
) -> None:
    route = api.post(TOKEN_PATH).mock(return_value=httpx.Response(status, json={"error": "revoked"}))
    with pytest.raises(AuthenticationError, match="revoked or expired") as info:
        tokens.authorization_header()
    assert route.call_count == 1
    assert CLIENT_SECRET not in str(info.value)


def test_token_5xx_is_retried(tokens: TokenManager, api: respx.MockRouter, sleeps: list[float]) -> None:
    route = api.post(TOKEN_PATH).mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json=token_json())]
    )
    tokens.authorization_header()
    assert route.call_count == 2
    assert len(sleeps) == 1


def test_token_network_error_gives_up_after_3(
    tokens: TokenManager, api: respx.MockRouter
) -> None:
    route = api.post(TOKEN_PATH).mock(side_effect=httpx.ConnectError("boom"))
    with pytest.raises(AuthenticationError, match="Could not reach"):
        tokens.authorization_header()
    assert route.call_count == 3


def test_token_rate_limit(tokens: TokenManager, api: respx.MockRouter, sleeps: list[float]) -> None:
    api.post(TOKEN_PATH).mock(return_value=httpx.Response(429, headers={"Retry-After": "2"}))
    with pytest.raises(RateLimitExceededError):
        tokens.authorization_header()
    assert sleeps == [2.0, 2.0]


def test_unexpected_token_response_does_not_leak_body(
    tokens: TokenManager, api: respx.MockRouter
) -> None:
    api.post(TOKEN_PATH).mock(return_value=httpx.Response(200, json={"token": "leaky-value-xyz"}))
    with pytest.raises(AuthenticationError, match="unexpected format") as info:
        tokens.authorization_header()
    assert "leaky-value-xyz" not in str(info.value)


def test_new_token_value_is_used_after_refresh(
    http: httpx.Client, settings, api: respx.MockRouter  # type: ignore[no-untyped-def]
) -> None:
    clock = FakeClock()
    api.post(TOKEN_PATH).mock(
        side_effect=[
            httpx.Response(200, json=token_json("first-token-111")),
            httpx.Response(200, json=token_json("second-token-222")),
        ]
    )
    manager = TokenManager(http, settings, clock=clock, sleep=lambda _: None)
    assert manager.authorization_header().endswith("first-token-111")
    manager.force_refresh()
    assert manager.authorization_header().endswith("second-token-222")
