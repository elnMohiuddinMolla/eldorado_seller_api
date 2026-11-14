"""Console helpers shared by CLI commands."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import NoReturn

import typer
from rich.console import Console
from rich.markup import escape

from eldorado.client import build_client
from eldorado.client.base import BaseClient
from eldorado.core.config import EXPIRY_WARNING_DAYS, Settings, load_settings
from eldorado.core.exceptions import EldoradoError, WriteOutcomeUnknownError
from eldorado.core.logging import redact

console = Console()
err_console = Console(stderr=True, soft_wrap=True)


def fail(exc: EldoradoError) -> NoReturn:
    label = "Outcome unknown" if isinstance(exc, WriteOutcomeUnknownError) else "Error"
    err_console.print(f"[red]{label}:[/red] {escape(redact(str(exc)))}")
    raise typer.Exit(code=1)


def warn_credential_expiry(settings: Settings) -> None:
    days = settings.days_until_expiry()
    if days is None:
        return
    if days < 0:
        err_console.print(
            "[red]Warning:[/red] the credential expired according to "
            "ELDORADO_CREDENTIAL_EXPIRES. Generate a new one at Dashboard > Seller API."
        )
    elif days <= EXPIRY_WARNING_DAYS:
        err_console.print(
            f"[yellow]Warning:[/yellow] the credential expires in {days} day(s). "
            "Generate a new one, update .env, then revoke the old one."
        )


@contextmanager
def open_client() -> Iterator[BaseClient]:
    """Load .env, warn about credential expiry, and yield a client that is always closed."""
    settings = load_settings()
    warn_credential_expiry(settings)
    client = build_client(settings)
    try:
        yield client
    finally:
        client.close()
