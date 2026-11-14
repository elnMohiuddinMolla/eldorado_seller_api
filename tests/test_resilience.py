"""Retry rules (AGENTS.md 4.3). Paths below are fake and exist only inside respx mocks."""

from __future__ import annotations

import httpx
import pytest
import respx

from eldorado.client.auth import TOKEN_PATH
from eldorado.client.base import BaseClient
from eldorado.core.exceptions import (
    AuthenticationError,
    EldoradoAPIError,
    RateLimitExceededError,
    ResourceNotFoundError,
    WriteOutcomeUnknownError,
)

from .conftest import token_json

READ_PATH = "/mock/read"
WRITE_PATH = "/mock/write"


def test_auth_rejected_renews_token_once(base: BaseClient, api: respx.MockRouter) -> None:
    tokens = api.post(TOKEN_PATH).mock(
        side_effect=[
            httpx.Response(200, json=token_json("old-token-1")),
            httpx.Response(200, json=token_json("new-token-2")),
        ]
    )
    route = api.get(READ_PATH).mock(side_effect=[httpx.Response(401), httpx.Response(200)])
    assert base.read("GET", READ_PATH).status_code == 200
    assert tokens.call_count == 2
    assert route.calls[0].request.headers["Authorization"] == "Bearer old-token-1"
    assert route.calls[1].request.headers["Authorization"] == "Bearer new-token-2"


def test_auth_rejected_twice_raises(
    base: BaseClient, api: respx.MockRouter, token_route: respx.Route
) -> None:
    route = api.get(READ_PATH).mock(return_value=httpx.Response(401))
    with pytest.raises(AuthenticationError):
        base.read("GET", READ_PATH)
    assert route.call_count == 2
    assert token_route.call_count == 2


def test_rate_limit_uses_retry_after_and_stops_at_3(
    base: BaseClient, api: respx.MockRouter, token_route: respx.Route, sleeps: list[float]
) -> None:
    route = api.get(READ_PATH).mock(return_value=httpx.Response(429, headers={"Retry-After": "5"}))
    with pytest.raises(RateLimitExceededError):
        base.read("GET", READ_PATH)
    assert route.call_count == 3
    assert sleeps == [5.0, 5.0]


def test_read_5xx_retried_with_backoff(
    base: BaseClient, api: respx.MockRouter, token_route: respx.Route, sleeps: list[float]
) -> None:
    route = api.get(READ_PATH).mock(
        side_effect=[httpx.Response(503), httpx.Response(502), httpx.Response(200)]
    )
    assert base.read("GET", READ_PATH).status_code == 200
    assert route.call_count == 3
    assert len(sleeps) == 2
    assert 1.5 <= sleeps[0] <= 3.0
    assert 3.0 <= sleeps[1] <= 4.5


def test_read_5xx_gives_up_after_3(
    base: BaseClient, api: respx.MockRouter, token_route: respx.Route
) -> None:
    route = api.get(READ_PATH).mock(return_value=httpx.Response(500))
    with pytest.raises(EldoradoAPIError):
        base.read("GET", READ_PATH)
    assert route.call_count == 3


def test_read_network_error_retried(
    base: BaseClient, api: respx.MockRouter, token_route: respx.Route
) -> None:
    route = api.get(READ_PATH).mock(side_effect=[httpx.ConnectError("x"), httpx.Response(200)])
    assert base.read("GET", READ_PATH).status_code == 200
    assert route.call_count == 2


@pytest.mark.parametrize("status", [500, 502, 503, 504])
def test_write_5xx_not_retried(
    base: BaseClient, api: respx.MockRouter, token_route: respx.Route, status: int
) -> None:
    route = api.put(WRITE_PATH).mock(return_value=httpx.Response(status))
    with pytest.raises(WriteOutcomeUnknownError, match="NOT retried"):
        base.write("PUT", WRITE_PATH, json={})
    assert route.call_count == 1


@pytest.mark.parametrize("error", [httpx.ReadTimeout("t"), httpx.ConnectError("c")])
def test_write_network_error_not_retried(
    base: BaseClient, api: respx.MockRouter, token_route: respx.Route, error: Exception
) -> None:
    route = api.put(WRITE_PATH).mock(side_effect=error)
    with pytest.raises(WriteOutcomeUnknownError):
        base.write("PUT", WRITE_PATH, json={})
    assert route.call_count == 1


def test_404_maps_to_not_found(
    base: BaseClient, api: respx.MockRouter, token_route: respx.Route
) -> None:
    api.get(READ_PATH).mock(return_value=httpx.Response(404))
    with pytest.raises(ResourceNotFoundError):
        base.read("GET", READ_PATH)


def test_other_4xx_maps_to_api_error_with_status(
    base: BaseClient, api: respx.MockRouter, token_route: respx.Route
) -> None:
    api.put(WRITE_PATH).mock(return_value=httpx.Response(422, json={"error": "bad price"}))
    with pytest.raises(EldoradoAPIError, match="bad price") as info:
        base.write("PUT", WRITE_PATH, json={})
    assert info.value.http_status == 422


def test_redirect_is_an_error_not_success(base, api, token_route) -> None:  # type: ignore[no-untyped-def]
    import httpx
    import pytest

    from eldorado.core.exceptions import EldoradoAPIError

    route = api.put("/x").mock(return_value=httpx.Response(301, headers={"Location": "https://elsewhere/x"}))
    with pytest.raises(EldoradoAPIError, match="redirected"):
        base.write("PUT", "/x")
    assert route.call_count == 1


def test_token_redirect_is_an_auth_error(tokens, api) -> None:  # type: ignore[no-untyped-def]
    import httpx
    import pytest

    from eldorado.client.auth import TOKEN_PATH
    from eldorado.core.exceptions import AuthenticationError

    api.post(TOKEN_PATH).mock(return_value=httpx.Response(301, headers={"Location": "https://www.x/"}))
    with pytest.raises(AuthenticationError, match="redirected"):
        tokens.authorization_header()
