"""Order models."""

from __future__ import annotations

from pydantic import BaseModel, field_validator


class DeliverResult(BaseModel):
    order_id: str
    dry_run: bool
    http_status: int | None = None

    @field_validator("order_id")
    @classmethod
    def _order_id_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("order id must not be empty")
        return value


class SellerOrder(BaseModel):
    """The fields the order alert needs from OrderPrivateViewModel (live shape, 2026-11-14).

    Buyer fields (buyerId, buyerUsername, conversation) are deliberately not modelled:
    they are never kept or shown by this tool.
    """

    id: str
    state: str
    created: str
    quantity: int
    total: str
    currency: str
    game_id: str | None = None
    game: str
    package: str

    @classmethod
    def from_api(cls, raw: dict[str, object], game_names: dict[str, str]) -> SellerOrder:
        details = raw.get("orderOfferDetails") or {}
        assert isinstance(details, dict)
        attrs = details.get("offerAttributesProperties") or []
        package = " ".join(
            str(v) for a in attrs if isinstance(a, dict) for v in (a.get("values") or [])[:1]
        )
        game_id = details.get("gameId")
        state = raw.get("state") or {}
        total = raw.get("totalPrice") or {}
        assert isinstance(state, dict) and isinstance(total, dict)
        return cls(
            id=str(raw["id"]),
            state=str(state.get("state", "?")),
            created=str(raw.get("createdDate", "")),
            quantity=int(raw.get("purchaseQuantity") or 0),  # type: ignore[call-overload]
            total=str(total.get("amount", "?")),
            currency=str(total.get("currency", "")),
            game_id=str(game_id) if game_id is not None else None,
            game=game_names.get(str(game_id), str(details.get("gameCategoryTitle") or "?")),
            package=package or str(details.get("gameCategoryTitle") or "?"),
        )
