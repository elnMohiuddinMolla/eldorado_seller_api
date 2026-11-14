"""Offer models for TopUp (predefined) offers. Shapes from the Swagger spec (api-spec.md 4.3, 4.6)."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

TOPUP_CATEGORY = "TopUp"


class Money(BaseModel):
    """MoneyBaseDTO. Amounts stay Decimal in code and become JSON numbers on the wire."""

    model_config = ConfigDict(extra="ignore")

    amount: Decimal
    currency: str

    def to_body(self) -> dict[str, object]:
        return {"amount": float(self.amount), "currency": self.currency}


class LibraryProperty(BaseModel):
    """LibraryPropertyDTO: one trade environment value or offer attribute value."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    value: str | None = None
    name: str | None = None
    id: str | None = None
    attribute_id: str | None = Field(default=None, alias="attributeId")

    def key(self) -> str:
        return f"{self.attribute_id or self.name or ''}={self.id or self.value or ''}"


class OfferAttribute(BaseModel):
    """Live shape (not in Swagger): {"id": "call-of-duty-mobile-cp", "name": "CP",
    "value": {"id": "80-cp", "name": "80 CP"}, "values": [...]}. `value` is the package."""

    model_config = ConfigDict(extra="ignore")

    id: str | None = None
    name: str | None = None
    value: LibraryProperty | None = None


class Offer(BaseModel):
    """Fields shared by PredefinedOfferPrivateViewDTO and PredefinedOfferGroupPublicDTO."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str
    user_id: str | None = Field(default=None, alias="userId")
    game_id: str | None = Field(default=None, alias="gameId")
    category: str | None = None
    title: str | None = Field(default=None, alias="gameCategoryTitle")
    quantity: int | None = None
    price: Money = Field(alias="pricePerUnit")
    price_usd: Money | None = Field(default=None, alias="pricePerUnitInUSD")
    state: str | None = Field(default=None, alias="offerState")
    trade_environment_values: list[LibraryProperty] | None = Field(
        default=None, alias="tradeEnvironmentValues"
    )
    attribute_values: list[LibraryProperty] | None = Field(
        default=None, alias="offerAttributeIdValues"
    )
    attributes: list[OfferAttribute] | None = None
    seo_alias: str | None = Field(default=None, alias="gameSeoAlias")

    def package_parts(self) -> list[str]:
        """Package identity, e.g. ['call-of-duty-mobile-cp=80-cp']. Empty when unknown."""
        parts = [
            f"{a.id}={a.value.id or a.value.name}"
            for a in self.attributes or []
            if a.id and a.value is not None and (a.value.id or a.value.name)
        ]
        parts += [p.key() for p in self.attribute_values or []]
        return sorted(parts)

    def product_key(self) -> tuple[str, ...]:
        """Identifies 'the same package of the same game' across sellers."""
        env = sorted(p.key() for p in self.trade_environment_values or [])
        return (self.game_id or "", *env, "|", *self.package_parts())

    def package_name(self) -> str:
        names = [a.value.name or a.value.id or "" for a in self.attributes or [] if a.value]
        names += [p.value or p.name or "" for p in self.attribute_values or []]
        return " ".join(n for n in names if n)

    def label(self) -> str:
        game = self.seo_alias or self.title or ""
        return " ".join(x for x in [game, self.package_name()] if x) or self.id


class CompetitorOffer(BaseModel):
    """PredefinedOfferGroupPublicViewModel: a public offer plus its seller."""

    model_config = ConfigDict(extra="ignore")

    offer: Offer
    seller: str | None = None


class Page(BaseModel):
    """IndexBasedPagedResult<T> with the fields the tool uses."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    page_index: int = Field(default=0, alias="pageIndex")
    total_pages: int = Field(default=0, alias="totalPages")
    record_count: int = Field(default=0, alias="recordCount")


class OfferPage(Page):
    results: list[Offer] = Field(default_factory=list)


class CompetitorPage(Page):
    results: list[CompetitorOffer] = Field(default_factory=list)


class PriceChange(BaseModel):
    offer_id: str
    label: str
    before: Decimal
    after: Decimal
    currency: str

    @property
    def percent(self) -> Decimal:
        if self.before == 0:
            return Decimal("100")
        return (self.after - self.before) / self.before * 100
