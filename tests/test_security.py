from __future__ import annotations

import logging

import httpx
import pytest
import respx

from eldorado.client.base import BaseClient
from eldorado.core.config import load_settings
from eldorado.core.exceptions import ConfigError, EldoradoAPIError
from eldorado.core.logging import REDACTED, RedactingFilter, redact

from .conftest import ACCESS_TOKEN, CLIENT_SECRET


def test_redact_masks_registered_secret(settings) -> None:  # type: ignore[no-untyped-def]
    assert CLIENT_SECRET not in redact(f"secret is {CLIENT_SECRET}")
    assert REDACTED in redact(f"secret is {CLIENT_SECRET}")


@pytest.mark.parametrize(
    "text",
    [
        "Authorization: Bearer abc.def.ghi",
        '{"Authorization": "Bearer abc.def.ghi"}',
        '{"accessToken": "abc.def.ghi", "expiresIn": 900}',
        '{"clientSecret": "abc.def.ghi"}',
    ],
)
def test_redact_masks_patterns(text: str) -> None:
    assert "abc.def.ghi" not in redact(text)


def test_exception_messages_are_masked(settings) -> None:  # type: ignore[no-untyped-def]
    exc = EldoradoAPIError(f"failed with {CLIENT_SECRET}")
    assert CLIENT_SECRET not in str(exc)


def test_logging_filter_masks(settings, caplog: pytest.LogCaptureFixture) -> None:  # type: ignore[no-untyped-def]
    logger = logging.getLogger("eldorado.test")
    logger.addFilter(RedactingFilter())
    with caplog.at_level(logging.WARNING, logger="eldorado.test"):
        logger.warning("secret=%s", CLIENT_SECRET)
    assert CLIENT_SECRET not in caplog.text


def test_access_token_masked_after_use(
    base: BaseClient, api: respx.MockRouter, token_route: respx.Route
) -> None:
    api.get("/mock/echo").mock(
        return_value=httpx.Response(400, text=f"bad token {ACCESS_TOKEN}")
    )
    with pytest.raises(EldoradoAPIError) as info:
        base.read("GET", "/mock/echo")
    assert ACCESS_TOKEN not in str(info.value)


def test_missing_settings_error_never_contains_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ELDORADO_CLIENT_SECRET", "only-secret-set-XYZ987")
    with pytest.raises(ConfigError, match="ELDORADO_CLIENT_ID") as info:
        load_settings()
    assert "only-secret-set-XYZ987" not in str(info.value)


def test_secret_not_in_settings_repr(settings) -> None:  # type: ignore[no-untyped-def]
    assert CLIENT_SECRET not in repr(settings)
    assert CLIENT_SECRET not in str(settings.model_dump())
