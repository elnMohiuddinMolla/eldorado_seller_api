"""Data for the local web page (`eldorado ui`). Reads only; never writes to Eldorado."""

from __future__ import annotations

import time
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any

from eldorado.client.offers import OffersClient
from eldorado.core.audit import AuditLogger
from eldorado.core.bidding_config import (
    CONFIG_WRITE_LOCK,
    game_name,
    BiddingConfig,
    OfferRule,
    load_bidding_config,
    parse_bidding_config,
    save_bidding_config,
)
from eldorado.core.exceptions import ConfigError, EldoradoError
from eldorado.models.offer import Offer
from eldorado.services.bidding import Bidder, fetch_markets
from eldorado.services.offers import OfferService


CACHE_SECONDS = 60


def _s(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


class Dashboard:
    def __init__(self, client: OffersClient, config_path: Path, *,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._client = client
        self._path = config_path
        self._clock = clock
        self._cache: tuple[float, list[Offer], dict[str, list[Offer]]] | None = None

    def _eldorado_data(self, fresh: bool) -> tuple[list[Offer], dict[str, list[Offer]], float]:
        """My offers + markets. Reused for CACHE_SECONDS unless fresh=True (Reload button)."""
        now = self._clock()
        if not fresh and self._cache is not None and now - self._cache[0] < CACHE_SECONDS:
            return self._cache[1], self._cache[2], now - self._cache[0]
        offers = [o for o in OfferService(self._client, AuditLogger()).list_mine()
                  if o.state in ("Active", "Paused")]
        market = fetch_markets(self._client, sorted({o.game_id for o in offers if o.game_id}))
        self._cache = (now, offers, market)
        return offers, market, 0.0

    def config(self) -> BiddingConfig:
        return load_bidding_config(self._path, require_enabled=False)

    def rows(self, fresh: bool = False) -> dict[str, Any]:
        config = self.config()
        rules = {r.id: r for r in config.offers}
        # Every TopUp offer on the account, any game: new uploads appear, deleted ones vanish.
        offers, market, age = self._eldorado_data(fresh)

        def name(o: Offer) -> str:
            return game_name(o.game_id, o.seo_alias, o.title)

        rows = []
        for o in sorted(offers, key=lambda o: (name(o), o.price.amount)):
            low = next((m for m in market.get(o.game_id or "", [])
                        if m.product_key() == o.product_key()), None)
            rule = rules.get(o.id)
            rows.append({
                "id": o.id,
                "game": name(o),
                "package": o.package_name() or "?",
                "state": o.state,
                "price": _s(o.price.amount),
                "currency": o.price.currency,
                "lowest": _s(low.price.amount) if low else None,
                "lowest_is_me": bool(low and low.id == o.id),
                "min_price": _s(rule.min_price) if rule else None,
                "max_price": _s(rule.max_price) if rule else None,
                "enabled": bool(rule and rule.enabled),
                "allow_big_change": bool(rule and rule.allow_big_change),
            })
        return {"undercut": str(config.undercut), "interval_seconds": config.interval_seconds,
                "paused": config.paused, "rows": rows, "data_age_seconds": int(age)}

    def save(self, payload: dict[str, Any]) -> BiddingConfig:
        """Merge edited rows into the file. Rules for offers not on the page are kept."""
        with CONFIG_WRITE_LOCK:
            return self._save(payload)

    def _save(self, payload: dict[str, Any]) -> BiddingConfig:
        current = self.config()
        edited: list[OfferRule] = []
        errors: list[str] = []
        for i, row in enumerate(payload.get("rows") or []):
            min_price = (row.get("min_price") or "").strip()
            max_price = (row.get("max_price") or "").strip()
            label = f"{row.get('game', '')} {row.get('package', '')}".strip() or f"row {i + 1}"
            if not min_price:
                if row.get("enabled") or max_price:
                    errors.append(f"{label}: min price is required")
                continue  # no rule for this offer
            try:
                edited.append(parse_bidding_config({"offers": [{
                    "id": row.get("id", ""), "note": label, "min_price": min_price,
                    "max_price": max_price or None, "enabled": bool(row.get("enabled")),
                    "allow_big_change": bool(row.get("allow_big_change")),
                }]}).offers[0])
            except ConfigError as exc:
                errors.append(f"{label}: {str(exc).split('has errors: ', 1)[-1]}")
        if errors:
            raise ConfigError("; ".join(errors))
        shown = {str(r.get("id")) for r in payload.get("rows") or []}
        kept = [r for r in current.offers if r.id not in shown]
        if payload.get("rows"):
            # Drop settings of offers that no longer exist on Eldorado (deleted by the seller).
            try:
                existing = {o.id for o in OfferService(self._client, AuditLogger()).list_mine()}
            except EldoradoError:
                existing = None  # cannot check now: keep everything
            if existing is not None:
                kept = [r for r in kept if r.id in existing]
        config = parse_bidding_config({
            "undercut": payload.get("undercut", str(current.undercut)),
            "interval_seconds": payload.get("interval_seconds", current.interval_seconds),
            "paused": bool(payload.get("paused", current.paused)),
            "offers": [r.model_dump() for r in kept + edited],
        })
        save_bidding_config(config, self._path)
        return config

    def preview(self) -> list[dict[str, Any]]:
        """What the bot would do now, with the saved file. Reads only, writes nothing."""
        config = self.config()
        if not config.enabled_rules():
            return []
        report = Bidder(self._client, AuditLogger(), config).plan()
        return [{
            "id": d.offer_id, "label": d.label, "action": d.kind, "reason": d.reason,
            "current": _s(d.current), "lowest": _s(d.lowest_competitor), "target": _s(d.target),
        } for d in report.decisions]
