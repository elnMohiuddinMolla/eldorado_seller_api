from __future__ import annotations

from pathlib import Path

import httpx
import respx

from eldorado.client.account import OFFLINE_PATH, ONLINE_PATH, AccountClient
from eldorado.client.base import BaseClient
from eldorado.core.audit import AuditLogger
from eldorado.services.account import AccountService


def test_online_and_offline_call_the_right_path(base: BaseClient, api: respx.MockRouter,
                                                token_route: respx.Route, tmp_path: Path) -> None:
    on = api.put(ONLINE_PATH).mock(return_value=httpx.Response(200))
    off = api.put(OFFLINE_PATH).mock(return_value=httpx.Response(200))
    service = AccountService(AccountClient(base), AuditLogger(tmp_path / "a.jsonl"))
    service.set_online(True, dry_run=False)
    assert (on.call_count, off.call_count) == (1, 0)
    service.set_online(False, dry_run=False)
    assert (on.call_count, off.call_count) == (1, 1)
    assert on.calls.last.request.content == b""
