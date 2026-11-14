"""Order endpoints."""

from __future__ import annotations

from urllib.parse import quote

from eldorado.client.base import BaseClient


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
