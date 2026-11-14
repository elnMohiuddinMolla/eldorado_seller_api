"""Seller online/offline status (F7)."""

from __future__ import annotations

from eldorado.client.account import AccountClient
from eldorado.core.audit import AuditLogger, record_unknown
from eldorado.core.exceptions import EldoradoError, WriteOutcomeUnknownError

ACTION_STATUS = "seller.status"


class AccountService:
    def __init__(self, client: AccountClient | None, audit: AuditLogger) -> None:
        self._client = client
        self._audit = audit

    def set_online(self, online: bool, *, dry_run: bool) -> int | None:
        after = {"online": online}
        if dry_run:
            self._audit.write(action=ACTION_STATUS, entity_type="seller_status", entity_id="me",
                              after=after, dry_run=True, outcome="dry_run")
            return None
        if self._client is None:
            raise RuntimeError("AccountService needs a client for live calls")
        try:
            status = self._client.set_online(online)
        except WriteOutcomeUnknownError as exc:
            record_unknown(self._audit, exc, action=ACTION_STATUS, entity_type="seller_status",
                           entity_id="me", after=after)
            raise
        except EldoradoError as exc:
            self._audit.write(action=ACTION_STATUS, entity_type="seller_status", entity_id="me",
                              after=after, dry_run=False, outcome="failed",
                              http_status=exc.http_status, message=str(exc))
            raise
        self._audit.write(action=ACTION_STATUS, entity_type="seller_status", entity_id="me",
                          after=after, dry_run=False, outcome="success", http_status=status)
        return status
