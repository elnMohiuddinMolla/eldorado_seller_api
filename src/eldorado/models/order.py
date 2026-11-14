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
