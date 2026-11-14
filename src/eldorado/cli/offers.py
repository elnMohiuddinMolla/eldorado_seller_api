"""`eldorado offers ...` commands (TopUp offers only)."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

import typer
from rich.markup import escape
from rich.table import Table

from eldorado.cli.shared import console, fail, open_client
from eldorado.client.offers import OffersClient
from eldorado.core.audit import AuditLogger
from eldorado.core.exceptions import EldoradoError
from eldorado.services.offers import ItemResult, OfferService

offers_app = typer.Typer(help="TopUp offer commands.", no_args_is_help=True)

STATES = {"active": "Active", "paused": "Paused", "closed": "Closed", "offline": "Offline"}


@offers_app.command("list")
def list_offers(
    game: str | None = typer.Option(None, "--game", help="Eldorado gameId."),
    status: str | None = typer.Option(None, "--status", help="active, paused, closed or offline."),
    limit: int = typer.Option(50, "--limit", min=1, help="Maximum offers to show."),
) -> None:
    """Show your TopUp offers. Read-only."""
    state = None
    if status is not None:
        state = STATES.get(status.lower())
        if state is None:
            raise typer.BadParameter(f"--status must be one of {', '.join(STATES)}")
    try:
        with open_client() as base:
            offers = OfferService(OffersClient(base), AuditLogger()).list_mine(
                game_id=game, state=state, limit=limit
            )
    except EldoradoError as exc:
        fail(exc)

    table = Table(title=f"Your TopUp offers ({len(offers)})")
    for col in ("Offer id", "Game id", "Package", "Price", "Qty", "State"):
        table.add_column(col)
    for o in offers:
        table.add_row(o.id, o.game_id or "-", escape(o.label()),
                      f"{o.price.amount} {o.price.currency}", str(o.quantity or "-"), o.state or "-")
    console.print(table)


@offers_app.command("update")
def update(
    offer_id: str = typer.Option(..., "--id", help="Offer id from `eldorado offers list`."),
    price: str = typer.Option(..., "--price", help="New price per unit, e.g. 4.99."),
    allow_big_change: bool = typer.Option(False, "--allow-big-change", help="Allow over 50%."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show the change, send nothing."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation prompt."),
) -> None:
    """Change one offer's price."""
    try:
        new_price = Decimal(price)
    except InvalidOperation:
        raise typer.BadParameter("--price must be a number") from None
    if not new_price.is_finite():
        raise typer.BadParameter("--price must be a number (not NaN or Infinity)")
    try:
        with open_client() as base:
            service = OfferService(OffersClient(base), AuditLogger())
            change = service.plan_price(offer_id.strip(), new_price, allow_big_change=allow_big_change)
            tag = "[cyan][DRY-RUN][/cyan] Would update" if dry_run else "About to update"
            console.print(f"{tag} offer {escape(change.offer_id)} ({escape(change.label)}):")
            console.print(f"  Price: {change.before} -> {change.after} {change.currency} "
                          f"({change.percent:+.1f}%)")
            if dry_run:
                service.apply_price(change, dry_run=True)
                console.print("Nothing was sent.")
                return
            if not yes and not typer.confirm("Continue on the LIVE account?", default=False):
                console.print("Cancelled. Nothing was sent.")
                raise typer.Exit(code=0)
            service.apply_price(change, dry_run=False)
    except EldoradoError as exc:
        fail(exc)
    console.print("[green]OK[/green] Price updated.")


def _pause_resume(offer_ids: list[str], *, paused: bool, dry_run: bool, yes: bool) -> None:
    ids = [i.strip() for i in offer_ids if i.strip()]
    if not ids:
        raise typer.BadParameter("give at least one offer id")
    verb = "pause" if paused else "resume"
    if dry_run:
        console.print(f"[cyan][DRY-RUN][/cyan] Would {verb} {len(ids)} offer(s): {escape(', '.join(ids))}")
    else:
        console.print(f"About to {verb} {len(ids)} offer(s) on the LIVE account.")
        if len(ids) > 1:
            console.print(f"Pilot: {escape(ids[0])} goes first.")
        if not yes and not typer.confirm("Continue?", default=False):
            console.print("Cancelled. Nothing was sent.")
            raise typer.Exit(code=0)

    def confirm_rest() -> bool:
        return yes or typer.confirm(f"Pilot OK. {verb.title()} the other {len(ids) - 1}?", default=False)

    try:
        if dry_run:
            results = OfferService(None, AuditLogger()).set_paused(ids, paused=paused, dry_run=True)
        else:
            with open_client() as base:
                results = OfferService(OffersClient(base), AuditLogger()).set_paused(
                    ids, paused=paused, dry_run=False, confirm_rest=confirm_rest)
    except EldoradoError as exc:
        fail(exc)
    _summary(results)
    if any(r.outcome in ("failed", "unknown") for r in results):
        raise typer.Exit(code=1)


def _summary(results: list[ItemResult]) -> None:
    counts: dict[str, int] = {}
    for r in results:
        counts[r.outcome] = counts.get(r.outcome, 0) + 1
        if r.outcome in ("failed", "unknown"):
            console.print(f"[red]{r.outcome}[/red] {escape(r.offer_id)}: {escape(r.message or '')}")
    console.print("Summary: " + ", ".join(f"{k} {v}" for k, v in counts.items()))
    if counts.get("unknown"):
        console.print("[yellow]Outcome unknown: check the Eldorado dashboard. Nothing was retried.[/yellow]")


@offers_app.command("pause")
def pause(
    offer_ids: list[str] = typer.Argument(..., help="One or more offer ids."),
    dry_run: bool = typer.Option(False, "--dry-run"),
    yes: bool = typer.Option(False, "--yes", "-y"),
) -> None:
    """Pause offers. With several ids, the first is a pilot."""
    _pause_resume(offer_ids, paused=True, dry_run=dry_run, yes=yes)


@offers_app.command("resume")
def resume(
    offer_ids: list[str] = typer.Argument(..., help="One or more offer ids."),
    dry_run: bool = typer.Option(False, "--dry-run"),
    yes: bool = typer.Option(False, "--yes", "-y"),
) -> None:
    """Resume offers. With several ids, the first is a pilot."""
    _pause_resume(offer_ids, paused=False, dry_run=dry_run, yes=yes)
