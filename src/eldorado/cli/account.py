"""`eldorado status online|offline` (F7)."""

from __future__ import annotations

import typer

from eldorado.cli.shared import console, fail, open_client
from eldorado.client.account import AccountClient
from eldorado.core.audit import AuditLogger
from eldorado.core.exceptions import EldoradoError
from eldorado.services.account import AccountService

status_app = typer.Typer(help="Seller online/offline status.", no_args_is_help=True)


def _set(online: bool, dry_run: bool, yes: bool) -> None:
    word = "online" if online else "offline"
    if dry_run:
        try:
            AccountService(None, AuditLogger()).set_online(online, dry_run=True)
        except EldoradoError as exc:
            fail(exc)
        console.print(f"[cyan][DRY-RUN][/cyan] Would switch seller status to {word}. Nothing was sent.")
        return
    if not yes and not typer.confirm(f"Switch your LIVE seller status to {word}?", default=False):
        console.print("Cancelled. Nothing was sent.")
        raise typer.Exit(code=0)
    try:
        with open_client() as base:
            AccountService(AccountClient(base), AuditLogger()).set_online(online, dry_run=False)
    except EldoradoError as exc:
        fail(exc)
    console.print(f"[green]OK[/green] Seller status is now {word}.")


@status_app.command("online")
def online(
    dry_run: bool = typer.Option(False, "--dry-run"),
    yes: bool = typer.Option(False, "--yes", "-y"),
) -> None:
    """Go online (PUT /api/offerUser/me/switchOnline)."""
    _set(True, dry_run, yes)


@status_app.command("offline")
def offline(
    dry_run: bool = typer.Option(False, "--dry-run"),
    yes: bool = typer.Option(False, "--yes", "-y"),
) -> None:
    """Go offline (PUT /api/offerUser/me/switchOffline)."""
    _set(False, dry_run, yes)
