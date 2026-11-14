"""`bidding.toml`: which offers the auto bidder may change, and their price limits (prd.md 9.1)."""

from __future__ import annotations

import threading
import tomllib
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from eldorado.core.exceptions import ConfigError

DEFAULT_BIDDING_PATH = Path("bidding.toml")
DEFAULT_UNDERCUT = Decimal("0.01")
DEFAULT_INTERVAL_SECONDS = 300
MIN_INTERVAL_SECONDS = 60

# Display names for Eldorado gameIds (only for nicer labels). Any game works without an entry:
# the name then comes from the offer's own seo alias. The bot itself never filters by game.
GAME_NAMES: dict[str, str] = {
    "59": "Call of Duty Mobile",
    "56": "Brawl Stars",
    "18": "Clash of Clans",
    "52": "Clash Royale",
    "70": "Roblox",
    "21": "PUBG Mobile",
    "254": "TikTok",
    "46": "Free Fire",
    "378": "Yalla Ludo",
    "385": "ChatGPT",
}
_ACRONYMS = {"uc", "cp", "pubg", "codm", "fc", "gta", "pc", "ea", "nba", "ff", "mlbb", "vp", "rp"}


def game_name(game_id: str | None, seo_alias: str | None = None, title: str | None = None) -> str:
    if game_id and game_id in GAME_NAMES:
        return GAME_NAMES[game_id]
    if seo_alias:
        words = [w for w in seo_alias.split("-") if w not in {"top", "up", "topup", "cheap", "purchase"}]
        return " ".join(w.upper() if w in _ACRONYMS else w.capitalize() for w in words) or seo_alias
    return title or (f"Game {game_id}" if game_id else "Unknown game")


def _decimal(value: Any) -> Any:
    # TOML floats are binary; go through str so 0.85 stays exactly 0.85.
    if isinstance(value, float | int):
        return Decimal(str(value))
    if isinstance(value, str):
        try:
            return Decimal(value.strip())
        except InvalidOperation:
            raise ValueError(f"not a number: {value!r}") from None
    return value


class OfferRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    min_price: Decimal
    max_price: Decimal | None = None
    allow_big_change: bool = False
    enabled: bool = True
    note: str | None = None

    @field_validator("min_price", "max_price", mode="before")
    @classmethod
    def _prices_decimal(cls, value: Any) -> Any:
        return _decimal(value)

    @field_validator("id")
    @classmethod
    def _id_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be empty")
        return value

    @model_validator(mode="after")
    def _limits(self) -> OfferRule:
        if self.min_price <= 0:
            raise ValueError("min_price must be greater than 0")
        if self.max_price is not None and self.max_price < self.min_price:
            raise ValueError("max_price must be >= min_price")
        return self


class BiddingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    undercut: Decimal = DEFAULT_UNDERCUT
    paused: bool = False  # global switch: a running bot reads it every cycle and sends nothing
    interval_seconds: int = Field(default=DEFAULT_INTERVAL_SECONDS, ge=MIN_INTERVAL_SECONDS)
    offers: list[OfferRule] = Field(default_factory=list)

    @field_validator("undercut", mode="before")
    @classmethod
    def _undercut_decimal(cls, value: Any) -> Any:
        return _decimal(value)

    @field_validator("undercut")
    @classmethod
    def _undercut_range(cls, value: Decimal) -> Decimal:
        if not Decimal("0.01") <= value <= Decimal("1.00"):
            raise ValueError("undercut must be between 0.01 and 1.00")
        return value

    @model_validator(mode="after")
    def _unique_ids(self) -> BiddingConfig:
        ids = [o.id for o in self.offers]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            raise ValueError(f"offer ids listed more than once: {', '.join(dupes)}")
        return self

    def enabled_rules(self) -> list[OfferRule]:
        return [o for o in self.offers if o.enabled]


def parse_bidding_config(data: Any, *, source: str = "bidding config") -> BiddingConfig:
    try:
        return BiddingConfig.model_validate(data)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in e['loc']) or 'file'}: {e['msg']}" for e in exc.errors()
        )
        raise ConfigError(f"{source} has errors: {problems}") from None


def load_bidding_config(
    path: Path = DEFAULT_BIDDING_PATH, *, require_enabled: bool = True
) -> BiddingConfig:
    if not path.exists():
        if not require_enabled:
            return BiddingConfig()
        raise ConfigError(
            f"{path} not found. Copy bidding.example.toml to {path} and add your offers "
            "(ids from `eldorado offers list`) with a min_price for each."
        )
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise ConfigError(f"{path} is not valid TOML: {exc}") from None
    config = parse_bidding_config(data, source=str(path))
    if require_enabled and not config.enabled_rules():
        raise ConfigError(f"{path} has no enabled [[offers]] entries.")
    return config


def _toml_str(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    escaped = "".join(ch if ch >= " " else " " for ch in escaped)
    return f'"{escaped}"'


def dump_bidding_config(config: BiddingConfig) -> str:
    lines = [
        "# Auto bidding config. Edited by `eldorado ui` or by hand.",
        "# min_price: never go below. max_price: highest price when searching upward.",
        "",
        f"undercut = {_toml_str(str(config.undercut))}",
        f"interval_seconds = {config.interval_seconds}",
        f"paused = {'true' if config.paused else 'false'}",
    ]
    for rule in config.offers:
        lines += ["", "[[offers]]", f"id = {_toml_str(rule.id)}"]
        if rule.note:
            lines.append(f"note = {_toml_str(rule.note)}")
        lines.append(f"min_price = {_toml_str(str(rule.min_price))}")
        if rule.max_price is not None:
            lines.append(f"max_price = {_toml_str(str(rule.max_price))}")
        if rule.allow_big_change:
            lines.append("allow_big_change = true")
        lines.append(f"enabled = {'true' if rule.enabled else 'false'}")
    return "\n".join(lines) + "\n"


# Held around every read-modify-write of bidding.toml inside one process (page + bot thread).
CONFIG_WRITE_LOCK = threading.RLock()


def save_bidding_config(config: BiddingConfig, path: Path = DEFAULT_BIDDING_PATH) -> None:
    """Write atomically: a crash mid-write never leaves a half file the bot would read."""
    text = dump_bidding_config(config)
    parse_bidding_config(tomllib.loads(text))  # round-trip check before touching the file
    with CONFIG_WRITE_LOCK:
        tmp = path.with_name(path.name + ".tmp")
        try:
            tmp.write_text(text, encoding="utf-8")
            tmp.replace(path)
        except OSError as exc:
            raise ConfigError(
                f"Could not save {path}: {exc.strerror or type(exc).__name__}. "
                "Is the file open or read-only?"
            ) from None
