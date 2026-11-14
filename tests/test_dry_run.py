from __future__ import annotations

import json
from typing import Any
from pathlib import Path

import respx
from typer.testing import CliRunner

from eldorado.cli.main import app
from eldorado.core.audit import AuditLogger
from eldorado.services.orders import OrderService

runner = CliRunner()


def test_service_dry_run_sends_nothing(api: respx.MockRouter, tmp_path: Path) -> None:
    audit_path = tmp_path / "a.jsonl"
    result = OrderService(None, AuditLogger(audit_path)).deliver("ABC123", dry_run=True)
    assert result.dry_run is True
    assert len(api.calls) == 0
    record = json.loads(audit_path.read_text(encoding="utf-8"))
    assert record["outcome"] == "dry_run"
    assert record["dry_run"] is True


def test_cli_deliver_dry_run_sends_nothing_and_needs_no_credentials(api: respx.MockRouter) -> None:
    result = runner.invoke(app, ["orders", "deliver", "ABC123", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "[DRY-RUN] Would mark order ABC123 as delivered" in result.output
    assert len(api.calls) == 0
    record = json.loads(Path("logs/audit.jsonl").read_text(encoding="utf-8"))
    assert record["entity_id"] == "ABC123"
    assert record["outcome"] == "dry_run"


WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _writes(api: respx.MockRouter) -> list[object]:
    from eldorado.client.auth import TOKEN_PATH

    return [c for c in api.calls
            if c.request.method in WRITE_METHODS and c.request.url.path != TOKEN_PATH]


def _creds(monkeypatch: object) -> None:
    from .conftest import CLIENT_ID, CLIENT_SECRET

    monkeypatch.setenv("ELDORADO_CLIENT_ID", CLIENT_ID)  # type: ignore[attr-defined]
    monkeypatch.setenv("ELDORADO_CLIENT_SECRET", CLIENT_SECRET)  # type: ignore[attr-defined]


def test_cli_status_dry_run_sends_nothing(api: respx.MockRouter) -> None:
    for word in ("online", "offline"):
        result = runner.invoke(app, ["status", word, "--dry-run"])
        assert result.exit_code == 0, result.output
    assert len(api.calls) == 0


def test_cli_pause_resume_dry_run_sends_nothing(api: respx.MockRouter) -> None:
    for cmd in ("pause", "resume"):
        result = runner.invoke(app, ["offers", cmd, "a", "b", "--dry-run"])
        assert result.exit_code == 0, result.output
    assert len(api.calls) == 0


def test_cli_offer_update_dry_run_sends_no_writes(api: respx.MockRouter, token_route: respx.Route,
                                                  monkeypatch: object) -> None:
    import httpx

    from eldorado.client.offers import MY_OFFERS_PATH

    from .factories import offer_json, page

    _creds(monkeypatch)
    api.get(MY_OFFERS_PATH).mock(return_value=httpx.Response(200, json=page([offer_json("o1", 10.0)])))
    result = runner.invoke(app, ["offers", "update", "--id", "o1", "--price", "9.50", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "10.0 -> 9.50" in result.output
    assert _writes(api) == []


def test_cli_bid_dry_run_sends_no_writes(api: respx.MockRouter, token_route: respx.Route,
                                         monkeypatch: object) -> None:
    import httpx

    from eldorado.client.offers import GAME_OFFERS_PATH, MY_OFFERS_PATH

    from .factories import market, offer_json, page

    _creds(monkeypatch)
    Path("bidding.toml").write_text('[[offers]]\nid = "o1"\nmin_price = "0.50"\nnote = "CODM 80 CP"\n',
                                    encoding="utf-8")
    api.get(MY_OFFERS_PATH).mock(return_value=httpx.Response(200, json=page([offer_json("o1", 1.00)])))
    api.get(GAME_OFFERS_PATH).mock(return_value=httpx.Response(200, json=market(
        offer_json("o1", 1.00), offer_json("c1", 0.95, user_id="rival"))))
    result = runner.invoke(app, ["bid", "run", "--once", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "would update" in result.output and "0.94" in result.output
    assert _writes(api) == []
    record = json.loads(Path("logs/audit.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert record["action"] == "offer.bid" and record["outcome"] == "dry_run"


def test_cli_bid_live_needs_confirmation(api: respx.MockRouter, monkeypatch: object) -> None:
    _creds(monkeypatch)
    Path("bidding.toml").write_text('[[offers]]\nid = "o1"\nmin_price = "0.50"\n', encoding="utf-8")
    result = runner.invoke(app, ["bid", "run", "--once"], input="n\n")
    assert result.exit_code == 0
    assert "Cancelled" in result.output
    assert len(api.calls) == 0


def test_cli_bid_reads_settings_every_cycle_and_honors_pause(
        api: respx.MockRouter, token_route: respx.Route, monkeypatch: Any) -> None:
    """Cycle 1 runs; then the page pauses the bot; cycle 2 sends nothing; then stop."""
    import httpx

    import eldorado.cli.bid as bid_cli
    from eldorado.client.offers import GAME_OFFERS_PATH, MY_OFFERS_PATH, change_price_path

    from .factories import market, offer_json, page

    _creds(monkeypatch)
    cfg = Path("bidding.toml")
    cfg.write_text('[[offers]]\nid = "o1"\nmin_price = "0.50"\n', encoding="utf-8")
    api.get(MY_OFFERS_PATH).mock(return_value=httpx.Response(200, json=page([offer_json("o1", 1.00)])))
    api.get(GAME_OFFERS_PATH).mock(return_value=httpx.Response(200, json=market(
        offer_json("c1", 0.95, user_id="rival"))))
    put = api.put(change_price_path("o1")).mock(return_value=httpx.Response(200))
    sleeps = {"n": 0}

    def fake_sleep(seconds: float) -> None:
        sleeps["n"] += 1
        if sleeps["n"] == 1:
            cfg.write_text('paused = true\n[[offers]]\nid = "o1"\nmin_price = "0.50"\n', encoding="utf-8")
        else:
            raise KeyboardInterrupt

    monkeypatch.setattr(bid_cli.time, "sleep", fake_sleep)
    result = runner.invoke(app, ["bid", "run", "--yes"])
    assert result.exit_code == 0, result.output
    assert put.call_count == 1                     # only the first cycle wrote
    assert "PAUSED" in result.output
