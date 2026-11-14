"""Data for the local web page (`eldorado ui`). Reads only; never writes to Eldorado."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from eldorado.client.offers import OffersClient
from eldorado.core.audit import DEFAULT_AUDIT_PATH, AuditLogger
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
from eldorado.services.bidding import Bidder, BidderMemory, fetch_markets
from eldorado.services.offers import OfferService


CACHE_SECONDS = 60


def _s(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _text(value: Any, what: str) -> str:
    """A price box from the page: text, or a plain number. Anything else is a ConfigError."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, int | float) and not isinstance(value, bool):
        return str(value)
    raise ConfigError(f"{what} must be text or a number")


def _flag(value: Any, what: str) -> bool:
    if value is None:
        return False
    if not isinstance(value, bool):
        raise ConfigError(f"{what} must be true or false")
    return value


class Dashboard:
    def __init__(self, client: OffersClient, config_path: Path, *,
                 clock: Callable[[], float] = time.monotonic,
                 bot_memory: Callable[[], BidderMemory | None] = lambda: None) -> None:
        """bot_memory: the running bot's between-cycle memory (`eldorado app`), so the preview
        shows what the bot itself would do. Without a bot the preview starts from nothing."""
        self._client = client
        self._path = config_path
        self._clock = clock
        self._bot_memory = bot_memory
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
        rows = payload.get("rows") or []
        if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
            raise ConfigError("rows must be a list of objects")
        if "paused" in payload:
            _flag(payload["paused"], "paused")
        edited: list[OfferRule] = []
        errors: list[str] = []
        for i, row in enumerate(rows):
            label = f"{row.get('game', '')} {row.get('package', '')}".strip() or f"row {i + 1}"
            try:
                min_price = _text(row.get("min_price"), "min price")
                max_price = _text(row.get("max_price"), "max price")
                enabled = _flag(row.get("enabled"), "ON")
                allow_big = _flag(row.get("allow_big_change"), "big change")
            except ConfigError as exc:
                errors.append(f"{label}: {exc}")
                continue
            if not min_price:
                if enabled or max_price:
                    errors.append(f"{label}: min price is required")
                continue  # no rule for this offer
            try:
                edited.append(parse_bidding_config({"offers": [{
                    "id": row.get("id", ""), "note": label, "min_price": min_price,
                    "max_price": max_price or None, "enabled": enabled,
                    "allow_big_change": allow_big,
                }]}).offers[0])
            except ConfigError as exc:
                errors.append(f"{label}: {str(exc).split('has errors: ', 1)[-1]}")
        if errors:
            raise ConfigError("; ".join(errors))
        shown = {str(r.get("id")) for r in rows}
        kept = [r for r in current.offers if r.id not in shown]
        if rows:
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
            "paused": payload.get("paused", current.paused),
            "offers": [r.model_dump() for r in kept + edited],
        })
        save_bidding_config(config, self._path)
        return config

    def preview(self) -> list[dict[str, Any]]:
        """What the bot would do now, with the saved file. Reads only, writes nothing."""
        config = self.config()
        if not config.enabled_rules():
            return []
        bidder = Bidder(self._client, AuditLogger(), config)
        memory = self._bot_memory()
        if memory is not None:
            bidder.restore_memory(memory)  # a copy: planning here never changes the bot
        report = bidder.plan()
        return [{
            "id": d.offer_id, "label": d.label, "action": d.kind, "reason": d.reason,
            "current": _s(d.current), "lowest": _s(d.lowest_competitor), "target": _s(d.target),
        } for d in report.decisions]

    def activity(self, limit: int = 15, audit_path: Path = DEFAULT_AUDIT_PATH) -> dict[str, Any]:
        """Recent live price changes from the audit log, newest first, plus today's count.
        Reads only the local log file (no Eldorado call)."""
        labels = {r.id: r.note or r.id[:8] for r in self.config().offers}
        if self._cache is not None:
            for o in self._cache[1]:
                labels.setdefault(o.id, f"{game_name(o.game_id, o.seo_alias, o.title)} {o.package_name()}")
        items: list[dict[str, Any]] = []
        today = datetime.now().astimezone().date()
        changed_today = 0
        try:
            lines = audit_path.read_text(encoding="utf-8").splitlines()[-2000:]
        except OSError:
            lines = []
        for line in lines:
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if rec.get("dry_run") or rec.get("entity_type") != "offer":
                continue
            try:
                ts = datetime.fromisoformat(str(rec["ts"]).replace("Z", "+00:00")).astimezone()
            except (KeyError, ValueError):
                continue
            if rec.get("outcome") == "success" and ts.date() == today:
                changed_today += 1
            items.append({
                "time": ts.strftime("%H:%M"), "date": ts.strftime("%d %b"),
                "label": labels.get(str(rec.get("entity_id")), str(rec.get("entity_id"))[:8]),
                "before": (rec.get("before") or {}).get("price"),
                "after": (rec.get("after") or {}).get("price"),
                "outcome": rec.get("outcome"), "action": rec.get("action"),
            })
        return {"changed_today": changed_today, "items": list(reversed(items))[:limit]}
