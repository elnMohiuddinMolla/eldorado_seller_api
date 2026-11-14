"""Order endpoints."""

from __future__ import annotations

import logging
from urllib.parse import quote

from eldorado.client.base import BaseClient
from eldorado.core.bidding_config import GAME_NAMES
from eldorado.core.exceptions import EldoradoAPIError
from eldorado.models.order import SellerOrder

log = logging.getLogger("eldorado.client")


def deliver_path(order_id: str) -> str:
    # [Confirmed] (swagger): PUT /api/v1/orders/me/{orderId}/deliver, no request body.
    # The dashboard example (/api/orders/me/{id}/delivered) does not exist in the spec.
    return f"/api/v1/orders/me/{quote(order_id, safe='')}/deliver"


class OrdersClient:
    def __init__(self, base: BaseClient) -> None:
        self._base = base

    def mark_delivered(self, order_id: str) -> int:
        """Mark an order delivered. Returns the HTTP status."""
        response = self._base.write("PUT", deliver_path(order_id))
        return response.status_code


# [Confirmed] (swagger + live 2026-11-14): cursor paged, newest first.
SELLER_ORDERS_PATH = "/api/v1/orders/me/seller/orders"


def list_seller_orders(
    base: BaseClient, *, state: str | None = None, page_size: int = 20
) -> list[SellerOrder]:
    """Read-only. Orders without buyer data. An order with an unexpected shape is skipped
    (and counted in a warning) so one odd order never hides all the others."""
    params: dict[str, object] = {"displayFilter": "DisplaySellingOrders", "pageSize": page_size}
    if state:
        params["orderState"] = state
    response = base.read("GET", SELLER_ORDERS_PATH, params=params)
    try:
        data = response.json()
    except ValueError:
        raise EldoradoAPIError(f"GET {SELLER_ORDERS_PATH} did not return JSON.") from None
    results = data.get("results") if isinstance(data, dict) else None
    if not isinstance(results, list):
        raise EldoradoAPIError(f"GET {SELLER_ORDERS_PATH} returned an unexpected format.")
    orders: list[SellerOrder] = []
    skipped = 0
    for raw in results:
        try:
            if not isinstance(raw, dict):
                raise ValueError("not an object")
            orders.append(SellerOrder.from_api(raw, GAME_NAMES))
        except (ValueError, TypeError):
            skipped += 1
    if skipped:
        log.warning("GET %s: skipped %d order(s) with an unexpected format", SELLER_ORDERS_PATH, skipped)
    return orders
