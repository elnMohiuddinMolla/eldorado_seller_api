"""Seller status endpoints. [Confirmed] (swagger), see api-spec.md 4.5."""

from __future__ import annotations

from eldorado.client.base import BaseClient

ONLINE_PATH = "/api/offerUser/me/switchOnline"
OFFLINE_PATH = "/api/offerUser/me/switchOffline"


class AccountClient:
    def __init__(self, base: BaseClient) -> None:
        self._base = base

    def set_online(self, online: bool) -> int:
        return self._base.write("PUT", ONLINE_PATH if online else OFFLINE_PATH).status_code
