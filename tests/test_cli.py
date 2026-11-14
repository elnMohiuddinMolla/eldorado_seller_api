from __future__ import annotations

from datetime import date, timedelta

import httpx
import pytest
import respx
from typer.testing import CliRunner

from eldorado.cli.main import app
from eldorado.client.auth import TOKEN_PATH

from .conftest import ACCESS_TOKEN, CLIENT_ID, CLIENT_SECRET

runner = CliRunner()


@pytest.fixture
def creds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ELDORADO_CLIENT_ID", CLIENT_ID)
    monkeypatch.setenv("ELDORADO_CLIENT_SECRET", CLIENT_SECRET)


@pytest.mark.usefixtures("creds")
def test_auth_check_ok_and_never_prints_token(token_route: respx.Route) -> None:
    result = runner.invoke(app, ["auth", "check"])
    assert result.exit_code == 0, result.output
    assert "Token received" in result.output
    assert ACCESS_TOKEN not in result.output
    assert CLIENT_SECRET not in result.output
    assert token_route.call_count == 1


@pytest.mark.usefixtures("creds")
def test_auth_check_rejected(api: respx.MockRouter) -> None:
    api.post(TOKEN_PATH).mock(return_value=httpx.Response(401))
    result = runner.invoke(app, ["auth", "check"])
    assert result.exit_code == 1
    assert "revoked or expired" in result.output
    assert CLIENT_SECRET not in result.output


def test_auth_check_without_env(api: respx.MockRouter) -> None:
    result = runner.invoke(app, ["auth", "check"])
    assert result.exit_code == 1
    assert "ELDORADO_CLIENT_ID" in result.output
    assert len(api.calls) == 0


@pytest.mark.usefixtures("creds")
def test_expiry_warning(monkeypatch: pytest.MonkeyPatch, token_route: respx.Route) -> None:
    soon = (date.today() + timedelta(days=3)).isoformat()
    monkeypatch.setenv("ELDORADO_CREDENTIAL_EXPIRES", soon)
    result = runner.invoke(app, ["auth", "check"])
    assert result.exit_code == 0
    assert "expires in 3 day(s)" in result.output


@pytest.mark.usefixtures("creds")
def test_live_deliver_is_blocked_before_any_request(api: respx.MockRouter) -> None:
    result = runner.invoke(app, ["orders", "deliver", "ABC123", "--yes"])
    assert result.exit_code == 1
    assert "Live 'mark delivered' is disabled" in result.output
    assert len(api.calls) == 0


def test_eldorado_home_moves_files_to_project_folder(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from pathlib import Path

    home = tmp_path / "project"
    home.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    monkeypatch.setenv("ELDORADO_HOME", str(home))
    result = runner.invoke(app, ["orders", "deliver", "X1", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert (Path(home) / "logs" / "audit.jsonl").exists()
    assert not (elsewhere / "logs").exists()


def test_bad_eldorado_home_is_an_error(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("ELDORADO_HOME", str(tmp_path / "missing"))
    result = runner.invoke(app, ["orders", "deliver", "X1", "--dry-run"])
    assert result.exit_code == 1
