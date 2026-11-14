"""Order endpoints."""

from __future__ import annotations

from urllib.parse import quote

from eldorado.client.base import BaseClient
from eldorado.core.exceptions import EldoradoAPIError


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


def list_seller_orders(base: BaseClient, *, state: str | None = None, page_size: int = 20) -> list[dict[str, object]]:
    """Read-only. Raw OrderPrivateViewModel dicts (the caller keeps only what it needs)."""
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
    return [r for r in results if isinstance(r, dict)]
