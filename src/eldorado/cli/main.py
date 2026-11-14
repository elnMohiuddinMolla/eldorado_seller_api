"""CLI entry point: `eldorado ...`."""

from __future__ import annotations

import os
from pathlib import Path

import typer
from rich.markup import escape

from eldorado.cli.account import status_app
from eldorado.cli.bid import bid_app
from eldorado.cli.offers import offers_app
from eldorado.cli.orders import orders_app
from eldorado.cli.ui import app_cmd, ui
from eldorado.cli.shared import console, err_console, fail, warn_credential_expiry
from eldorado.client import build_client
from eldorado.core.config import load_settings
from eldorado.core.exceptions import EldoradoError
from eldorado.core.logging import setup_logging

app = typer.Typer(
    name="eldorado",
    help="Eldorado.gg Seller API tool. No sandbox exists: every live write changes real data.",
    no_args_is_help=True,
)
auth_app = typer.Typer(help="Credential and token checks.", no_args_is_help=True)
app.add_typer(auth_app, name="auth")
app.add_typer(offers_app, name="offers")
app.add_typer(orders_app, name="orders")
app.add_typer(status_app, name="status")
app.add_typer(bid_app, name="bid")
app.command("ui")(ui)
app.command("app")(app_cmd)


@app.callback()
def _root() -> None:
    setup_logging()
    _go_home()


def _go_home() -> None:
    """ELDORADO_HOME (set by bin/eldorado.cmd) makes .env, bidding.toml and logs/ resolve
    to the project folder, so `eldorado` works from any directory."""
    home = os.environ.get("ELDORADO_HOME", "").strip()
    if not home:
        return
    path = Path(home).expanduser()
    if not path.is_dir():
        err_console.print(f"[red]ELDORADO_HOME is not a folder:[/red] {escape(str(path))}")
        raise typer.Exit(code=1)
    os.chdir(path)


@auth_app.command("check")
def auth_check() -> None:
    """Request an access token to verify the credentials in .env. Changes nothing."""
    try:
        settings = load_settings()
        warn_credential_expiry(settings)
        client = build_client(settings)
        try:
            seconds = int(client.check_token())
        finally:
            client.close()
    except EldoradoError as exc:
        fail(exc)
    console.print(f"[green]OK[/green] Token received. Valid for about {seconds} seconds.")
    console.print(f"Client ID: {escape(settings.client_id)}")
