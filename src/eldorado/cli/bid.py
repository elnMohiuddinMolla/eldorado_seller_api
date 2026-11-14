"""`eldorado bid run`: the auto bidder (F16)."""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

import typer
from rich.markup import escape
from rich.table import Table

from eldorado.cli.shared import console, err_console, fail, open_client
from eldorado.client.offers import OffersClient
from eldorado.core.audit import AuditLogger
from eldorado.core.bidding_config import DEFAULT_BIDDING_PATH, MIN_INTERVAL_SECONDS, load_bidding_config
from eldorado.core.exceptions import (
    AuditLogError,
    AuthenticationError,
    EldoradoError,
    WriteOutcomeUnknownError,
)
from eldorado.core.instance_lock import BotLock
from eldorado.core.logging import redact
from eldorado.services.bidding import Bidder, CycleReport

bid_app = typer.Typer(help="Auto bidding for TopUp offers.", no_args_is_help=True)

RESULT_STYLE = {
    "success": "[green]updated[/green]", "dry_run": "[cyan]would update[/cyan]",
    "failed": "[red]failed[/red]", "unknown": "[red]UNKNOWN[/red]", "not_sent": "[yellow]not sent[/yellow]",
}


def _print_report(report: CycleReport) -> None:
    table = Table(title=f"Bid cycle {datetime.now():%H:%M:%S}")
    for col in ("Offer", "Current", "Lowest other", "Target", "Action", "Why"):
        table.add_column(col)
    for d in report.decisions:
        if d.kind == "change":
            action = RESULT_STYLE.get(d.result, d.result) + (" (pilot)" if d.pilot else "")
        else:
            action = d.kind
        table.add_row(
            escape(d.label), str(d.current or "-"), str(d.lowest_competitor or "-"),
            str(d.target or "-"), action, escape(d.reason),
        )
    console.print(table)


@bid_app.command("run")
def run(
    config_path: Path = typer.Option(DEFAULT_BIDDING_PATH, "--config", help="Bidding config file."),
    once: bool = typer.Option(False, "--once", help="Run one cycle and exit."),
    interval: int | None = typer.Option(
        None, "--interval", min=MIN_INTERVAL_SECONDS, help="Seconds between cycles (default from config, 300)."
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Decide and show prices, send no writes."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the start confirmation."),
) -> None:
    """Keep each configured offer 0.01 below the cheapest other seller, never below min_price."""
    try:
        # --once needs something to do; a long-running bot may start with nothing ON or paused
        # and pick up changes from the settings page later.
        config = load_bidding_config(config_path, require_enabled=once)
    except EldoradoError as exc:
        fail(exc)
    rules = config.enabled_rules()
    mode = "[cyan]DRY-RUN[/cyan]" if dry_run else "[bold red]LIVE[/bold red]"
    console.print(f"Auto bidding {mode}: {len(rules)} offer(s) ON, undercut {config.undercut}, "
                  + ("one cycle." if once else
                     f"every {interval or config.interval_seconds}s. Settings are re-read every cycle. "
                     "Ctrl+C to stop."))
    if not dry_run and not yes and not typer.confirm("Start changing LIVE prices?", default=False):
        console.print("Cancelled. Nothing was sent.")
        raise typer.Exit(code=0)

    audit = AuditLogger()
    lock = BotLock()

    def paused_now() -> bool:
        """Checked before every live write, so `paused = true` saved mid-cycle stops the rest."""
        try:
            return load_bidding_config(config_path, require_enabled=False).paused
        except EldoradoError:
            return False
    try:
        if not dry_run:
            lock.acquire()  # refuse to run next to another live bot
        with open_client() as base:
            bidder = Bidder(OffersClient(base), audit, config)
            first = True
            while True:
                if not first:
                    try:
                        bidder.set_config(load_bidding_config(config_path, require_enabled=False))
                        if bidder.config_changed:
                            console.print(f"Settings reloaded: {len(bidder.config.enabled_rules())} offer(s) ON"
                                          + (", PAUSED." if bidder.config.paused else "."))
                    except EldoradoError as exc:
                        err_console.print(f"[yellow]Settings not reloaded, keeping the last good ones:[/yellow] "
                                          f"{escape(redact(str(exc)))}")
                first = False
                stamp = f"{time.strftime('%H:%M:%S')}"
                if bidder.config.paused:
                    console.print(f"{stamp} Bot is PAUSED in settings. Nothing sent.")
                elif not bidder.config.enabled_rules():
                    console.print(f"{stamp} No offer is ON. Nothing sent.")
                else:
                    try:
                        _print_report(bidder.run_cycle(dry_run=dry_run, should_stop=paused_now))
                    except (WriteOutcomeUnknownError, AuthenticationError, AuditLogError):
                        # Never carry on: with no audit record, the next cycle could repeat a
                        # write whose outcome is unknown.
                        raise
                    except EldoradoError as exc:
                        if once:
                            raise
                        err_console.print(f"[yellow]Cycle skipped:[/yellow] {escape(redact(str(exc)))}")
                    except Exception as exc:  # noqa: BLE001 - may be mid-write: stop, never retry
                        raise WriteOutcomeUnknownError(
                            f"Unexpected error during a cycle ({type(exc).__name__}: {exc}). "
                            "A price change may or may not have been sent."
                        ) from None
                if once:
                    return
                time.sleep(interval or bidder.config.interval_seconds)
    except KeyboardInterrupt:
        console.print("Stopped.")
    except WriteOutcomeUnknownError as exc:
        err_console.print("[red]Bot stopped.[/red] A price write had an unknown outcome.")
        fail(exc)
    except EldoradoError as exc:
        fail(exc)
    finally:
        lock.release()
