from __future__ import annotations

import threading
import tomllib
from pathlib import Path

import httpx
import pytest
import respx

from eldorado.client.base import BaseClient
from eldorado.client.offers import GAME_OFFERS_PATH, MY_OFFERS_PATH, OffersClient, change_price_path
from eldorado.core.audit import AuditLogger
from eldorado.services.bot_runner import BotRunner, set_paused

from .factories import market, offer_json, page


@pytest.fixture
def cfg(tmp_path: Path) -> Path:
    p = tmp_path / "bidding.toml"
    p.write_text('paused = false\n[[offers]]\nid = "o1"\nmin_price = "0.50"\n', encoding="utf-8")
    return p


@pytest.fixture
def mocked(api: respx.MockRouter, token_route: respx.Route) -> respx.Route:
    api.get(MY_OFFERS_PATH).mock(return_value=httpx.Response(200, json=page([offer_json("o1", 1.00)])))
    api.get(GAME_OFFERS_PATH).mock(return_value=httpx.Response(200, json=market(
        offer_json("c1", 0.95, user_id="rival"))))
    return api.put(change_price_path("o1"))


def _runner(base: BaseClient, cfg: Path, tmp_path: Path) -> BotRunner:
    return BotRunner(OffersClient(base), AuditLogger(tmp_path / "a.jsonl"), cfg)


def test_paused_sends_nothing(mocked: respx.Route, base: BaseClient, cfg: Path, tmp_path: Path) -> None:
    set_paused(cfg, True)
    runner = _runner(base, cfg, tmp_path)
    runner.run_once()
    assert mocked.call_count == 0
    assert runner.status()["state"] == "paused"


def test_running_changes_price(mocked: respx.Route, base: BaseClient, cfg: Path, tmp_path: Path) -> None:
    mocked.mock(return_value=httpx.Response(200))
    runner = _runner(base, cfg, tmp_path)
    runner.run_once()
    assert mocked.call_count == 1
    assert runner.status()["last_changes"] == 1


def test_unknown_outcome_pauses_bot_in_file(mocked: respx.Route, base: BaseClient, cfg: Path, tmp_path: Path) -> None:
    mocked.mock(return_value=httpx.Response(503))
    runner = _runner(base, cfg, tmp_path)
    runner.run_once()
    assert mocked.call_count == 1                       # not retried
    assert tomllib.loads(cfg.read_text(encoding="utf-8"))["paused"] is True
    assert runner.status()["state"] == "error"
    runner.run_once()                                   # next cycle: paused, no write
    assert mocked.call_count == 1


def test_bad_settings_keep_last_good(mocked: respx.Route, base: BaseClient, cfg: Path, tmp_path: Path) -> None:
    set_paused(cfg, True)
    runner = _runner(base, cfg, tmp_path)
    runner.run_once()
    cfg.write_text("this is not toml [", encoding="utf-8")
    runner.run_once()
    assert runner.status()["state"] == "paused"
    assert mocked.call_count == 0


def test_bad_settings_at_start_mean_paused(mocked: respx.Route, base: BaseClient, cfg: Path, tmp_path: Path) -> None:
    cfg.write_text("broken [", encoding="utf-8")
    runner = _runner(base, cfg, tmp_path)
    runner.run_once()
    assert runner.status()["state"] == "paused"
    assert mocked.call_count == 0


def test_wake_runs_next_cycle_now_and_stop_ends_loop(mocked: respx.Route, base: BaseClient,
                                                     cfg: Path, tmp_path: Path) -> None:
    set_paused(cfg, True)
    mocked.mock(return_value=httpx.Response(200))
    runner = _runner(base, cfg, tmp_path)
    thread = threading.Thread(target=runner.loop, daemon=True)
    thread.start()
    for _ in range(100):
        if runner.status()["state"] == "paused":
            break
        threading.Event().wait(0.05)
    set_paused(cfg, False)
    runner.wake()                                       # what a page Save does
    for _ in range(100):
        if mocked.call_count:
            break
        threading.Event().wait(0.05)
    assert mocked.call_count == 1                       # did not wait 300 seconds
    runner.stop()
    thread.join(timeout=5)
    assert not thread.is_alive()
    assert runner.status()["state"] == "stopped"


def test_window_is_told_each_state_change_once(mocked: respx.Route, base: BaseClient, cfg: Path,
                                               tmp_path: Path) -> None:
    mocked.mock(return_value=httpx.Response(200))
    seen: list[str] = []
    runner = BotRunner(OffersClient(base), AuditLogger(tmp_path / "a.jsonl"), cfg,
                       on_state=lambda state, message: seen.append(state))
    set_paused(cfg, True)
    runner.run_once()
    runner.run_once()                 # still paused: no new line
    set_paused(cfg, False)
    runner.run_once()                 # RUN clicked
    runner.run_once()                 # still running: no new line
    set_paused(cfg, True)
    runner.run_once()
    assert seen == ["paused", "running", "paused"]
