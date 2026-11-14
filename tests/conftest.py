from __future__ import annotations

import os
from collections.abc import Iterator

import httpx
import pytest
import respx

from eldorado.client.auth import TOKEN_PATH, TokenManager
from eldorado.client.base import BaseClient
from eldorado.core.config import Settings

BASE_URL = "https://www.eldorado.gg"
CLIENT_ID = "test-client-id"
CLIENT_SECRET = "test-secret-DO-NOT-LEAK-9f8e7d"
ACCESS_TOKEN = "eyJ.test-access-token.abc123"


def token_json(token: str = ACCESS_TOKEN, expires_in: int = 900) -> dict[str, object]:
    return {"accessToken": token, "expiresIn": expires_in, "tokenType": "Bearer"}


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: os.PathLike[str]) -> None:
    """No real .env, no real ELDORADO_* variables, audit logs go to a temp dir."""
    for key in list(os.environ):
        if key.startswith("ELDORADO_"):
            monkeypatch.delenv(key)
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def settings() -> Settings:
    return Settings(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,  # type: ignore[arg-type]
        _env_file=None,  # type: ignore[call-arg]
    )


@pytest.fixture
def api() -> Iterator[respx.MockRouter]:
    """Every HTTP call is mocked. An unmocked call fails the test."""
    with respx.mock(base_url=BASE_URL, assert_all_called=False) as router:
        yield router


@pytest.fixture
def token_route(api: respx.MockRouter) -> respx.Route:
    return api.post(TOKEN_PATH).mock(return_value=httpx.Response(200, json=token_json()))


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def sleeps() -> list[float]:
    return []


@pytest.fixture
def http() -> Iterator[httpx.Client]:
    with httpx.Client(base_url=BASE_URL) as client:
        yield client


@pytest.fixture
def tokens(http: httpx.Client, settings: Settings, clock: FakeClock, sleeps: list[float]) -> TokenManager:
    return TokenManager(http, settings, clock=clock, sleep=sleeps.append)


@pytest.fixture
def base(http: httpx.Client, tokens: TokenManager, sleeps: list[float]) -> BaseClient:
    return BaseClient(http, tokens, sleep=sleeps.append)
