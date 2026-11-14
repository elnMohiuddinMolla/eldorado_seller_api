"""Append-only audit log at `logs/audit.jsonl` (format: database.md section 2)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from eldorado.core.exceptions import AuditLogError
from eldorado.core.logging import redact

DEFAULT_AUDIT_PATH = Path("logs") / "audit.jsonl"
ROTATE_BYTES = 10 * 1024 * 1024

Outcome = Literal["success", "failed", "unknown", "skipped", "dry_run"]
EntityType = Literal["offer", "order", "seller_status"]


class AuditRecord(BaseModel):
    ts: str
    run_id: str
    action: str
    entity_type: EntityType
    entity_id: str
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    dry_run: bool
    pilot: bool
    outcome: Outcome
    http_status: int | None
    message: str | None


def _jsonable(values: dict[str, Any] | None) -> dict[str, Any] | None:
    """Money stays exact: Decimal values are written as strings."""
    if values is None:
        return None
    return {k: (str(v) if isinstance(v, Decimal) else v) for k, v in values.items()}


class AuditLogger:
    def __init__(self, path: Path = DEFAULT_AUDIT_PATH, run_id: str | None = None) -> None:
        self.path = path
        self.run_id = run_id or uuid.uuid4().hex[:12]

    def write(
        self,
        *,
        action: str,
        entity_type: EntityType,
        entity_id: str,
        outcome: Outcome,
        dry_run: bool,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        pilot: bool = False,
        http_status: int | None = None,
        message: str | None = None,
    ) -> AuditRecord:
        record = AuditRecord(
            ts=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            run_id=self.run_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before=_jsonable(before),
            after=_jsonable(after),
            dry_run=dry_run,
            pilot=pilot,
            outcome=outcome,
            http_status=http_status,
            message=redact(message) if message else None,
        )
        line = redact(json.dumps(record.model_dump(), ensure_ascii=False, separators=(",", ":")))
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._rotate_if_needed()
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except OSError as exc:
            raise AuditLogError(
                f"Could not write the audit log at {self.path.resolve()}: "
                f"{exc.strerror or type(exc).__name__}. On Windows, Controlled Folder Access "
                "may block Python from writing inside Documents."
            ) from None
        return record

    def _rotate_if_needed(self) -> None:
        if not self.path.exists() or self.path.stat().st_size <= ROTATE_BYTES:
            return
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        target = self.path.with_name(f"audit-{stamp}.jsonl")
        n = 1
        while target.exists():
            target = self.path.with_name(f"audit-{stamp}-{n}.jsonl")
            n += 1
        self.path.rename(target)
