from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import httpx
import respx

from eldorado.client.base import BaseClient
from eldorado.client.orders import SELLER_ORDERS_PATH
from eldorado.models.order import SellerOrder
from eldorado.services.order_watch import GAME_NAMES, OrderWatcher, age_minutes


def order_json(order_id: str, state: str = "Paid", game_id: str = "59", package: str = "5000 CP",
               created: str = "2026-11-14T10:00:00Z") -> dict[str, Any]:
    """Live shape of OrderPrivateViewModel (trimmed), including buyer fields the tool must drop."""
    return {
        "id": order_id, "sellerId": "me", "buyerId": "buyer-123", "buyerUsername": "SomeBuyer",
        "offerId": "o1", "purchaseQuantity": 2,
        "totalPrice": {"amount": 87.54, "currency": "USD"},
        "state": {"state": state, "createdDate": created},
        "createdDate": created,
        "orderOfferDetails": {
            "gameId": game_id, "gameCategoryTitle": "CP", "category": "TopUp",
            "offerAttributesProperties": [{"values": [package], "name": "CP", "id": "x",
                                           "attributeId": "call-of-duty-mobile-cp"}],
        },
        "conversationDetails": {"secret": "chat"},
    }


def cursor_page(*orders: dict[str, Any]) -> dict[str, Any]:
    return {"pageSize": 20, "results": list(orders), "cursor": None, "pageDirection": "Next",
            "previousPageCursor": None, "nextPageCursor": None}


def test_from_api_keeps_no_buyer_data() -> None:
    o = SellerOrder.from_api(order_json("a1"), GAME_NAMES)
    assert (o.game, o.package, o.quantity, o.total, o.state) == ("Call of Duty Mobile", "5000 CP", 2, "87.54", "Paid")
    dumped = json.dumps(o.model_dump())
    assert "SomeBuyer" not in dumped and "buyer-123" not in dumped and "chat" not in dumped


def test_unknown_game_falls_back_to_title() -> None:
    assert SellerOrder.from_api(order_json("a1", game_id="999"), GAME_NAMES).game == "CP"


def test_from_api_accepts_state_as_plain_string() -> None:
    """Live API may return state as a bare string instead of {state, createdDate} object.

    Regression for the warning "skipped N order(s) with an unexpected format" that fires
    when isinstance(state, dict) is False.  Both shapes must be parsed without skipping.
    """
    raw = order_json("a2", state="Completed")
    # Replace nested dict state with a plain string — the live variant that caused skips.
    raw["state"] = "Completed"
    o = SellerOrder.from_api(raw, GAME_NAMES)
    assert o.state == "Completed"
    assert o.id == "a2"


def test_from_api_rejects_missing_state() -> None:
    """state=None must still raise ValueError so the order is counted as skipped."""
    import pytest
    raw = order_json("a3")
    raw["state"] = None
    with pytest.raises((ValueError, TypeError)):
        SellerOrder.from_api(raw, GAME_NAMES)


def test_age_minutes() -> None:
    now = datetime(2026, 11, 14, 11, 30, tzinfo=timezone.utc)
    assert age_minutes("2026-11-14T10:00:00Z", now) == 90
    assert age_minutes("2026-11-14T09:58:14.4344569Z", now) == 91   # live format, 7 digits
    assert age_minutes("2026-11-14T09:58:14", now) == 91            # no zone: treated as UTC
    assert age_minutes("not a date", now) is None


def test_first_poll_does_not_alert_then_new_order_alerts_once(base: BaseClient, api: respx.MockRouter,
                                                              token_route: respx.Route) -> None:
    orders = {"recent": [order_json("old", state="Completed")], "paid": [order_json("waiting")]}

    def view(request: httpx.Request) -> httpx.Response:
        params = request.url.params
        assert params["displayFilter"] == "DisplaySellingOrders"
        key = "paid" if params.get("orderState") == "Paid" else "recent"
        return httpx.Response(200, json=cursor_page(*orders[key]))

    route = api.get(SELLER_ORDERS_PATH).mock(side_effect=view)
    alerts: list[list[SellerOrder]] = []
    w = OrderWatcher(base, on_new=alerts.append)

    assert w.poll() == []                                   # seeding: old orders never alert
    snap = w.snapshot()
    assert [o["id"] for o in snap["pending"]] == ["waiting"]

    orders["recent"].insert(0, order_json("fresh"))
    orders["paid"].insert(0, order_json("fresh"))
    new = w.poll()
    assert [o.id for o in new] == ["fresh"]                 # once, even though it is in both lists
    assert [o.id for o in alerts[0]] == ["fresh"]
    assert w.poll() == []                                   # not again
    assert [a["id"] for a in w.snapshot()["alerts"]] == ["fresh"]
    assert all(c.request.method == "GET" for c in route.calls)  # read-only


def test_loop_survives_errors(base: BaseClient, api: respx.MockRouter, token_route: respx.Route) -> None:
    api.get(SELLER_ORDERS_PATH).mock(return_value=httpx.Response(200, text="<html>", headers={"content-type": "text/html"}))
    w = OrderWatcher(base)

    def once(interval: float = 0) -> None:
        w.stop()

    w._stop.wait = lambda timeout=None: True  # type: ignore[method-assign]
    w._stop.set()
    w._stop.clear()
    calls = {"n": 0}
    original = w.poll

    def poll() -> list[SellerOrder]:
        calls["n"] += 1
        w.stop()
        return original()

    w.poll = poll  # type: ignore[method-assign]
    w.loop(interval=0)
    assert calls["n"] == 1
    assert "JSON" in str(w.snapshot()["error"])
