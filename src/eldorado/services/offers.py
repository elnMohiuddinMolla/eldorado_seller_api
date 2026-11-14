"""Manual TopUp offer changes (F3, F4): 50% guard, pilot, dry-run and audit."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from eldorado.client.offers import FIRST_PAGE, OffersClient
from eldorado.core.audit import AuditLogger, record_unknown
from eldorado.core.exceptions import (
    EldoradoError,
    PriceGuardError,
    ResourceNotFoundError,
    WriteOutcomeUnknownError,
)
from eldorado.models.offer import Money, Offer, PriceChange
from eldorado.services.bidding import BIG_CHANGE_PERCENT, MAX_PAGES, PAGE_SIZE

ACTION_UPDATE = "offer.update"
ACTION_PAUSE = "offer.pause"
ACTION_RESUME = "offer.resume"

Outcome = Literal["success", "failed", "unknown", "dry_run", "not_sent"]


@dataclass
class ItemResult:
    offer_id: str
    outcome: Outcome
    pilot: bool
    message: str | None = None


class OfferService:
    def __init__(self, client: OffersClient | None, audit: AuditLogger) -> None:
        self._client = client  # None only for dry runs that need no reads
        self._audit = audit

    def _live_client(self) -> OffersClient:
        if self._client is None:
            raise RuntimeError("OfferService needs a client for this call")
        return self._client

    def list_mine(self, *, game_id: str | None = None, state: str | None = None,
                  limit: int | None = None) -> list[Offer]:
        offers: list[Offer] = []
        for index in range(FIRST_PAGE, FIRST_PAGE + MAX_PAGES):
            page = self._live_client().list_mine(
                game_id=game_id, state=state, page_index=index, page_size=PAGE_SIZE
            )
            offers.extend(page.results)
            if limit is not None and len(offers) >= limit:
                return offers[:limit]
            if not page.results or index >= page.total_pages:
                break
        return offers

    def find(self, offer_id: str) -> Offer:
        for offer in self.list_mine():
            if offer.id == offer_id:
                return offer
        raise ResourceNotFoundError(f"Offer {offer_id} is not one of your TopUp offers.")

    def plan_price(self, offer_id: str, price: Decimal, *, allow_big_change: bool) -> PriceChange:
        # is_finite first: comparing NaN with <= raises InvalidOperation.
        if not price.is_finite() or price <= 0:
            raise PriceGuardError("Price must be a number greater than 0.")
        offer = self.find(offer_id)
        change = PriceChange(
            offer_id=offer.id, label=offer.label(), before=offer.price.amount,
            after=price.quantize(Decimal("0.01")), currency=offer.price.currency,
        )
        if abs(change.percent) > BIG_CHANGE_PERCENT and not allow_big_change:
            raise PriceGuardError(
                f"Price change {change.before} -> {change.after} is {change.percent:+.1f}%, "
                "over the 50% limit. Pass --allow-big-change if this is intended."
            )
        return change

    def apply_price(self, change: PriceChange, *, dry_run: bool) -> ItemResult:
        before, after = {"price": change.before}, {"price": change.after}
        if dry_run:
            self._audit.write(action=ACTION_UPDATE, entity_type="offer", entity_id=change.offer_id,
                              before=before, after=after, dry_run=True, outcome="dry_run")
            return ItemResult(change.offer_id, "dry_run", pilot=False)
        try:
            status = self._live_client().change_price(
                change.offer_id, Money(amount=change.after, currency=change.currency))
        except WriteOutcomeUnknownError as exc:
            record_unknown(self._audit, exc, action=ACTION_UPDATE, entity_type="offer",
                           entity_id=change.offer_id, before=before, after=after)
            raise
        except EldoradoError as exc:
            self._audit.write(action=ACTION_UPDATE, entity_type="offer", entity_id=change.offer_id,
                              before=before, after=after, dry_run=False, outcome="failed",
                              http_status=exc.http_status, message=str(exc))
            raise
        self._audit.write(action=ACTION_UPDATE, entity_type="offer", entity_id=change.offer_id,
                          before=before, after=after, dry_run=False, outcome="success",
                          http_status=status)
        return ItemResult(change.offer_id, "success", pilot=False)

    def set_paused(
        self,
        offer_ids: list[str],
        *,
        paused: bool,
        dry_run: bool,
        confirm_rest: Callable[[], bool] = lambda: True,
    ) -> list[ItemResult]:
        """Pause or resume offers. The first id is the pilot; a failed pilot stops the rest."""
        action = ACTION_PAUSE if paused else ACTION_RESUME
        def call(offer_id: str) -> int:
            client = self._live_client()
            return client.pause(offer_id) if paused else client.resume(offer_id)

        after = {"state": "Paused" if paused else "Active"}
        results: list[ItemResult] = []
        for index, offer_id in enumerate(offer_ids):
            pilot = index == 0 and len(offer_ids) > 1
            if dry_run:
                self._audit.write(action=action, entity_type="offer", entity_id=offer_id,
                                  after=after, dry_run=True, pilot=pilot, outcome="dry_run")
                results.append(ItemResult(offer_id, "dry_run", pilot))
                continue
            try:
                status = call(offer_id)
            except WriteOutcomeUnknownError as exc:
                record_unknown(self._audit, exc, action=action, entity_type="offer",
                               entity_id=offer_id, after=after, pilot=pilot)
                results.append(ItemResult(offer_id, "unknown", pilot, str(exc)))
                results.extend(ItemResult(i, "not_sent", False) for i in offer_ids[index + 1:])
                return results
            except EldoradoError as exc:
                self._audit.write(action=action, entity_type="offer", entity_id=offer_id, after=after,
                                  dry_run=False, pilot=pilot, outcome="failed",
                                  http_status=exc.http_status, message=str(exc))
                results.append(ItemResult(offer_id, "failed", pilot, str(exc)))
                if pilot:
                    results.extend(ItemResult(i, "not_sent", False) for i in offer_ids[index + 1:])
                    return results
                continue
            self._audit.write(action=action, entity_type="offer", entity_id=offer_id, after=after,
                              dry_run=False, pilot=pilot, outcome="success", http_status=status)
            results.append(ItemResult(offer_id, "success", pilot))
            if pilot and not confirm_rest():
                results.extend(ItemResult(i, "not_sent", False) for i in offer_ids[index + 1:])
                return results
        return results
