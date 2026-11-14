"""Runs the auto bidder in a background thread for `eldorado app` (bot + settings page together).

- Settings are re-read from bidding.toml every cycle; the page's Bot switch is `paused`.
- `wake()` starts the next cycle now (called when the page saves), so a click acts at once.
- An unknown write outcome or an auth failure never stops the thread silently: the bot sets
  `paused = true` in bidding.toml and shows the error, and the user resumes from the page
  after checking the Eldorado dashboard. Nothing is retried.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from eldorado.client.offers import OffersClient
from eldorado.core.audit import AuditLogger
from eldorado.core.bidding_config import (
    CONFIG_WRITE_LOCK,
    BiddingConfig,
    load_bidding_config,
    save_bidding_config,
)
from eldorado.core.exceptions import (
    AuthenticationError,
    EldoradoError,
    WriteOutcomeUnknownError,
)
from eldorado.core.logging import redact
from eldorado.services.bidding import Bidder, CycleReport


@dataclass
class BotStatus:
    state: str = "starting"  # starting | paused | idle | running | error | stopped
    message: str = ""
    last_cycle: str | None = None
    last_changes: int = 0
    next_cycle: str | None = None


def set_paused(path: Path, paused: bool) -> None:
    with CONFIG_WRITE_LOCK:
        config = load_bidding_config(path, require_enabled=False)
        if config.paused != paused:
            save_bidding_config(config.model_copy(update={"paused": paused}), path)


class BotRunner:
    def __init__(
        self,
        offers: OffersClient,
        audit: AuditLogger,
        config_path: Path,
        *,
        on_report: Callable[[CycleReport], None] = lambda r: None,
        log: Callable[[str], None] = lambda m: None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._offers = offers
        self._audit = audit
        self._path = config_path
        self._on_report = on_report
        self._log = log
        self._clock = clock
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._status = BotStatus()
        self._bidder: Bidder | None = None

    def status(self) -> dict[str, object]:
        with self._lock:
            return asdict(self._status)

    def _set(self, **changes: object) -> None:
        with self._lock:
            for key, value in changes.items():
                setattr(self._status, key, value)

    def wake(self) -> None:
        self._wake.set()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()

    def _load(self) -> BiddingConfig:
        try:
            return load_bidding_config(self._path, require_enabled=False)
        except EldoradoError as exc:
            self._log(f"Settings not reloaded: {redact(str(exc))}")
            if self._bidder is not None:
                return self._bidder.config
            return BiddingConfig(paused=True)

    def run_once(self) -> BiddingConfig:
        config = self._load()
        if self._bidder is None:
            self._bidder = Bidder(self._offers, self._audit, config)
        else:
            self._bidder.set_config(config)
        stamp = time.strftime("%H:%M:%S", time.localtime(self._clock()))
        if config.paused:
            self._set(state="paused", message="Paused. Nothing is sent.", last_cycle=stamp)
            return config
        if not config.enabled_rules():
            self._set(state="idle", message="No offer is ON.", last_cycle=stamp)
            return config
        try:
            report = self._bidder.run_cycle(dry_run=False)
        except (WriteOutcomeUnknownError, AuthenticationError) as exc:
            text = redact(str(exc))
            set_paused(self._path, True)
            self._set(state="error", last_cycle=stamp,
                      message=f"Bot paused itself: {text} Check the Eldorado dashboard, then click RUN.")
            self._log(f"ERROR, bot paused: {text}")
            return config
        except EldoradoError as exc:
            self._set(state="running", last_cycle=stamp,
                      message=f"Last cycle skipped: {redact(str(exc))}")
            self._log(f"Cycle skipped: {redact(str(exc))}")
            return config
        changed = sum(1 for d in report.changes() if d.result == "success")
        failed = sum(1 for d in report.changes() if d.result == "failed")
        note = f"{len(config.enabled_rules())} offer(s) ON, {changed} price(s) changed"
        self._set(state="running", last_cycle=stamp, last_changes=changed,
                  message=note + (f", {failed} failed" if failed else "") + ".")
        self._on_report(report)
        return config

    def _fail_safe(self, exc: BaseException) -> BiddingConfig:
        """Unexpected error: it may have happened mid-write, so treat it like an unknown
        outcome. Pause in the file (if possible) and show it; never retry."""
        text = redact(f"{type(exc).__name__}: {exc}")
        try:
            set_paused(self._path, True)
        except Exception as pause_exc:  # noqa: BLE001 - keep the thread alive no matter what
            self._log(f"Could not write paused = true: {redact(str(pause_exc))}")
        stamp = time.strftime("%H:%M:%S", time.localtime(self._clock()))
        self._set(state="error", last_cycle=stamp,
                  message=f"Bot paused itself after an unexpected error ({text}). "
                          "Check the Eldorado dashboard, then click RUN.")
        self._log(f"ERROR, bot paused: {text}")
        return BiddingConfig(paused=True)

    def loop(self) -> None:
        while not self._stop.is_set():
            try:
                config = self.run_once()
            except Exception as exc:  # noqa: BLE001 - the bot thread must never die silently
                config = self._fail_safe(exc)
            wait = config.interval_seconds
            self._set(next_cycle=time.strftime(
                "%H:%M:%S", time.localtime(self._clock() + wait)))
            self._wake.wait(wait)
            self._wake.clear()
        self._set(state="stopped", message="Bot stopped.", next_cycle=None)
