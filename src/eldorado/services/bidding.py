"""Auto bidding (F16). Rules in prd.md 9.1.

`decide` is a pure function. `Bidder.run_cycle` reads offers, decides, then writes:
the first change of a cycle is the pilot, and a failed pilot stops the cycle.
A write with an unknown outcome is re-raised so the caller stops the bot.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from decimal import ROUND_DOWN, Decimal
from typing import Literal

from eldorado.client.offers import FIRST_PAGE, OffersClient
from eldorado.core.audit import AuditLogger
from eldorado.core.bidding_config import BiddingConfig, OfferRule
from eldorado.core.exceptions import EldoradoError, WriteOutcomeUnknownError
from eldorado.models.offer import Money, Offer

ACTION_BID = "offer.bid"
SUPPORTED_CURRENCY = "USD"
BIG_CHANGE_PERCENT = Decimal("50")
CENT = Decimal("0.01")
PAGE_SIZE = 50
MAX_PAGES = 20
WRITE_DELAY_SECONDS = 1.0
READ_WORKERS = 2  # parallel market reads (4 hit HTTP 429 live); writes are always one at a time
# After a search up to max_price ends back at min_price (the cheaper seller was still there,
# e.g. a tie at min_price), do not search again for this long. Stops a min <-> max loop.
PROBE_BACKOFF_SECONDS = 30 * 60

Kind = Literal["change", "keep", "skip"]
Result = Literal["planned", "success", "failed", "unknown", "dry_run", "not_sent"]


@dataclass
class Decision:
    offer_id: str
    label: str
    kind: Kind
    reason: str
    current: Decimal | None = None
    target: Decimal | None = None
    lowest_competitor: Decimal | None = None
    result: Result = "planned"
    pilot: bool = False
    held_at_floor: bool = False  # a cheaper seller exists below min_price


@dataclass
class CycleReport:
    decisions: list[Decision] = field(default_factory=list)

    def changes(self) -> list[Decision]:
        return [d for d in self.decisions if d.kind == "change"]


def _usd_price(offer: Offer) -> Decimal | None:
    if offer.price.currency == SUPPORTED_CURRENCY:
        return offer.price.amount
    if offer.price_usd is not None and offer.price_usd.currency == SUPPORTED_CURRENCY:
        return offer.price_usd.amount
    return None


def decide(
    mine: Offer,
    competitors: list[Offer],
    rule: OfferRule,
    undercut: Decimal,
    *,
    was_held: bool = False,
) -> Decision:
    """was_held: last cycle this offer was held at min_price because a seller was below it."""
    label = rule.note or mine.label()
    base = Decision(offer_id=mine.id, label=label, kind="skip", reason="", current=mine.price.amount)

    if mine.state not in (None, "Active"):
        base.reason = f"offer is {mine.state}"
        return base
    if mine.price.currency != SUPPORTED_CURRENCY:
        base.reason = f"currency {mine.price.currency} not supported (USD only)"
        return base

    if not mine.package_parts():
        base.reason = "package unknown (no attributes), not compared"
        return base

    key = mine.product_key()
    i_am_listed = any(c.id == mine.id for c in competitors)
    prices = [
        p for c in competitors
        if c.id != mine.id
        and (mine.user_id is None or c.user_id != mine.user_id)
        and c.state in (None, "Active")
        and c.product_key() == key
        and (p := _usd_price(c)) is not None
        and p > 0
    ]
    if not prices:
        # The market lists ONE offer per package (the cheapest). When that offer is ours,
        # the next price is not visible, so the price is kept (prd.md 9.1).
        current = mine.price.amount
        if i_am_listed and was_held and rule.max_price is not None and rule.max_price > current:
            # The seller below min_price is gone, so we are now listed lowest, and the market
            # hides the next seller. Go to max_price for one cycle; the next cycle then sees
            # the next seller and undercuts it.
            base.target = rule.max_price
            percent = abs(rule.max_price - current) / current * 100 if current else Decimal("100")
            if percent > BIG_CHANGE_PERCENT and not rule.allow_big_change:
                base.reason = (f"cheaper seller gone, but max_price is {percent:.1f}% up "
                               "(over 50%; set allow_big_change)")
                return base
            base.kind = "change"
            base.reason = "cheaper seller gone: up to max_price to find the next seller"
            return base
        base.kind = "keep"
        if i_am_listed and was_held and rule.max_price is None:
            base.reason = "you are listed lowest at min_price (set max_price to search higher)"
        elif i_am_listed and was_held:
            base.reason = "you are listed lowest; no other seller below max_price"
        elif i_am_listed:
            base.reason = "you are the listed lowest offer"
        else:
            base.reason = "no other offer for this package"
        return base

    lowest = min(prices)
    base.lowest_competitor = lowest
    target = (lowest - undercut).quantize(CENT, rounding=ROUND_DOWN)
    note = f"lowest competitor {lowest}"
    if rule.max_price is not None and target > rule.max_price:
        target, note = rule.max_price, note + ", capped at max_price"
    if target < rule.min_price:
        target, note = rule.min_price, note + ", held at min_price"
        base.held_at_floor = True
    base.target = target

    current = mine.price.amount
    if target == current:
        base.kind, base.reason = "keep", note
        return base
    percent = abs(target - current) / current * 100 if current else Decimal("100")
    if percent > BIG_CHANGE_PERCENT and not rule.allow_big_change:
        base.reason = f"change {percent:.1f}% is over 50% (set allow_big_change to allow)"
        return base
    base.kind, base.reason = "change", note
    return base


def _pool() -> ThreadPoolExecutor:
    return ThreadPoolExecutor(max_workers=READ_WORKERS, thread_name_prefix="market")


def fetch_market(client: OffersClient, game_id: str, pool: ThreadPoolExecutor | None = None) -> list[Offer]:
    """Every page of the public market for one game (one offer per package and region).
    Page 1 tells how many pages there are; the rest are read in parallel."""
    first = client.list_game(game_id=game_id, page_index=FIRST_PAGE, page_size=PAGE_SIZE)
    offers = [item.offer for item in first.results]
    last = min(first.total_pages, FIRST_PAGE + MAX_PAGES - 1)
    if not first.results or last <= FIRST_PAGE:
        return offers

    def page(index: int) -> list[Offer]:
        return [item.offer for item in
                client.list_game(game_id=game_id, page_index=index, page_size=PAGE_SIZE).results]

    indexes = range(FIRST_PAGE + 1, last + 1)
    if pool is None:
        with _pool() as own:
            rest = list(own.map(page, indexes))
    else:
        rest = list(pool.map(page, indexes))
    for chunk in rest:
        offers.extend(chunk)
    return offers


def fetch_markets(client: OffersClient, game_ids: list[str]) -> dict[str, list[Offer]]:
    """Markets of several games at once. Any error is raised (nothing is half-used)."""
    if not game_ids:
        return {}
    with _pool() as games, _pool() as pages:
        futures = {g: games.submit(fetch_market, client, g, pages) for g in game_ids}
        return {g: f.result() for g, f in futures.items()}


class Bidder:
    def __init__(
        self,
        client: OffersClient,
        audit: AuditLogger,
        config: BiddingConfig,
        *,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client = client
        self._clock = clock
        # offer id -> clock time before which no new search up to max_price is allowed
        self._probe_blocked_until: dict[str, float] = {}
        self._probing: set[str] = set()
        self._audit = audit
        self._config = config
        self._sleep = sleep
        self.config_changed = False
        # offer id -> held at min_price in the previous cycle (memory only, per bot run)
        self._held: dict[str, bool] = {}

    @property
    def config(self) -> BiddingConfig:
        return self._config

    def set_config(self, config: BiddingConfig) -> None:
        """Swap in settings re-read from bidding.toml between cycles."""
        self.config_changed = config != self._config
        self._config = config

    def _my_offers(self) -> dict[str, Offer]:
        found: dict[str, Offer] = {}
        for index in range(FIRST_PAGE, FIRST_PAGE + MAX_PAGES):
            page = self._client.list_mine(page_index=index, page_size=PAGE_SIZE)
            for offer in page.results:
                found[offer.id] = offer
            if not page.results or index >= page.total_pages:
                break
        return found

    def plan(self) -> CycleReport:
        """Reads only. Decides what each configured offer's price should be."""
        report = CycleReport()
        mine = self._my_offers()
        wanted = sorted({o.game_id for r in self._config.enabled_rules()
                         if (o := mine.get(r.id)) is not None and o.game_id})
        market: dict[str, list[Offer]] = fetch_markets(self._client, wanted)
        for rule in self._config.enabled_rules():
            offer = mine.get(rule.id)
            if offer is None:
                report.decisions.append(Decision(
                    offer_id=rule.id, label=rule.note or rule.id, kind="skip",
                    reason="not found in your TopUp offers",
                ))
                continue
            if not offer.game_id:
                report.decisions.append(Decision(
                    offer_id=offer.id, label=rule.note or offer.label(), kind="skip",
                    reason="offer has no gameId", current=offer.price.amount,
                ))
                continue
            # First cycle after start: no memory, so sitting exactly at min_price counts as held.
            was_held = self._held.get(offer.id, offer.price.amount == rule.min_price)
            now = self._clock()
            blocked_until = self._probe_blocked_until.get(offer.id, 0.0)
            may_probe = now >= blocked_until
            decision = decide(offer, market[offer.game_id], rule, self._config.undercut,
                              was_held=was_held and may_probe)
            probe = (decision.kind == "change" and decision.lowest_competitor is None
                     and was_held and may_probe)
            if probe:
                self._probing.add(offer.id)
            elif offer.id in self._probing:
                self._probing.discard(offer.id)
                if decision.held_at_floor:
                    # The search found the cheaper seller still there: back off.
                    self._probe_blocked_until[offer.id] = now + PROBE_BACKOFF_SECONDS
            if not may_probe and decision.kind == "keep" and decision.lowest_competitor is None:
                minutes = int((blocked_until - now) // 60) + 1
                decision.reason += f" (next search for a higher seller in ~{minutes} min)"
            # Stay "held" while searching or while waiting for the next search.
            self._held[offer.id] = decision.held_at_floor or probe or (
                was_held and not may_probe and decision.kind == "keep")
            report.decisions.append(decision)
        return report

    def run_cycle(self, *, dry_run: bool) -> CycleReport:
        report = self.plan()
        pilot_done = False
        stop = False
        for decision in report.changes():
            if stop:
                decision.result = "not_sent"
                continue
            decision.pilot = not pilot_done
            before = {"price": decision.current}
            after = {"price": decision.target}
            if dry_run:
                decision.result = "dry_run"
                self._audit.write(
                    action=ACTION_BID, entity_type="offer", entity_id=decision.offer_id,
                    before=before, after=after, dry_run=True, pilot=decision.pilot,
                    outcome="dry_run", message=decision.reason,
                )
                pilot_done = True
                continue

            if pilot_done:
                self._sleep(WRITE_DELAY_SECONDS)
            assert decision.target is not None
            try:
                status = self._client.change_price(
                    decision.offer_id, Money(amount=decision.target, currency=SUPPORTED_CURRENCY)
                )
            except WriteOutcomeUnknownError as exc:
                decision.result = "unknown"
                self._audit.write(
                    action=ACTION_BID, entity_type="offer", entity_id=decision.offer_id,
                    before=before, after=after, dry_run=False, pilot=decision.pilot,
                    outcome="unknown", http_status=exc.http_status, message=str(exc),
                )
                raise
            except EldoradoError as exc:
                decision.result = "failed"
                self._audit.write(
                    action=ACTION_BID, entity_type="offer", entity_id=decision.offer_id,
                    before=before, after=after, dry_run=False, pilot=decision.pilot,
                    outcome="failed", http_status=exc.http_status, message=str(exc),
                )
                if decision.pilot:
                    stop = True
                pilot_done = True
                continue

            decision.result = "success"
            self._audit.write(
                action=ACTION_BID, entity_type="offer", entity_id=decision.offer_id,
                before=before, after=after, dry_run=False, pilot=decision.pilot,
                outcome="success", http_status=status, message=decision.reason,
            )
            pilot_done = True
        return report
