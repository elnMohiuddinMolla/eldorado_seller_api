"""TopUp (predefined) offer endpoints. All paths [Confirmed] (swagger), see api-spec.md 4.3."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx
from pydantic import ValidationError

from eldorado.client.base import BaseClient
from eldorado.core.exceptions import EldoradoAPIError
from eldorado.models.offer import TOPUP_CATEGORY, CompetitorOffer, CompetitorPage, Money, OfferPage

MY_OFFERS_PATH = "/api/predefinedOffers/me"
GAME_OFFERS_PATH = "/api/predefinedOffers/game"  # public list of every seller's offers
# pageIndex is 1-based: pageIndex=0 returns HTTP 400 "invalid values: PageIndex" (live, 2026-11-14).
FIRST_PAGE = 1


def _id(offer_id: str) -> str:
    return quote(offer_id, safe="")


def change_price_path(offer_id: str) -> str:
    return f"/api/predefinedOffersUser/me/{_id(offer_id)}/changePrice"


def pause_path(offer_id: str) -> str:
    return f"/api/predefinedOffersUser/me/{_id(offer_id)}/pause"


def resume_path(offer_id: str) -> str:
    return f"/api/predefinedOffersUser/me/{_id(offer_id)}/resume"


def _clean(params: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in params.items() if v is not None}


class OffersClient:
    def __init__(self, base: BaseClient) -> None:
        self._base = base

    def list_mine(
        self,
        *,
        game_id: str | None = None,
        state: str | None = None,
        page_index: int = FIRST_PAGE,
        page_size: int = 50,
    ) -> OfferPage:
        params = _clean({
            "category": TOPUP_CATEGORY, "gameId": game_id, "offerState": state,
            "pageIndex": page_index, "pageSize": page_size,
        })
        response = self._base.read("GET", MY_OFFERS_PATH, params=params)
        return _parse(OfferPage, _json(response, MY_OFFERS_PATH), MY_OFFERS_PATH)

    def list_game(
        self,
        *,
        game_id: str,
        trade_environment_id: str | None = None,
        page_index: int = FIRST_PAGE,
        page_size: int = 50,
    ) -> CompetitorPage:
        params = _clean({
            "gameId": game_id, "category": TOPUP_CATEGORY,
            "tradeEnvironmentId": trade_environment_id,
            "pageIndex": page_index, "pageSize": page_size,
        })
        response = self._base.read("GET", GAME_OFFERS_PATH, params=params)
        data = _json(response, GAME_OFFERS_PATH)
        # PredefinedOfferGroupPublicViewModel = {offer, user: {username, ...}, ...}
        if isinstance(data, dict):
            for item in data.get("results") or []:
                if isinstance(item, dict) and isinstance(item.get("user"), dict):
                    item.setdefault("seller", item["user"].get("username"))
        return _parse(CompetitorPage, data, GAME_OFFERS_PATH)

    def change_price(self, offer_id: str, price: Money) -> int:
        """Returns the HTTP status (recorded in the audit log)."""
        return self._base.write("PUT", change_price_path(offer_id), json=price.to_body()).status_code

    def pause(self, offer_id: str) -> int:
        return self._base.write("PUT", pause_path(offer_id)).status_code

    def resume(self, offer_id: str) -> int:
        return self._base.write("PUT", resume_path(offer_id)).status_code


def _json(response: httpx.Response, path: str) -> Any:
    """A 200 with HTML (maintenance or bot-check page) must be an API error, not a crash."""
    try:
        return response.json()
    except ValueError:
        ctype = response.headers.get("content-type", "?")
        raise EldoradoAPIError(
            f"GET {path} returned HTTP {response.status_code} but not JSON (content-type {ctype})."
        ) from None


def _parse(model: type[OfferPage] | type[CompetitorPage], data: Any, path: str) -> Any:
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        fields = sorted({".".join(str(p) for p in e["loc"]) for e in exc.errors()})[:5]
        raise EldoradoAPIError(
            f"GET {path} returned an unexpected format (fields: {', '.join(fields)}). "
            "Update models/offer.py to match the real response."
        ) from None


__all__ = ["OffersClient", "CompetitorOffer"]
