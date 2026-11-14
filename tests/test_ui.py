"""Local settings page: security guards, load, save (merge + validation), preview (no writes)."""

from __future__ import annotations

import json
import threading
import tomllib
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from eldorado.cli.ui import LocalServer, make_handler
from eldorado.client.base import BaseClient
from eldorado.client.offers import GAME_OFFERS_PATH, MY_OFFERS_PATH, OffersClient
from eldorado.services.dashboard import Dashboard

from .factories import market, offer_json, page

TOKEN = "test-token"


@pytest.fixture
def cfg(tmp_path: Path) -> Path:
    p = tmp_path / "bidding.toml"
    p.write_text('[[offers]]\nid = "other"\nmin_price = "1"\nenabled = true\n', encoding="utf-8")
    return p


@pytest.fixture
def server(base: BaseClient, api: respx.MockRouter, token_route: respx.Route, cfg: Path) -> Iterator[str]:
    mine = offer_json("o1", 1.00, game_id="59")
    api.get(MY_OFFERS_PATH).mock(return_value=httpx.Response(200, json=page([mine])))
    api.get(GAME_OFFERS_PATH).mock(return_value=httpx.Response(200, json=market(
        offer_json("c1", 0.95, user_id="rival", game_id="59"))))
    httpd = LocalServer(("127.0.0.1", 0), make_handler(Dashboard(OffersClient(base), cfg), TOKEN, 0))
    port = httpd.server_address[1]
    httpd.RequestHandlerClass = make_handler(Dashboard(OffersClient(base), cfg), TOKEN, port)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    httpd.shutdown()
    httpd.server_close()


def req(url: str, method: str = "GET", body: Any = None, token: str | None = TOKEN,
        host: str | None = None) -> tuple[int, Any]:
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("X-Token", token)
    if host:
        r.add_header("Host", host)
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if resp.headers.get_content_type() == "application/json" else raw)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def test_page_has_token_and_no_secret(server: str) -> None:
    from .conftest import ACCESS_TOKEN, CLIENT_SECRET

    status, body = req(server + "/", token=None)
    assert status == 200
    assert TOKEN.encode() in body
    assert CLIENT_SECRET.encode() not in body and ACCESS_TOKEN.encode() not in body


def test_api_needs_token_and_local_host(server: str) -> None:
    assert req(server + "/api/offers", token=None)[0] == 403
    assert req(server + "/api/offers", token="wrong")[0] == 403
    assert req(server + "/api/offers", host="evil.example:80")[0] == 403


def test_offers_rows(server: str) -> None:
    status, body = req(server + "/api/offers")
    assert status == 200
    (row,) = body["rows"]
    assert row["game"] == "Call of Duty Mobile" and row["package"] == "80 CP"
    assert row["price"] == "1.0" and row["lowest"] == "0.95" and row["min_price"] is None


def test_save_merges_and_writes_valid_toml(server: str, cfg: Path) -> None:
    rows = [{"id": "o1", "game": "CODM", "package": "80 CP", "min_price": "0.90",
             "max_price": "1.20", "enabled": True}]
    status, body = req(server + "/api/config", "POST", {"undercut": "0.01", "rows": rows})
    assert status == 200 and body["enabled"] == 2
    data = tomllib.loads(cfg.read_text(encoding="utf-8"))
    by_id = {o["id"]: o for o in data["offers"]}
    assert by_id["other"]["min_price"] == "1"            # rule not on the page is kept
    assert by_id["o1"]["min_price"] == "0.90" and by_id["o1"]["max_price"] == "1.20"


@pytest.mark.parametrize("row, fragment", [
    ({"min_price": "", "enabled": True}, "min price is required"),
    ({"min_price": "abc"}, "not a number"),
    ({"min_price": "2", "max_price": "1"}, "max_price"),
    ({"min_price": "-1"}, "greater than 0"),
])
def test_save_rejects_bad_values_and_keeps_file(server: str, cfg: Path, row: dict[str, Any], fragment: str) -> None:
    before = cfg.read_text(encoding="utf-8")
    status, body = req(server + "/api/config", "POST", {"rows": [{"id": "o1", **row}]})
    assert status == 400 and fragment in body["error"]
    assert cfg.read_text(encoding="utf-8") == before


def test_preview_sends_no_writes(server: str, cfg: Path, api: respx.MockRouter) -> None:
    req(server + "/api/config", "POST", {"rows": [{"id": "o1", "min_price": "0.50", "enabled": True}]})
    status, body = req(server + "/api/preview", "POST", {})
    assert status == 200
    d = next(x for x in body["decisions"] if x["id"] == "o1")
    assert d["action"] == "change" and d["target"] == "0.94"
    assert [c for c in api.calls if c.request.method == "PUT"] == []


def test_idle_connection_does_not_block_others(server: str) -> None:
    import socket

    idle = socket.create_connection(("127.0.0.1", int(server.rsplit(":", 1)[1])))  # like a browser preconnect
    try:
        assert req(server + "/", token=None)[0] == 200
    finally:
        idle.close()


def test_bot_switch_pauses_without_touching_rules(server: str, cfg: Path) -> None:
    status, body = req(server + "/api/config", "POST", {"paused": True, "rows": []})
    assert status == 200
    data = tomllib.loads(cfg.read_text(encoding="utf-8"))
    assert data["paused"] is True
    assert [o["id"] for o in data["offers"]] == ["other"]
    assert req(server + "/api/offers")[1]["paused"] is True


def test_orders_endpoint_needs_token(server: str) -> None:
    assert req(server + "/api/orders", token=None)[0] == 403
    status, body = req(server + "/api/orders")
    assert status == 200 and body == {"enabled": False}
