"""Settings read from `.env` via pydantic-settings."""

from __future__ import annotations

from datetime import date

from pydantic import SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from eldorado.core.exceptions import ConfigError
from eldorado.core.logging import register_secret

# eldorado.gg answers every request with 301 -> www.eldorado.gg (seen 2026-11-14),
# and the Swagger server is www.eldorado.gg.
DEFAULT_BASE_URL = "https://www.eldorado.gg"
EXPIRY_WARNING_DAYS = 7


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ELDORADO_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    client_id: str
    client_secret: SecretStr
    credential_expires: date | None = None
    base_url: str = DEFAULT_BASE_URL
    timeout_seconds: float = 20.0

    @field_validator("credential_expires", mode="before")
    @classmethod
    def _blank_date_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("client_id")
    @classmethod
    def _client_id_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be empty")
        return value

    @field_validator("client_secret")
    @classmethod
    def _secret_not_blank(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("must not be empty")
        register_secret(value.get_secret_value())
        return value

    def days_until_expiry(self, today: date | None = None) -> int | None:
        if self.credential_expires is None:
            return None
        return (self.credential_expires - (today or date.today())).days


def load_settings() -> Settings:
    """Load settings, turning validation errors into a ConfigError.

    The pydantic error is dropped on purpose: its text includes input values,
    which could contain the Client secret.
    """
    try:
        return Settings()  # type: ignore[call-arg]
    except ValidationError as exc:
        fields = sorted({".".join(str(p) for p in err["loc"]) for err in exc.errors()})
        names = ", ".join(f"ELDORADO_{f.upper()}" for f in fields)
        raise ConfigError(
            f"Invalid or missing settings in .env: {names}. "
            "Copy .env.example to .env and fill it in."
        ) from None
