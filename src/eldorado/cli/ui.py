"""`eldorado ui`: a local web page to edit bidding.toml (min/max/on per offer).

Security: binds to 127.0.0.1 only, checks the Host header (blocks DNS rebinding), and every
API call needs a random per-run token embedded in the page (blocks other sites posting to it).
The page itself never sends price changes; the bot does (`eldorado bid run`, or the bot
thread started by `eldorado app`).
"""

from __future__ import annotations

import json
import secrets
import sys
import time
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import typer
from rich.markup import escape

from eldorado.cli.bid import _print_report
from eldorado.cli.shared import console, err_console, fail, open_client
from eldorado.core.audit import AuditLogger
from eldorado.cli.ui_page import PAGE
from eldorado.client.offers import OffersClient
from eldorado.core.bidding_config import DEFAULT_BIDDING_PATH
from eldorado.core.exceptions import ConfigError, EldoradoError
from eldorado.core.instance_lock import BotLock
from eldorado.core.logging import redact
from eldorado.services.bidding import CycleReport
from eldorado.services.bot_runner import BotRunner, set_paused
from eldorado.services.dashboard import Dashboard
from eldorado.services.order_watch import OrderWatcher
from eldorado.models.order import SellerOrder

MAX_BODY_BYTES = 1_000_000
DEFAULT_PORT = 8765


def make_handler(
    dashboard: Dashboard, token: str, port: int, runner: BotRunner | None = None,
    watcher: OrderWatcher | None = None,
) -> type[BaseHTTPRequestHandler]:
    allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
    page = PAGE.replace("__TOKEN__", token).encode("utf-8")
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        server_version = "eldorado-ui"
        sys_version = ""
        # Browsers open spare connections and send nothing; drop them instead of waiting forever.
        timeout = 10

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return  # keep the terminal quiet

        def _send(self, status: int, body: bytes, ctype: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Content-Security-Policy",
                             "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
                             "connect-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, payload: Any) -> None:
            self._send(status, json.dumps(payload).encode("utf-8"), "application/json")

        def _host_ok(self) -> bool:
            return self.headers.get("Host", "") in allowed_hosts

        def _token_ok(self) -> bool:
            return secrets.compare_digest(self.headers.get("X-Token", ""), token)

        def _guard(self, need_token: bool) -> bool:
            if not self._host_ok():
                self._json(HTTPStatus.FORBIDDEN, {"error": "bad host"})
                return False
            if need_token and not self._token_ok():
                self._json(HTTPStatus.FORBIDDEN, {"error": "bad token, reload the page"})
                return False
            return True

        def _run(self, fn: Any) -> None:
            try:
                with lock:  # one request at a time: the HTTP client is not shared across threads
                    self._json(HTTPStatus.OK, fn())
            except ConfigError as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"error": redact(str(exc))})
            except EldoradoError as exc:
                self._json(HTTPStatus.BAD_GATEWAY, {"error": redact(str(exc))})
            except Exception as exc:  # noqa: BLE001 - answer with JSON, never drop the connection
                self._json(HTTPStatus.INTERNAL_SERVER_ERROR,
                           {"error": f"internal error ({type(exc).__name__})"})

        def do_GET(self) -> None:  # noqa: N802
            path, _, query = self.path.partition("?")
            if path in ("/", "/index.html"):
                if self._guard(need_token=False):
                    self._send(HTTPStatus.OK, page, "text/html; charset=utf-8")
            elif path == "/api/offers":
                if self._guard(need_token=True):
                    fresh = "fresh=1" in query.split("&")
                    self._run(lambda: dashboard.rows(fresh=fresh))
            elif path == "/api/activity":
                if self._guard(need_token=True):
                    self._run(dashboard.activity)
            elif path == "/api/orders":
                if self._guard(need_token=True):
                    self._json(HTTPStatus.OK, watcher.snapshot() if watcher else {"enabled": False})
            elif path == "/api/status":
                if self._guard(need_token=True):
                    self._json(HTTPStatus.OK, runner.status() if runner else {"state": "none"})
            else:
                self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            if not self._guard(need_token=True):
                return
            if self.headers.get_content_type() != "application/json":
                self._json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "JSON only"})
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = -1
            if length < 0:
                self._json(HTTPStatus.BAD_REQUEST, {"error": "bad Content-Length"})
                return
            if length > MAX_BODY_BYTES:
                self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "too large"})
                return
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except ValueError:
                self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid JSON"})
                return
            if self.path == "/api/config":
                def save() -> dict[str, Any]:
                    config = dashboard.save(body if isinstance(body, dict) else {})
                    if runner is not None:
                        runner.wake()  # act on the new settings now, not in 5 minutes
                    return {"enabled": len(config.enabled_rules())}
                self._run(save)
            elif self.path == "/api/preview":
                self._run(lambda: {"decisions": dashboard.preview()})
            else:
                self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    return Handler


class LocalServer(ThreadingHTTPServer):
    # On Windows SO_REUSEADDR lets a second server bind the same port silently; fail instead.
    allow_reuse_address = False
    daemon_threads = True


def _now() -> str:
    return time.strftime("%H:%M:%S")


STATE_TEXT = {
    "running": "[bold green]Bot RUNNING[/bold green]: prices are managed.",
    "paused": "[bold yellow]Bot PAUSED[/bold yellow]: nothing is sent. Click Bot on the page to run.",
    "idle": "[yellow]Bot RUNNING, but no offer is ON[/yellow]. Turn offers ON on the page.",
    "error": "[bold red]Bot PAUSED ITSELF after an error[/bold red]",
    "stopped": "Bot stopped.",
}


def _announce_state(state: str, message: str) -> None:
    text = STATE_TEXT.get(state, state)
    if state == "error":
        text += f": {escape(message)}"
    console.print(f"{_now()} {text}")


def _report_cycle(report: CycleReport, interval_seconds: int) -> None:
    """Full table only when something was sent or failed; otherwise one short line."""
    changes = report.changes()
    if changes:
        _print_report(report)
        return
    skipped = sum(1 for d in report.decisions if d.kind == "skip")
    nxt = time.strftime("%H:%M:%S", time.localtime(time.time() + interval_seconds))
    console.print(f"{_now()} checked {len(report.decisions)} offer(s): 0 changed"
                  + (f", {skipped} skipped" if skipped else "")
                  + f". Next check about {nxt}.")


def _announce_orders(orders: list[SellerOrder]) -> None:
    """New order: beep and print in the app window (the page shows its own alert)."""
    for order in orders:
        console.print(f"{_now()} [bold green]NEW ORDER[/bold green] {escape(order.game)} {escape(order.package)} "
                      f"x{order.quantity}  {order.total} {order.currency}  ({escape(order.state)})")
    if sys.platform == "win32":
        import winsound

        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
    else:
        console.bell()


def _serve(config_path: Path, port: int, no_browser: bool, *, with_bot: bool) -> None:
    token = secrets.token_urlsafe(24)
    runner: BotRunner | None = None
    thread: threading.Thread | None = None
    lock = BotLock()
    try:
        if with_bot:
            lock.acquire()  # refuse to start a second bot
            # Safe start: nothing is sent until the user clicks RUN on the page.
            set_paused(config_path, True)
        with open_client() as page_client, open_client() as bot_client, \
                open_client() as order_client:
            dashboard = Dashboard(
                OffersClient(page_client), config_path,
                # The preview plans with a copy of the bot's memory, so it matches the bot.
                bot_memory=lambda: runner.bidder_memory() if runner is not None else None,
            )
            if with_bot:
                runner = BotRunner(
                    OffersClient(bot_client), AuditLogger(), config_path,
                    on_report=_report_cycle,
                    log=lambda m: err_console.print(f"{_now()} [yellow]{escape(m)}[/yellow]"),
                    on_state=_announce_state,
                )
                thread = threading.Thread(target=runner.loop, name="bot", daemon=True)
            watcher = OrderWatcher(order_client, on_new=_announce_orders,
                                   log=lambda m: err_console.print(f"{_now()} [yellow]{escape(m)}[/yellow]"))
            threading.Thread(target=watcher.loop, name="orders", daemon=True).start()
            server = LocalServer(("127.0.0.1", port),
                                 make_handler(dashboard, token, port, runner, watcher))
            url = f"http://127.0.0.1:{port}/"
            console.print(f"Settings page: [bold]{url}[/bold]  (only on this computer).")
            if with_bot:
                console.print("Close this window (or Ctrl+C) to stop everything. "
                              "Bot status changes appear below.")
                assert thread is not None
                thread.start()
            if not no_browser:
                webbrowser.open(url)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                console.print("Stopped.")
            finally:
                if runner is not None:
                    runner.stop()
                watcher.stop()
                server.server_close()
    except OSError as exc:
        console.print(f"[red]Could not start on port {port}:[/red] {exc.strerror}. "
                      "Is it already running in another window?")
        raise typer.Exit(code=1) from None
    except EldoradoError as exc:
        fail(exc)
    finally:
        lock.release()


def ui(
    config_path: Path = typer.Option(DEFAULT_BIDDING_PATH, "--config", help="Bidding config file."),
    port: int = typer.Option(DEFAULT_PORT, "--port", min=1024, max=65535),
    no_browser: bool = typer.Option(False, "--no-browser", help="Do not open the browser."),
) -> None:
    """Open a local web page to edit min/max price and ON/OFF per offer (no bot)."""
    _serve(config_path, port, no_browser, with_bot=False)


def app_cmd(
    config_path: Path = typer.Option(DEFAULT_BIDDING_PATH, "--config", help="Bidding config file."),
    port: int = typer.Option(DEFAULT_PORT, "--port", min=1024, max=65535),
    no_browser: bool = typer.Option(False, "--no-browser", help="Do not open the browser."),
) -> None:
    """Settings page AND the bot in one window. Starts PAUSED; run/pause it from the page."""
    _serve(config_path, port, no_browser, with_bot=True)
