"""HTTP layer. `build_client` wires the httpx client, token manager and base client."""

from __future__ import annotations

import httpx

from eldorado import __version__
from eldorado.client.auth import TokenManager
from eldorado.client.base import BaseClient
from eldorado.core.config import Settings


def build_client(settings: Settings) -> BaseClient:
    http = httpx.Client(
        base_url=settings.base_url,
        timeout=settings.timeout_seconds,
        headers={
            "Accept": "application/json",
            "User-Agent": f"eldorado-seller-tool/{__version__}",
        },
    )
    return BaseClient(http, TokenManager(http, settings))
