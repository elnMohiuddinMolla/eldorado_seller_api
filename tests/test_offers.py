from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import respx

from eldorado.client.base import BaseClient
from eldorado.client.offers import MY_OFFERS_PATH, OffersClient, change_price_path, pause_path, resume_path
from eldorado.core.audit import AuditLogger
from eldorado.core.exceptions import EldoradoAPIError, PriceGuardError, ResourceNotFoundError
from eldorado.services.offers import OfferService

from .factories import offer_json, page


def test_paths_match_swagger() -> None:
    assert change_price_path("a b") == "/api/predefinedOffersUser/me/a%20b/changePrice"
    assert pause_path("x") == "/api/predefinedOffersUser/me/x/pause"
    assert resume_path("x") == "/api/predefinedOffersUser/me/x/resume"


def test_list_sends_topup_filters_and_parses(base: BaseClient, api: respx.MockRouter, token_route: respx.Route) -> None:
    route = api.get(MY_OFFERS_PATH).mock(return_value=httpx.Response(200, json=page([offer_json("o1", 0.99)])))
    result = OffersClient(base).list_mine(game_id="g1", state="Active")
    params = route.calls.last.request.url.params
    assert params["category"] == "TopUp" and params["gameId"] == "g1" and params["offerState"] == "Active"
    assert result.results[0].price.amount == Decimal("0.99")


def test_list_follows_pages_and_limit(base: BaseClient, api: respx.MockRouter, token_route: respx.Route) -> None:
    api.get(MY_OFFERS_PATH, params={"pageIndex": "1"}).mock(
        return_value=httpx.Response(200, json=page([offer_json("o1", 1)], total_pages=2)))
    api.get(MY_OFFERS_PATH, params={"pageIndex": "2"}).mock(
        return_value=httpx.Response(200, json=page([offer_json("o2", 1)], total_pages=2, index=2)))
    service = OfferService(OffersClient(base), AuditLogger())
    assert [o.id for o in service.list_mine()] == ["o1", "o2"]
    assert [o.id for o in service.list_mine(limit=1)] == ["o1"]


def test_unexpected_list_format_is_a_clear_error(base: BaseClient, api: respx.MockRouter, token_route: respx.Route) -> None:
    api.get(MY_OFFERS_PATH).mock(return_value=httpx.Response(200, json={"results": [{"id": "x"}]}))
    with pytest.raises(EldoradoAPIError, match="unexpected format"):
        OffersClient(base).list_mine()


@pytest.fixture
def one_offer(api: respx.MockRouter, token_route: respx.Route) -> respx.MockRouter:
    api.get(MY_OFFERS_PATH).mock(return_value=httpx.Response(200, json=page([offer_json("o1", 10.00)])))
    return api


def test_price_guard_blocks_over_50_percent(one_offer: respx.MockRouter, base: BaseClient) -> None:
    service = OfferService(OffersClient(base), AuditLogger())
    with pytest.raises(PriceGuardError, match="50%"):
        service.plan_price("o1", Decimal("4.00"), allow_big_change=False)
    assert service.plan_price("o1", Decimal("4.00"), allow_big_change=True).after == Decimal("4.00")
    with pytest.raises(PriceGuardError):
        service.plan_price("o1", Decimal("0"), allow_big_change=True)


def test_unknown_offer_id(one_offer: respx.MockRouter, base: BaseClient) -> None:
    with pytest.raises(ResourceNotFoundError):
        OfferService(OffersClient(base), AuditLogger()).plan_price("nope", Decimal("9"), allow_big_change=False)


def test_apply_price_live_and_dry_run(one_offer: respx.MockRouter, base: BaseClient, tmp_path: Path) -> None:
    route = one_offer.put(change_price_path("o1")).mock(return_value=httpx.Response(200, json={"amount": 9.5, "currency": "USD"}))
    service = OfferService(OffersClient(base), AuditLogger(tmp_path / "a.jsonl"))
    change = service.plan_price("o1", Decimal("9.50"), allow_big_change=False)
    service.apply_price(change, dry_run=True)
    assert route.call_count == 0
    service.apply_price(change, dry_run=False)
    assert json.loads(route.calls.last.request.content) == {"amount": 9.5, "currency": "USD"}


def test_pause_pilot_failure_stops_rest(base: BaseClient, api: respx.MockRouter, token_route: respx.Route, tmp_path: Path) -> None:
    api.put(pause_path("a")).mock(return_value=httpx.Response(400))
    rb = api.put(pause_path("b")).mock(return_value=httpx.Response(200))
    results = OfferService(OffersClient(base), AuditLogger(tmp_path / "a.jsonl")).set_paused(
        ["a", "b"], paused=True, dry_run=False)
    assert [r.outcome for r in results] == ["failed", "not_sent"]
    assert rb.call_count == 0


def test_resume_asks_after_pilot(base: BaseClient, api: respx.MockRouter, token_route: respx.Route, tmp_path: Path) -> None:
    api.put(resume_path("a")).mock(return_value=httpx.Response(200))
    rb = api.put(resume_path("b")).mock(return_value=httpx.Response(200))
    results = OfferService(OffersClient(base), AuditLogger(tmp_path / "a.jsonl")).set_paused(
        ["a", "b"], paused=False, dry_run=False, confirm_rest=lambda: False)
    assert [r.outcome for r in results] == ["success", "not_sent"]
    assert results[0].pilot is True
    assert rb.call_count == 0


def test_pause_5xx_is_unknown_and_stops(base: BaseClient, api: respx.MockRouter, token_route: respx.Route, tmp_path: Path) -> None:
    ra = api.put(pause_path("a")).mock(return_value=httpx.Response(502))
    results = OfferService(OffersClient(base), AuditLogger(tmp_path / "a.jsonl")).set_paused(
        ["a", "b"], paused=True, dry_run=False)
    assert [r.outcome for r in results] == ["unknown", "not_sent"]
    assert ra.call_count == 1
