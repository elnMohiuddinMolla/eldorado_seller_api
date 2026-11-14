"""Regression tests for the 2026-11-14 project audit.

- An audit log that cannot be written must stop/pause the bot and never hide an unknown
  write outcome (else the next cycle sends the same write again).
- A pause saved mid-cycle stops the remaining writes.
- The page preview plans with the bot's memory and never changes it.
- Bad input from the page or the CLI is a clean error, not a crash.
"""

from __future__ import annotations

import http.client
import http.server
import json
import threading
import time
import tomllib
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

from eldorado.cli.main import app
from eldorado.cli.ui import LocalServer, make_handler
from eldorado.client.base import BaseClient
from eldorado.client.offers import GAME_OFFERS_PATH, MY_OFFERS_PATH, OffersClient, change_price_path
from eldorado.client.orders import SELLER_ORDERS_PATH, list_seller_orders
from eldorado.core.audit import AuditLogger
from eldorado.core.bidding_config import load_bidding_config, parse_bidding_config
from eldorado.core.config import load_settings
from eldorado.core.exceptions import ConfigError, PriceGuardError, WriteOutcomeUnknownError
from eldorado.services.bidding import Bidder, BidderMemory
from eldorado.services.bot_runner import BotRunner, set_paused
from eldorado.services.dashboard import Dashboard
from eldorado.services.offers import OfferService

from .conftest import CLIENT_ID, CLIENT_SECRET
from .factories import market, offer_json, page
from .test_order_watch import cursor_page, order_json


@pytest.fixture
def broken_audit(tmp_path: Path) -> AuditLogger:
    """The log path is a folder, so every write fails like a blocked or full disk."""
    path = tmp_path / "blocked.jsonl"
    path.mkdir()
    return AuditLogger(path)


@pytest.fixture
def cfg(tmp_path: Path) -> Path:
    p = tmp_path / "bidding.toml"
    p.write_text('paused = false\n[[offers]]\nid = "o1"\nmin_price = "0.50"\n', encoding="utf-8")
    return p


@pytest.fixture
def one_change(api: respx.MockRouter, token_route: respx.Route) -> respx.Route:
    api.get(MY_OFFERS_PATH).mock(return_value=httpx.Response(200, json=page([offer_json("o1", 1.00)])))
    api.get(GAME_OFFERS_PATH).mock(return_value=httpx.Response(200, json=market(
        offer_json("c1", 0.95, user_id="rival"))))
    return api.put(change_price_path("o1"))


def _paused(cfg: Path) -> bool:
    return bool(tomllib.loads(cfg.read_text(encoding="utf-8"))["paused"])


# --- audit log cannot be written ------------------------------------------------------------

@pytest.mark.parametrize("status", [200, 503])
def test_bot_pauses_when_audit_log_fails(one_change: respx.Route, base: BaseClient, cfg: Path,
                                         broken_audit: AuditLogger, status: int) -> None:
    one_change.mock(return_value=httpx.Response(status))
    runner = BotRunner(OffersClient(base), broken_audit, cfg)
    runner.run_once()
    runner.run_once()
    assert one_change.call_count == 1          # never sent again
    assert _paused(cfg) is True
    assert runner.status()["state"] == "paused"


def test_unknown_outcome_survives_audit_failure(one_change: respx.Route, base: BaseClient,
                                                broken_audit: AuditLogger) -> None:
    one_change.mock(return_value=httpx.Response(503))
    config = parse_bidding_config({"offers": [{"id": "o1", "min_price": "0.50"}]})
    with pytest.raises(WriteOutcomeUnknownError, match="audit log could not be written"):
        Bidder(OffersClient(base), broken_audit, config, sleep=lambda s: None).run_cycle(dry_run=False)


def test_manual_update_unknown_survives_audit_failure(one_change: respx.Route, base: BaseClient,
                                                      broken_audit: AuditLogger) -> None:
    one_change.mock(return_value=httpx.Response(503))
    service = OfferService(OffersClient(base), broken_audit)
    change = service.plan_price("o1", Decimal("0.99"), allow_big_change=False)
    with pytest.raises(WriteOutcomeUnknownError):
        service.apply_price(change, dry_run=False)
    assert one_change.call_count == 1


def test_bid_run_stops_when_audit_log_fails(monkeypatch: pytest.MonkeyPatch, one_change: respx.Route,
                                            tmp_path: Path) -> None:
    monkeypatch.setenv("ELDORADO_CLIENT_ID", CLIENT_ID)
    monkeypatch.setenv("ELDORADO_CLIENT_SECRET", CLIENT_SECRET)
    monkeypatch.setattr(time, "sleep", lambda s: None)
    (tmp_path / "logs" / "audit.jsonl").mkdir(parents=True)  # cwd is tmp_path
    (tmp_path / "bidding.toml").write_text('[[offers]]\nid = "o1"\nmin_price = "0.50"\n', encoding="utf-8")
    one_change.mock(return_value=httpx.Response(200))
    result = CliRunner().invoke(app, ["bid", "run", "--yes"])  # not --once: must stop by itself
    assert result.exit_code == 1, result.output
    assert one_change.call_count == 1


# --- pause mid-cycle -------------------------------------------------------------------------

def test_pause_mid_cycle_stops_remaining_writes(api: respx.MockRouter, token_route: respx.Route,
                                                base: BaseClient, tmp_path: Path) -> None:
    cfg = tmp_path / "bidding.toml"
    cfg.write_text('paused = false\n[[offers]]\nid = "o1"\nmin_price = "0.50"\n'
                   '[[offers]]\nid = "o2"\nmin_price = "0.50"\n', encoding="utf-8")
    api.get(MY_OFFERS_PATH).mock(return_value=httpx.Response(200, json=page([
        offer_json("o1", 1.00), offer_json("o2", 1.00, package="400 CP")])))
    api.get(GAME_OFFERS_PATH).mock(return_value=httpx.Response(200, json=market(
        offer_json("c1", 0.95, user_id="rival"), offer_json("c2", 0.95, user_id="rival", package="400 CP"))))

    def pilot_then_user_pauses(request: httpx.Request) -> httpx.Response:
        set_paused(cfg, True)  # the user clicks pause on the page while the cycle runs
        return httpx.Response(200)

    first = api.put(change_price_path("o1")).mock(side_effect=pilot_then_user_pauses)
    second = api.put(change_price_path("o2")).mock(return_value=httpx.Response(200))
    runner = BotRunner(OffersClient(base), AuditLogger(tmp_path / "a.jsonl"), cfg)
    runner.run_once()
    assert first.call_count == 1
    assert second.call_count == 0
    assert "1 not sent" in str(runner.status()["message"])


# --- preview uses the bot's memory ---------------------------------------------------------

def test_preview_uses_bot_memory_without_changing_it(api: respx.MockRouter, token_route: respx.Route,
                                                     base: BaseClient, tmp_path: Path) -> None:
    cfg = tmp_path / "bidding.toml"
    cfg.write_text('[[offers]]\nid = "o1"\nmin_price = "1.00"\nmax_price = "1.40"\n', encoding="utf-8")
    mine = offer_json("o1", 1.00)
    api.get(MY_OFFERS_PATH).mock(return_value=httpx.Response(200, json=page([mine])))
    api.get(GAME_OFFERS_PATH).mock(return_value=httpx.Response(200, json=market(mine)))  # we are #1

    fresh = Dashboard(OffersClient(base), cfg).preview()
    assert fresh[0]["action"] == "change"      # no memory: would search up to max_price

    memory = BidderMemory(held={"o1": True},
                          probe_blocked_until={"o1": time.monotonic() + 3600})
    with_bot = Dashboard(OffersClient(base), cfg, bot_memory=lambda: memory).preview()
    assert with_bot[0]["action"] == "keep"     # the bot is waiting, so it would not search
    assert "next search" in with_bot[0]["reason"]
    assert memory.held == {"o1": True} and memory.probing == set()


# --- bad input -------------------------------------------------------------------------------

@pytest.mark.parametrize("payload", [
    {"rows": [{"id": "o1", "min_price": ["1"]}]},
    {"rows": [{"id": "o1", "min_price": "1", "enabled": "yes"}]},
    {"rows": "o1"},
    {"paused": "false", "rows": []},
])
def test_dashboard_save_rejects_bad_types(base: BaseClient, cfg: Path, payload: dict[str, object]) -> None:
    before = cfg.read_text(encoding="utf-8")
    with pytest.raises(ConfigError):
        Dashboard(OffersClient(base), cfg).save(payload)
    assert cfg.read_text(encoding="utf-8") == before


def test_dashboard_save_accepts_number_prices(api: respx.MockRouter, token_route: respx.Route,
                                              base: BaseClient, cfg: Path) -> None:
    api.get(MY_OFFERS_PATH).mock(return_value=httpx.Response(200, json=page([offer_json("o1", 1.00)])))
    Dashboard(OffersClient(base), cfg).save({"rows": [{"id": "o1", "min_price": 0.75, "enabled": True}]})
    assert load_bidding_config(cfg).offers[0].min_price == Decimal("0.75")


@pytest.fixture
def server(base: BaseClient, cfg: Path) -> Iterator[int]:
    httpd = LocalServer(("127.0.0.1", 0), make_handler(Dashboard(OffersClient(base), cfg), "t", 0))
    port = httpd.server_address[1]
    httpd.RequestHandlerClass = make_handler(Dashboard(OffersClient(base), cfg), "t", port)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield port
    httpd.shutdown()
    httpd.server_close()


def _post(port: int, body: bytes, length: str) -> tuple[int, dict[str, object]]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    conn.putrequest("POST", "/api/config", skip_host=True)
    conn.putheader("Host", f"127.0.0.1:{port}")
    conn.putheader("X-Token", "t")
    conn.putheader("Content-Type", "application/json")
    conn.putheader("Content-Length", length)
    conn.endheaders(body)
    resp = conn.getresponse()
    data = json.loads(resp.read() or b"{}")
    conn.close()
    return resp.status, data


def test_server_answers_bad_input_with_json(server: int) -> None:
    body = json.dumps({"rows": [{"id": "o1", "min_price": {"x": 1}}]}).encode()
    status, data = _post(server, body, str(len(body)))
    assert status == 400 and "min price" in str(data["error"])
    assert _post(server, b"{}", "abc")[0] == 400
    assert _post(server, b"{}", "-5")[0] == 400


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", "sNaN"])
def test_cli_rejects_non_finite_price(value: str) -> None:
    result = CliRunner().invoke(app, ["offers", "update", "--id", "o1", "--price", value, "--dry-run"])
    assert result.exit_code == 2
    assert "Traceback" not in result.output


def test_service_rejects_non_finite_price(base: BaseClient, tmp_path: Path) -> None:
    with pytest.raises(PriceGuardError):
        OfferService(OffersClient(base), AuditLogger(tmp_path / "a.jsonl")).plan_price(
            "o1", Decimal("NaN"), allow_big_change=False)


def test_plain_http_base_url_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ELDORADO_CLIENT_ID", CLIENT_ID)
    monkeypatch.setenv("ELDORADO_CLIENT_SECRET", CLIENT_SECRET)
    monkeypatch.setenv("ELDORADO_BASE_URL", "http://www.eldorado.gg")
    with pytest.raises(ConfigError, match="ELDORADO_BASE_URL"):
        load_settings()


def test_one_odd_order_does_not_hide_the_others(api: respx.MockRouter, token_route: respx.Route,
                                                base: BaseClient) -> None:
    odd = order_json("bad")
    odd["totalPrice"] = "87.54"   # not an object
    api.get(SELLER_ORDERS_PATH).mock(return_value=httpx.Response(200, json=cursor_page(
        odd, {"no": "id"}, "text", order_json("good"))))
    assert [o.id for o in list_seller_orders(base)] == ["good"]


def test_closed_browser_connection_prints_no_traceback(capsys: pytest.CaptureFixture[str]) -> None:
    srv = LocalServer(("127.0.0.1", 0), http.server.BaseHTTPRequestHandler)
    try:
        for exc in (ConnectionAbortedError(10053, "aborted"), ConnectionResetError()):
            try:
                raise exc
            except ConnectionError:
                srv.handle_error(None, ("127.0.0.1", 1))
        assert capsys.readouterr().err == ""
        try:
            raise ValueError("real bug")
        except ValueError:
            srv.handle_error(None, ("127.0.0.1", 1))
        assert "real bug" in capsys.readouterr().err   # real errors still show
    finally:
        srv.server_close()
