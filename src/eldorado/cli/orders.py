"""`eldorado orders ...` commands."""

from __future__ import annotations

import typer
from rich.markup import escape

from eldorado.cli.shared import console, fail, warn_credential_expiry
from eldorado.client import build_client
from eldorado.client.orders import OrdersClient
from eldorado.core.audit import AuditLogger
from eldorado.core.config import load_settings
from eldorado.core.exceptions import EldoradoError
from eldorado.services.orders import OrderService

orders_app = typer.Typer(help="Order commands.", no_args_is_help=True)


@orders_app.command("deliver")
def deliver(
    order_id: str = typer.Argument(..., help="Eldorado order id."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show the change, send nothing."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation prompt."),
) -> None:
    """Mark an order as delivered (PUT /api/orders/me/{orderId}/delivered)."""
    order_id = order_id.strip()
    if not order_id:
        raise typer.BadParameter("order id must not be empty")
    audit = AuditLogger()

    if dry_run:
        try:
            OrderService(None, audit).deliver(order_id, dry_run=True)
        except EldoradoError as exc:
            fail(exc)
        console.print(f"[cyan][DRY-RUN][/cyan] Would mark order {escape(order_id)} as delivered.")
        console.print("Nothing was sent.")
        return

    try:
        OrderService.ensure_live_deliver_allowed()
        settings = load_settings()
        warn_credential_expiry(settings)
    except EldoradoError as exc:
        fail(exc)

    console.print(f"About to mark order {escape(order_id)} as delivered on the LIVE account.")
    if not yes and not typer.confirm("Continue?", default=False):
        console.print("Cancelled. Nothing was sent.")
        raise typer.Exit(code=0)

    client = build_client(settings)
    try:
        result = OrderService(OrdersClient(client), audit).deliver(order_id, dry_run=False)
    except EldoradoError as exc:
        fail(exc)
    finally:
        client.close()
    console.print(
        f"[green]OK[/green] Order {escape(order_id)} marked delivered (HTTP {result.http_status})."
    )
