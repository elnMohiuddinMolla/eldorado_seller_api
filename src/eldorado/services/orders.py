"""Order business rules: dry-run, audit, and the gate for unconfirmed request details."""

from __future__ import annotations

from eldorado.client.orders import OrdersClient
from eldorado.core.audit import AuditLogger, record_unknown
from eldorado.core.exceptions import (
    EldoradoError,
    EndpointNotConfirmedError,
    WriteOutcomeUnknownError,
)
from eldorado.models.order import DeliverResult

# Swagger confirms PUT /api/v1/orders/me/{orderId}/deliver with no body, but the dashboard
# example shows a different path. Flip to True only when the user decides to enable it.
DELIVER_LIVE_ENABLED = False

ACTION_DELIVER = "order.deliver"


class OrderService:
    def __init__(self, client: OrdersClient | None, audit: AuditLogger) -> None:
        self._client = client
        self._audit = audit

    @staticmethod
    def ensure_live_deliver_allowed() -> None:
        if not DELIVER_LIVE_ENABLED:
            raise EndpointNotConfirmedError(
                "Live 'mark delivered' is disabled. Swagger and the dashboard example disagree "
                "on the path (see api-spec.md 4.4); it stays off until you enable it. "
                "--dry-run works."
            )

    def deliver(self, order_id: str, *, dry_run: bool) -> DeliverResult:
        result = DeliverResult(order_id=order_id, dry_run=dry_run)
        order_id = result.order_id
        after = {"status": "delivered"}

        if dry_run:
            self._audit.write(
                action=ACTION_DELIVER, entity_type="order", entity_id=order_id,
                after=after, outcome="dry_run", dry_run=True,
            )
            return result

        self.ensure_live_deliver_allowed()
        if self._client is None:
            raise RuntimeError("OrderService needs a client for live calls")

        try:
            status = self._client.mark_delivered(order_id)
        except WriteOutcomeUnknownError as exc:
            record_unknown(self._audit, exc, action=ACTION_DELIVER, entity_type="order",
                           entity_id=order_id, after=after)
            raise
        except EldoradoError as exc:
            self._audit.write(
                action=ACTION_DELIVER, entity_type="order", entity_id=order_id, after=after,
                outcome="failed", dry_run=False, http_status=exc.http_status, message=str(exc),
            )
            raise

        self._audit.write(
            action=ACTION_DELIVER, entity_type="order", entity_id=order_id, after=after,
            outcome="success", dry_run=False, http_status=status,
        )
        return result.model_copy(update={"http_status": status})
