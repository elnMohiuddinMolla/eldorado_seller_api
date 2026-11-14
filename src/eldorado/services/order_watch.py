"""New-order alert (F18). Reads only: never changes an order.

Every poll reads the newest seller orders and the orders waiting for delivery (state Paid).
The first poll only learns what already exists, so starting the app never alerts on old orders.
Orders are kept in memory only and contain no buyer data (see models.order.SellerOrder).
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from eldorado.client.base import BaseClient
from eldorado.client.orders import list_seller_orders
from eldorado.core.bidding_config import GAME_NAMES  # noqa: F401 - re-exported (tests use it)
from eldorado.core.exceptions import EldoradoError
from eldorado.core.logging import redact
from eldorado.models.order import SellerOrder

POLL_SECONDS = 60
MAX_ALERTS = 50


def age_minutes(created: str, now: datetime | None = None) -> int | None:
    try:
        ts = datetime.fromisoformat(created.replace("Z", "+00:00"))
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return max(int(((now or datetime.now(timezone.utc)) - ts).total_seconds() // 60), 0)


class OrderWatcher:
    def __init__(
        self,
        base: BaseClient,
        *,
        on_new: Callable[[list[SellerOrder]], None] = lambda orders: None,
        log: Callable[[str], None] = lambda m: None,
    ) -> None:
        self._base = base
        self._on_new = on_new
        self._log = log
        self._lock = threading.Lock()
        self._seen: set[str] = set()
        self._seeded = False
        self._alerts: list[SellerOrder] = []  # newest first
        self._pending: list[SellerOrder] = []
        self._last_check: str | None = None
        self._error: str | None = None
        self._stop = threading.Event()

    def poll(self) -> list[SellerOrder]:
        """One check. Returns the orders that are new since the last check."""
        recent = list_seller_orders(self._base, page_size=20)
        pending = list_seller_orders(self._base, state="Paid", page_size=50)
        new: list[SellerOrder] = []
        with self._lock:
            for order in recent + pending:
                if order.id not in self._seen:
                    self._seen.add(order.id)
                    if self._seeded and all(o.id != order.id for o in new):
                        new.append(order)
            self._seeded = True
            self._pending = pending
            self._alerts = (new + self._alerts)[:MAX_ALERTS]
            self._last_check = time.strftime("%H:%M:%S")
            self._error = None
        if new:
            self._on_new(new)
        return new

    def snapshot(self) -> dict[str, Any]:
        now = datetime.now(timezone.utc)

        def row(o: SellerOrder) -> dict[str, Any]:
            return {**o.model_dump(), "age_minutes": age_minutes(o.created, now)}

        with self._lock:
            return {
                "last_check": self._last_check,
                "error": self._error,
                "pending": [row(o) for o in self._pending],
                "alerts": [row(o) for o in self._alerts],
            }

    def loop(self, interval: float = POLL_SECONDS) -> None:
        while not self._stop.is_set():
            try:
                self.poll()
            except EldoradoError as exc:
                with self._lock:
                    self._error = redact(str(exc))
                self._log(f"Order check failed: {redact(str(exc))}")
            except Exception as exc:  # noqa: BLE001 - read-only thread must never die silently
                with self._lock:
                    self._error = redact(f"{type(exc).__name__}: {exc}")
                self._log(f"Order check failed: {type(exc).__name__}")
            self._stop.wait(interval)

    def stop(self) -> None:
        self._stop.set()
