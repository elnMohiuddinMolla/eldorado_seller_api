"""JSON shaped like the Swagger schemas (PredefinedOffer*DTO), for mocked responses."""

from __future__ import annotations

from typing import Any

ME = "seller-me"
GAME = "game-codm"


def offer_json(
    offer_id: str,
    price: float,
    *,
    user_id: str = ME,
    game_id: str = GAME,
    package: str = "80 CP",
    state: str = "Active",
    currency: str = "USD",
) -> dict[str, Any]:
    return {
        "id": offer_id,
        "userId": user_id,
        "gameId": game_id,
        "category": "TopUp",
        "gameCategoryTitle": "Call of Duty Mobile",
        "quantity": 100,
        "pricePerUnit": {"amount": price, "currency": currency},
        "pricePerUnitInUSD": {"amount": price, "currency": "USD"} if currency == "USD" else None,
        "guaranteedDeliveryTime": "Instant",
        "offerState": state,
        "tradeEnvironmentValues": [],
        "offerAttributeIdValues": [],
        "gameSeoAlias": "codm-top-up",
        # Live shape: the package is attributes[].value (not in the Swagger schema).
        "attributes": [{
            "id": "call-of-duty-mobile-cp", "name": "CP", "type": "Select",
            "value": {"id": package.replace(" ", "-").lower(), "name": package},
            "values": [{"id": package.replace(" ", "-").lower(), "name": package}],
        }],
    }


def page(results: list[dict[str, Any]], total_pages: int = 1, index: int = 0) -> dict[str, Any]:
    return {"pageSize": 50, "pageIndex": index, "totalPages": total_pages,
            "recordCount": len(results), "results": results}


def market(*offers: dict[str, Any]) -> dict[str, Any]:
    return page([{"offer": o, "user": {"id": o["userId"], "username": o["userId"]}} for o in offers])
