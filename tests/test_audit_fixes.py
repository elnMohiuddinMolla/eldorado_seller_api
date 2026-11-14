"""Tests for the 2026-11-14 audit fixes: silent bot death, double bot, file write lock,
non-JSON responses, and HTTP status in the audit log."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from typer.testing import CliRunner

from eldorado.cli.main import app
from eldorado.client.base import BaseClient
from eldorado.client.offers import GAME_OFFERS_PATH, MY_OFFERS_PATH, OffersClient, change_price_path
from eldorado.core.audit import AuditLogger
from eldorado.core.bidding_config import BiddingConfig, OfferRule
from eldorado.core.exceptions import EldoradoAPIError
from eldorado.core.instance_lock import BotAlreadyRunningError, BotLock
from eldorado.services.bidding import Bidder
from eldorado.services.bot_runner import BotRunner

from .conftest import CLIENT_ID, CLIENT_SECRET
from .factories import market, offer_json, page

runner = CliRunner()


# ---------- 1: HTML instead of JSON is an API error, not a crash ----------

def test_html_200_is_an_api_error(base: BaseClient, api: respx.MockRouter, token_route: respx.Route) -> None:
    api.get(MY_OFFERS_PATH).mock(return_value=httpx.Response(
        200, text="<html>Just a moment...</html>", headers={"content-type": "text/html"}))
    with pytest.raises(EldoradoAPIError, match="not JSON"):
        OffersClient(base).list_mine()


def test_bot_thread_survives_unexpected_error_and_pauses(base: BaseClient, api: respx.MockRouter,
                                                         token_route: respx.Route, tmp_path: Path) -> None:
    cfg = tmp_path / "bidding.toml"
    cfg.write_text('paused = false\n[[offers]]\nid = "o1"\nmin_price = "0.5"\n', encoding="utf-8")
    bot = BotRunner(OffersClient(base), AuditLogger(tmp_path / "a.jsonl"), cfg)

    def boom() -> BiddingConfig:
        bot.stop()       # so the loop ends after this one iteration
        raise KeyError("something nobody expected")

    bot.run_once = boom  # type: ignore[method-assign]
    bot.loop()
    status = bot.status()
    assert status["state"] == "stopped"           # loop ended normally, did not crash
    assert tomllib.loads(cfg.read_text(encoding="utf-8"))["paused"] is True


def test_fail_safe_message_is_shown(base: BaseClient, tmp_path: Path) -> None:
    cfg = tmp_path / "bidding.toml"
    cfg.write_text('paused = false\n', encoding="utf-8")
    bot = BotRunner(OffersClient(base), AuditLogger(tmp_path / "a.jsonl"), cfg)
    bot._fail_safe(ValueError("bad"))
    assert bot.status()["state"] == "error"
    assert "ValueError" in str(bot.status()["message"])


# ---------- 2: only one live bot ----------

def test_second_lock_is_refused(tmp_path: Path) -> None:
    with BotLock(tmp_path / "bot.lock"):
        with pytest.raises(BotAlreadyRunningError):
            BotLock(tmp_path / "bot.lock").acquire()
    BotLock(tmp_path / "bot.lock").acquire()      # free again after release


def test_bid_run_refuses_when_another_bot_runs(api: respx.MockRouter, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ELDORADO_CLIENT_ID", CLIENT_ID)
    monkeypatch.setenv("ELDORADO_CLIENT_SECRET", CLIENT_SECRET)
    Path("bidding.toml").write_text('[[offers]]\nid = "o1"\nmin_price = "0.5"\n', encoding="utf-8")
    with BotLock():                               # logs/bot.lock in the test's cwd
        result = runner.invoke(app, ["bid", "run", "--once", "--yes"])
    assert result.exit_code == 1
    assert "Another bot is already running" in result.output
    assert len(api.calls) == 0


def test_bid_run_dry_run_works_next_to_a_bot(api: respx.MockRouter, token_route: respx.Route,
                                             monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ELDORADO_CLIENT_ID", CLIENT_ID)
    monkeypatch.setenv("ELDORADO_CLIENT_SECRET", CLIENT_SECRET)
    Path("bidding.toml").write_text('[[offers]]\nid = "o1"\nmin_price = "0.5"\n', encoding="utf-8")
    api.get(MY_OFFERS_PATH).mock(return_value=httpx.Response(200, json=page([offer_json("o1", 1.0)])))
    api.get(GAME_OFFERS_PATH).mock(return_value=httpx.Response(200, json=market()))
    with BotLock():
        result = runner.invoke(app, ["bid", "run", "--once", "--dry-run"])
    assert result.exit_code == 0, result.output


def test_unexpected_error_in_cli_cycle_stops_as_unknown(api: respx.MockRouter, token_route: respx.Route,
                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    import eldorado.cli.bid as bid_cli

    monkeypatch.setenv("ELDORADO_CLIENT_ID", CLIENT_ID)
    monkeypatch.setenv("ELDORADO_CLIENT_SECRET", CLIENT_SECRET)
    Path("bidding.toml").write_text('[[offers]]\nid = "o1"\nmin_price = "0.5"\n', encoding="utf-8")

    def boom(self: Any, *, dry_run: bool) -> Any:
        raise KeyError("unexpected")

    monkeypatch.setattr(bid_cli.Bidder, "run_cycle", boom)
    result = runner.invoke(app, ["bid", "run", "--yes"])
    assert result.exit_code == 1
    assert "unknown outcome" in result.output or "Outcome unknown" in result.output


# ---------- 6: HTTP status is in the audit log ----------

def test_bid_success_records_http_status(base: BaseClient, api: respx.MockRouter,
                                         token_route: respx.Route, tmp_path: Path) -> None:
    api.get(MY_OFFERS_PATH).mock(return_value=httpx.Response(200, json=page([offer_json("o1", 1.0)])))
    api.get(GAME_OFFERS_PATH).mock(return_value=httpx.Response(200, json=market(
        offer_json("c1", 0.95, user_id="rival"))))
    api.put(change_price_path("o1")).mock(return_value=httpx.Response(204))
    audit = tmp_path / "a.jsonl"
    config = BiddingConfig(offers=[OfferRule(id="o1", min_price=0.5)])  # type: ignore[arg-type]
    Bidder(OffersClient(base), AuditLogger(audit), config, sleep=lambda s: None).run_cycle(dry_run=False)
    record = json.loads(audit.read_text(encoding="utf-8").splitlines()[-1])
    assert record["outcome"] == "success" and record["http_status"] == 204
