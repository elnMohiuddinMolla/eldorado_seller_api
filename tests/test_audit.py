from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from eldorado.core import audit as audit_mod
from eldorado.core.audit import AuditLogger
from eldorado.core.exceptions import AuditLogError

from .conftest import CLIENT_SECRET

EXPECTED_KEYS = {
    "ts", "run_id", "action", "entity_type", "entity_id", "before", "after",
    "dry_run", "pilot", "outcome", "http_status", "message",
}


def test_writes_one_json_line_with_all_fields(tmp_path: Path) -> None:
    logger = AuditLogger(tmp_path / "logs" / "audit.jsonl", run_id="run1")
    logger.write(
        action="offer.update", entity_type="offer", entity_id="123",
        before={"price": Decimal("5.99")}, after={"price": Decimal("4.99")},
        outcome="success", dry_run=False, pilot=True, http_status=200,
    )
    lines = (tmp_path / "logs" / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert set(record) == EXPECTED_KEYS
    assert record["before"] == {"price": "5.99"}
    assert record["after"] == {"price": "4.99"}
    assert record["ts"].endswith("Z")
    assert record["run_id"] == "run1"


def test_appends(tmp_path: Path) -> None:
    logger = AuditLogger(tmp_path / "audit.jsonl")
    for _ in range(3):
        logger.write(action="order.deliver", entity_type="order", entity_id="1",
                     outcome="dry_run", dry_run=True)
    assert len((tmp_path / "audit.jsonl").read_text(encoding="utf-8").splitlines()) == 3


def test_message_is_masked(tmp_path: Path, settings) -> None:  # type: ignore[no-untyped-def]
    logger = AuditLogger(tmp_path / "audit.jsonl")
    logger.write(action="order.deliver", entity_type="order", entity_id="1",
                 outcome="failed", dry_run=False, message=f"oops {CLIENT_SECRET}")
    assert CLIENT_SECRET not in (tmp_path / "audit.jsonl").read_text(encoding="utf-8")


def test_unwritable_path_raises_audit_error(tmp_path: Path) -> None:
    blocker = tmp_path / "not_a_dir"
    blocker.write_text("x", encoding="utf-8")
    logger = AuditLogger(blocker / "audit.jsonl")
    with pytest.raises(AuditLogError, match="Could not write the audit log"):
        logger.write(action="order.deliver", entity_type="order", entity_id="1",
                     outcome="dry_run", dry_run=True)


def test_rotates_large_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(audit_mod, "ROTATE_BYTES", 10)
    path = tmp_path / "audit.jsonl"
    path.write_text("x" * 50, encoding="utf-8")
    AuditLogger(path).write(action="order.deliver", entity_type="order", entity_id="1",
                            outcome="dry_run", dry_run=True)
    rotated = list(tmp_path.glob("audit-*.jsonl"))
    assert len(rotated) == 1
    assert len(path.read_text(encoding="utf-8").splitlines()) == 1
