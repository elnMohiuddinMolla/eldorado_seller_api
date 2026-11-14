from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx

from eldorado.client.base import BaseClient
from eldorado.client.orders import OrdersClient, deliver_path
from eldorado.core.audit import AuditLogger
from eldorado.core.exceptions import (
    EldoradoAPIError,
    EndpointNotConfirmedError,
    WriteOutcomeUnknownError,
)
from eldorado.services import orders as orders_service
from eldorado.services.orders import OrderService


def _records(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_deliver_path_matches_confirmed_endpoint() -> None:
    assert deliver_path("ABC123") == "/api/v1/orders/me/ABC123/deliver"


def test_deliver_path_escapes_id() -> None:
    assert deliver_path("../x y") == "/api/v1/orders/me/..%2Fx%20y/deliver"


def test_client_sends_put(base: BaseClient, api: respx.MockRouter, token_route: respx.Route) -> None:
    route = api.put("/api/v1/orders/me/ABC123/deliver").mock(return_value=httpx.Response(200))
    assert OrdersClient(base).mark_delivered("ABC123") == 200
    request = route.calls.last.request
    assert request.headers["Authorization"].startswith("Bearer ")
    assert request.content == b""  # Swagger: no request body


def test_live_deliver_blocked_until_enabled(tmp_path: Path) -> None:
    service = OrderService(None, AuditLogger(tmp_path / "a.jsonl"))
    with pytest.raises(EndpointNotConfirmedError):
        service.deliver("ABC123", dry_run=False)
    assert not (tmp_path / "a.jsonl").exists()


@pytest.fixture
def body_confirmed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(orders_service, "DELIVER_LIVE_ENABLED", True)


@pytest.mark.usefixtures("body_confirmed")
def test_live_deliver_success_is_audited(
    base: BaseClient, api: respx.MockRouter, token_route: respx.Route, tmp_path: Path
) -> None:
    api.put("/api/v1/orders/me/ABC123/deliver").mock(return_value=httpx.Response(204))
    audit_path = tmp_path / "a.jsonl"
    result = OrderService(OrdersClient(base), AuditLogger(audit_path)).deliver("ABC123", dry_run=False)
    assert result.http_status == 204
    (record,) = _records(audit_path)
    assert record["outcome"] == "success"
    assert record["http_status"] == 204
    assert record["action"] == "order.deliver"


@pytest.mark.usefixtures("body_confirmed")
def test_live_deliver_5xx_is_unknown_and_audited(
    base: BaseClient, api: respx.MockRouter, token_route: respx.Route, tmp_path: Path
) -> None:
    route = api.put("/api/v1/orders/me/ABC123/deliver").mock(return_value=httpx.Response(503))
    audit_path = tmp_path / "a.jsonl"
    with pytest.raises(WriteOutcomeUnknownError):
        OrderService(OrdersClient(base), AuditLogger(audit_path)).deliver("ABC123", dry_run=False)
    assert route.call_count == 1
    (record,) = _records(audit_path)
    assert record["outcome"] == "unknown"


@pytest.mark.usefixtures("body_confirmed")
def test_live_deliver_4xx_is_failed_and_audited(
    base: BaseClient, api: respx.MockRouter, token_route: respx.Route, tmp_path: Path
) -> None:
    api.put("/api/v1/orders/me/ABC123/deliver").mock(return_value=httpx.Response(409))
    audit_path = tmp_path / "a.jsonl"
    with pytest.raises(EldoradoAPIError):
        OrderService(OrdersClient(base), AuditLogger(audit_path)).deliver("ABC123", dry_run=False)
    (record,) = _records(audit_path)
    assert record["outcome"] == "failed"
    assert record["http_status"] == 409
