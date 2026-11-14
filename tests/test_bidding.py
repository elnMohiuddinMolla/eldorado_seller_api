from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import respx

from eldorado.client.base import BaseClient
from eldorado.client.offers import GAME_OFFERS_PATH, MY_OFFERS_PATH, OffersClient, change_price_path
from eldorado.core.audit import AuditLogger
from eldorado.core.bidding_config import BiddingConfig, OfferRule, load_bidding_config
from eldorado.core.exceptions import ConfigError, WriteOutcomeUnknownError
from eldorado.models.offer import Offer
from eldorado.services.bidding import Bidder, decide

from .factories import market, offer_json, page

U = Decimal("0.01")


def _offer(offer_id: str, price: float, **kw: object) -> Offer:
    return Offer.model_validate(offer_json(offer_id, price, **kw))  # type: ignore[arg-type]


def _rule(min_price: str = "0.50", max_price: str | None = None, **kw: object) -> OfferRule:
    return OfferRule(id="mine", min_price=Decimal(min_price),
                     max_price=Decimal(max_price) if max_price else None, **kw)  # type: ignore[arg-type]


# ---------- decide(): the pricing rules (prd.md 9.1) ----------

def test_undercuts_lowest_competitor_by_one_cent() -> None:
    d = decide(_offer("mine", 1.00), [_offer("a", 0.95, user_id="x"), _offer("b", 0.99, user_id="y")], _rule(), U)
    assert d.kind == "change"
    assert d.target == Decimal("0.94")
    assert d.lowest_competitor == Decimal("0.95")


def test_raises_price_when_already_cheapest() -> None:
    d = decide(_offer("mine", 0.80), [_offer("a", 0.95, user_id="x")], _rule(), U)
    assert d.kind == "change"
    assert d.target == Decimal("0.94")


def test_never_goes_below_min_price() -> None:
    d = decide(_offer("mine", 1.00), [_offer("a", 0.70, user_id="x")], _rule(min_price="0.90"), U)
    assert d.target == Decimal("0.90")
    assert "min_price" in d.reason


def test_keeps_when_already_at_floor_and_competitor_is_lower() -> None:
    d = decide(_offer("mine", 0.90), [_offer("a", 0.70, user_id="x")], _rule(min_price="0.90"), U)
    assert d.kind == "keep"


def test_raise_is_capped_at_max_price() -> None:
    d = decide(_offer("mine", 0.80), [_offer("a", 2.00, user_id="x")], _rule(max_price="0.95", allow_big_change=True), U)
    assert d.target == Decimal("0.95")


def test_keeps_when_already_at_target() -> None:
    d = decide(_offer("mine", 0.94), [_offer("a", 0.95, user_id="x")], _rule(), U)
    assert d.kind == "keep"


def test_ignores_own_offers_other_packages_and_inactive_offers() -> None:
    competitors = [
        _offer("mine", 1.00),                                  # itself
        _offer("other-mine", 0.60),                            # my other offer
        _offer("a", 0.70, user_id="x", package="400 CP"),      # other package
        _offer("b", 0.75, user_id="y", state="Paused"),        # not active
        _offer("c", 0.98, user_id="z"),                        # the real competitor
    ]
    d = decide(_offer("mine", 1.00), competitors, _rule(), U)
    assert d.lowest_competitor == Decimal("0.98")
    assert d.target == Decimal("0.97")


def test_no_competitors_keeps_price() -> None:
    d = decide(_offer("mine", 1.00), [], _rule(), U)
    assert d.kind == "keep"
    assert d.target is None


def test_big_change_is_skipped_unless_allowed() -> None:
    comp = [_offer("a", 3.00, user_id="x")]
    assert decide(_offer("mine", 1.00), comp, _rule(), U).kind == "skip"
    assert decide(_offer("mine", 1.00), comp, _rule(allow_big_change=True), U).kind == "change"


def test_non_usd_and_paused_offers_are_skipped() -> None:
    comp = [_offer("a", 0.95, user_id="x")]
    assert decide(_offer("mine", 1.00, currency="EUR"), comp, _rule(), U).kind == "skip"
    assert decide(_offer("mine", 1.00, state="Paused"), comp, _rule(), U).kind == "skip"


def test_target_rounds_down_to_cents() -> None:
    d = decide(_offer("mine", 1.00), [_offer("a", 0.955, user_id="x")], _rule(), U)
    assert d.target == Decimal("0.94")


# ---------- Bidder.run_cycle(): reads, pilot, dry-run ----------

@pytest.fixture
def config() -> BiddingConfig:
    return BiddingConfig(offers=[
        OfferRule(id="o1", min_price=Decimal("0.50")),
        OfferRule(id="o2", min_price=Decimal("0.50")),
    ])


@pytest.fixture
def mocked(api: respx.MockRouter, token_route: respx.Route) -> respx.MockRouter:
    api.get(MY_OFFERS_PATH).mock(return_value=httpx.Response(200, json=page([
        offer_json("o1", 1.00), offer_json("o2", 1.00, package="400 CP"),
    ])))
    api.get(GAME_OFFERS_PATH).mock(return_value=httpx.Response(200, json=market(
        offer_json("o1", 1.00), offer_json("o2", 1.00, package="400 CP"),
        offer_json("c1", 0.95, user_id="rival"), offer_json("c2", 0.97, user_id="rival", package="400 CP"),
    )))
    return api


def _writes(api: respx.MockRouter) -> list[httpx.Request]:
    return [c.request for c in api.calls if c.request.method == "PUT"]


def _records(path: Path) -> list[dict[str, object]]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]


def test_cycle_reads_market_once_per_game(mocked: respx.MockRouter, base: BaseClient,
                                          config: BiddingConfig, tmp_path: Path) -> None:
    report = Bidder(OffersClient(base), AuditLogger(tmp_path / "a.jsonl"), config,
                    sleep=lambda s: None).plan()
    assert [d.target for d in report.decisions] == [Decimal("0.94"), Decimal("0.96")]
    assert mocked.routes[1].call_count == 1  # GAME_OFFERS_PATH
    assert _writes(mocked) == []


def test_cycle_dry_run_sends_no_writes(mocked: respx.MockRouter, base: BaseClient,
                                       config: BiddingConfig, tmp_path: Path) -> None:
    audit = tmp_path / "a.jsonl"
    Bidder(OffersClient(base), AuditLogger(audit), config, sleep=lambda s: None).run_cycle(dry_run=True)
    assert _writes(mocked) == []
    recs = _records(audit)
    assert [r["outcome"] for r in recs] == ["dry_run", "dry_run"]
    assert recs[0]["pilot"] is True and recs[1]["pilot"] is False
    assert recs[0]["before"] == {"price": "1.0"} and recs[0]["after"] == {"price": "0.94"}


def test_cycle_live_sends_price_body(mocked: respx.MockRouter, base: BaseClient,
                                     config: BiddingConfig, tmp_path: Path) -> None:
    r1 = mocked.put(change_price_path("o1")).mock(return_value=httpx.Response(200, json={"amount": 0.94, "currency": "USD"}))
    r2 = mocked.put(change_price_path("o2")).mock(return_value=httpx.Response(200, json={"amount": 0.96, "currency": "USD"}))
    sleeps: list[float] = []
    report = Bidder(OffersClient(base), AuditLogger(tmp_path / "a.jsonl"), config,
                    sleep=sleeps.append).run_cycle(dry_run=False)
    assert json.loads(r1.calls.last.request.content) == {"amount": 0.94, "currency": "USD"}
    assert r2.call_count == 1
    assert [d.result for d in report.changes()] == ["success", "success"]
    assert sleeps == [1.0]  # delay between writes


def test_failed_pilot_stops_the_cycle(mocked: respx.MockRouter, base: BaseClient,
                                      config: BiddingConfig, tmp_path: Path) -> None:
    mocked.put(change_price_path("o1")).mock(return_value=httpx.Response(400, json={"title": "bad"}))
    r2 = mocked.put(change_price_path("o2")).mock(return_value=httpx.Response(200))
    report = Bidder(OffersClient(base), AuditLogger(tmp_path / "a.jsonl"), config,
                    sleep=lambda s: None).run_cycle(dry_run=False)
    assert r2.call_count == 0
    assert [d.result for d in report.changes()] == ["failed", "not_sent"]


def test_unknown_write_outcome_is_not_retried_and_raises(mocked: respx.MockRouter, base: BaseClient,
                                                         config: BiddingConfig, tmp_path: Path) -> None:
    r1 = mocked.put(change_price_path("o1")).mock(return_value=httpx.Response(503))
    r2 = mocked.put(change_price_path("o2")).mock(return_value=httpx.Response(200))
    audit = tmp_path / "a.jsonl"
    with pytest.raises(WriteOutcomeUnknownError):
        Bidder(OffersClient(base), AuditLogger(audit), config, sleep=lambda s: None).run_cycle(dry_run=False)
    assert r1.call_count == 1 and r2.call_count == 0
    assert _records(audit)[0]["outcome"] == "unknown"


def test_offer_missing_from_account_is_skipped(mocked: respx.MockRouter, base: BaseClient, tmp_path: Path) -> None:
    config = BiddingConfig(offers=[OfferRule(id="gone", min_price=Decimal("1"))])
    report = Bidder(OffersClient(base), AuditLogger(tmp_path / "a.jsonl"), config).plan()
    assert report.decisions[0].kind == "skip"
    assert "not found" in report.decisions[0].reason


# ---------- bidding.toml ----------

def test_config_loads_exact_decimals(tmp_path: Path) -> None:
    p = tmp_path / "b.toml"
    p.write_text('undercut = 0.01\n[[offers]]\nid = "x"\nmin_price = 0.85\nmax_price = "1.20"\n', encoding="utf-8")
    cfg = load_bidding_config(p)
    assert cfg.undercut == Decimal("0.01")
    assert cfg.offers[0].min_price == Decimal("0.85")
    assert cfg.interval_seconds == 300


@pytest.mark.parametrize("body, fragment", [
    ('[[offers]]\nid = "x"\n', "min_price"),
    ('[[offers]]\nid = "x"\nmin_price = "0"\n', "greater than 0"),
    ('[[offers]]\nid = "x"\nmin_price = "2"\nmax_price = "1"\n', "max_price"),
    ('interval_seconds = 5\n[[offers]]\nid = "x"\nmin_price = "1"\n', "interval_seconds"),
    ('undercut = "0"\n[[offers]]\nid = "x"\nmin_price = "1"\n', "undercut"),
    ('[[offers]]\nid = "x"\nmin_price = "1"\n[[offers]]\nid = "x"\nmin_price = "1"\n', "more than once"),
    ('[[offers]]\nid = "x"\nmin_price = "1"\nenabled = false\n', "no enabled"),
    ('[[offers]]\nid = "x"\nmin_prise = "1"\n', "min_prise"),
])
def test_config_rejects_unsafe_values(tmp_path: Path, body: str, fragment: str) -> None:
    p = tmp_path / "b.toml"
    p.write_text(body, encoding="utf-8")
    with pytest.raises(ConfigError, match=fragment):
        load_bidding_config(p)


def test_missing_config_explains_what_to_do(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="bidding.example.toml"):
        load_bidding_config(tmp_path / "nope.toml")


def test_example_config_is_valid() -> None:
    example = Path(__file__).resolve().parents[1] / "bidding.example.toml"
    assert len(load_bidding_config(example).enabled_rules()) == 2


def test_offer_without_package_is_never_compared() -> None:
    raw = offer_json("mine", 1.00)
    raw["attributes"] = []
    d = decide(Offer.model_validate(raw), [_offer("a", 0.50, user_id="x")], _rule(), U)
    assert d.kind == "skip"
    assert "package unknown" in d.reason


def test_keeps_price_when_market_lists_us_as_lowest() -> None:
    d = decide(_offer("mine", 0.90), [_offer("mine", 0.90)], _rule(), U)
    assert d.kind == "keep"
    assert "you are the listed lowest" in d.reason


def test_label_uses_game_and_package() -> None:
    assert _offer("mine", 1.0, package="80 CP").label() == "codm-top-up 80 CP"


# ---------- floor recovery: cheaper seller below min_price disappears ----------

def test_held_offer_goes_to_max_when_cheaper_seller_is_gone() -> None:
    rule = _rule(min_price="4.20", max_price="5.00")
    d = decide(_offer("mine", 4.20), [_offer("mine", 4.20)], rule, U, was_held=True)
    assert d.kind == "change" and d.target == Decimal("5.00")


def test_listed_lowest_without_hold_keeps_price() -> None:
    rule = _rule(min_price="4.20", max_price="5.00")
    d = decide(_offer("mine", 4.49), [_offer("mine", 4.49)], rule, U, was_held=False)
    assert d.kind == "keep"


def test_held_without_max_price_stays_at_min() -> None:
    d = decide(_offer("mine", 4.20), [_offer("mine", 4.20)], _rule(min_price="4.20"), U, was_held=True)
    assert d.kind == "keep" and "set max_price" in d.reason


def test_full_story_420_then_449(api: respx.MockRouter, token_route: respx.Route,
                                 base: BaseClient, tmp_path: Path) -> None:
    """min 4.20. Seller at 4.00 -> hold 4.20. 4.00 sells out -> probe 5.00 -> see 4.50 -> 4.49."""
    config = BiddingConfig(offers=[OfferRule(id="o1", min_price=Decimal("4.20"), max_price=Decimal("5.00"))])
    price = {"v": 4.65}
    rivals = {"v": [offer_json("cheap", 4.00, user_id="r1"), offer_json("mid", 4.50, user_id="r2")]}

    def my_offers(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=page([offer_json("o1", price["v"])]))

    def market_view(request: httpx.Request) -> httpx.Response:
        everyone = rivals["v"] + [offer_json("o1", price["v"])]
        lowest = min(everyone, key=lambda o: o["pricePerUnit"]["amount"])  # API shows ONE per package
        return httpx.Response(200, json=market(lowest))

    def change(request: httpx.Request) -> httpx.Response:
        price["v"] = json.loads(request.content)["amount"]
        return httpx.Response(200, json=json.loads(request.content))

    api.get(MY_OFFERS_PATH).mock(side_effect=my_offers)
    api.get(GAME_OFFERS_PATH).mock(side_effect=market_view)
    api.put(change_price_path("o1")).mock(side_effect=change)
    bot = Bidder(OffersClient(base), AuditLogger(tmp_path / "a.jsonl"), config, sleep=lambda s: None)

    bot.run_cycle(dry_run=False)
    assert price["v"] == 4.20                       # 4.00 is below min: hold at min
    bot.run_cycle(dry_run=False)
    assert price["v"] == 4.20                       # still there: stay
    rivals["v"] = [offer_json("mid", 4.50, user_id="r2")]   # 4.00 sold out
    bot.run_cycle(dry_run=False)
    assert price["v"] == 5.00                       # we are listed lowest: probe up
    bot.run_cycle(dry_run=False)
    assert price["v"] == 4.49                       # next seller visible: undercut
    bot.run_cycle(dry_run=False)
    assert price["v"] == 4.49                       # listed lowest, not held: stay (no loop)


def test_tie_at_min_does_not_loop_between_min_and_max(api: respx.MockRouter, token_route: respx.Route,
                                                      base: BaseClient, tmp_path: Path) -> None:
    """A rival sits exactly at our min. The market sometimes lists us instead of them.
    After one search up to max that ends back at min, the bot waits 30 min before searching again."""
    from eldorado.services.bidding import PROBE_BACKOFF_SECONDS

    config = BiddingConfig(offers=[OfferRule(id="o1", min_price=Decimal("4.20"), max_price=Decimal("5.00"))])
    price = {"v": 4.20}
    listed = {"who": "me"}
    now = {"t": 0.0}

    def my_offers(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=page([offer_json("o1", price["v"])]))

    def market_view(request: httpx.Request) -> httpx.Response:
        rival = offer_json("r", 4.20, user_id="rival")
        me = offer_json("o1", price["v"])
        if price["v"] > 4.20:
            return httpx.Response(200, json=market(rival))          # we went up: rival is lowest
        return httpx.Response(200, json=market(me if listed["who"] == "me" else rival))

    def change(request: httpx.Request) -> httpx.Response:
        price["v"] = json.loads(request.content)["amount"]
        return httpx.Response(200)

    api.get(MY_OFFERS_PATH).mock(side_effect=my_offers)
    api.get(GAME_OFFERS_PATH).mock(side_effect=market_view)
    put = api.put(change_price_path("o1")).mock(side_effect=change)
    bot = Bidder(OffersClient(base), AuditLogger(tmp_path / "a.jsonl"), config,
                 sleep=lambda s: None, clock=lambda: now["t"])

    bot.run_cycle(dry_run=False)          # listed lowest at min, held -> search
    assert price["v"] == 5.00
    bot.run_cycle(dry_run=False)          # rival at 4.20 still there -> back to min, back off
    assert price["v"] == 4.20
    for _ in range(5):                    # market lists us again, but no new search for 30 min
        now["t"] += 300
        report = bot.run_cycle(dry_run=False)
        assert price["v"] == 4.20
    assert "next search" in report.decisions[0].reason
    assert put.call_count == 2
    now["t"] = PROBE_BACKOFF_SECONDS + 1  # backoff over -> one new search is allowed
    bot.run_cycle(dry_run=False)
    assert price["v"] == 5.00
