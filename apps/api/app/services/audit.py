"""Automatic AuditLog instrumentation via SQLAlchemy event listeners.

Tracks create/update/delete on a curated whitelist of NF525-relevant tables
(transactions, Z reports, cash drawers, products, users, clients) and writes
``AuditLog`` rows in the same flush so the audit trail is atomic with the
business operation.

Design notes:
- ``before_flush`` collects pending changes and queues AuditLog instances on
  the session. They are then included in the same flush so a rollback rolls
  back both the business write and its audit row.
- The user id is read from a ContextVar populated by the audit middleware.
- For updates we only persist the diff of a small set of "sensitive" fields
  per entity to keep the table compact and to avoid logging large payloads.
- The audit trail is never the source of truth for fiscal data — the NF525
  hash chain on transactions remains the legal anchor (P1-001).
"""

from __future__ import annotations

import enum
import hashlib
import re
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Iterable

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from app.core.audit_context import get_current_user_id
from app.models.audit import AuditLog
from app.models.client import Client, LoyaltyAccount
from app.models.pos import CashDrawer, Transaction, ZReport
from app.models.product import Product
from app.models.user import User


# Per-entity whitelist of fields whose change is recorded in AuditLog.data.
# Hashed/secret values (pin_hash, password_hash) appear as a boolean flag only.
_SENSITIVE_FIELDS: dict[type, tuple[str, ...]] = {
    Transaction: ("total_ttc", "hash_chain", "transaction_type", "client_id"),
    CashDrawer: ("opening_amount", "closing_amount", "is_open"),
    ZReport: ("total_sales", "total_refunds", "total_net", "hash"),
    Product: ("sale_price", "status", "zone_id"),
    User: ("role", "is_active", "pin_hash", "password_hash"),
    Client: ("email", "phone", "first_name", "last_name"),
    LoyaltyAccount: ("membership_number", "points"),
}

# Entity-name labels for AuditLog.entity (kept stable across renames).
_ENTITY_LABELS: dict[type, str] = {
    Transaction: "transaction",
    CashDrawer: "cash_drawer",
    ZReport: "z_report",
    Product: "product",
    User: "user",
    Client: "client",
    LoyaltyAccount: "loyalty_account",
}

# Marker key on session.info: list of (instance_ref, action, captured_data)
# tuples queued during before_flush and materialised into AuditLog rows in
# after_flush (when default-generated ids like UUIDs have been populated).
_PENDING_KEY = "_vintiz_audit_pending"


def _entity_id(instance: Any) -> uuid.UUID | None:
    raw = getattr(instance, "id", None)
    if isinstance(raw, uuid.UUID):
        return raw
    if isinstance(raw, str):
        try:
            return uuid.UUID(raw)
        except ValueError:
            return None
    return None


_HASH_PREFIX = "sha256:"
_HASH_TRUNC = 12  # 48 bits — assez pour corréler 2 entrées audit, trop peu pour rainbow attack
_PHONE_DIGITS_RE = re.compile(r"\D+")


def _hash_pii(normalized: str) -> str:
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"{_HASH_PREFIX}{digest[:_HASH_TRUNC]}"


def _redact(field: str, value: Any) -> Any:
    """Hide secret values + JSON-safe coercion before storage in audit data.

    The audit row's ``data`` column is JSONB ; ``json.dumps`` chokes on
    Decimal, Enum, datetime and UUID natively. We coerce those to JSON-
    friendly primitives here so a misbehaved caller never crashes the
    flush (which would deny-list the whole transaction).

    Conformité RGPD (minimisation, art. 5-1-c) + NF525 (rétention 6 ans) :
    les champs PII directement identifiants (`email`, `phone`) sont
    hashés en SHA-256 tronqué 12 caractères avant persistance. Le hash
    reste **déterministe** (même e-mail → même hash) pour permettre la
    corrélation entre deux entrées d'audit, mais non-réversible.
    Les champs `first_name` / `last_name` restent en clair pour la
    traçabilité d'audit ; ils ne sont identifiants qu'en combinaison.
    """
    if field in {"pin_hash", "password_hash"}:
        return "<set>" if value else "<empty>"
    if value is None:
        return None
    if field == "email":
        normalized = str(value).strip().lower()
        return _hash_pii(normalized) if normalized else None
    if field == "phone":
        digits = _PHONE_DIGITS_RE.sub("", str(value))
        return _hash_pii(digits) if digits else None
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _diff_for_update(instance: Any, fields: Iterable[str]) -> dict[str, dict]:
    """Return {field: {before, after}} for sensitive fields whose value changed."""
    state = inspect(instance)
    diff: dict[str, dict] = {}
    for field in fields:
        if field not in state.attrs:
            continue
        history = state.attrs[field].history
        if not history.has_changes():
            continue
        before = history.deleted[0] if history.deleted else None
        after = history.added[0] if history.added else getattr(instance, field, None)
        diff[field] = {
            "before": _redact(field, before),
            "after": _redact(field, after),
        }
    return diff


def _snapshot_for_create(instance: Any, fields: Iterable[str]) -> dict[str, Any]:
    return {
        field: _redact(field, getattr(instance, field, None))
        for field in fields
        if hasattr(instance, field)
    }


def _collect_pending(session: Session) -> list[tuple[Any, str, dict | None]]:
    """Inspect the current flush and return (instance, action, data) tuples.

    Updates that touch no whitelisted field, and writes targeting the
    AuditLog table itself, are filtered out. The instance reference is kept
    so we can read its id in after_flush, once column defaults have run.
    """
    pending: list[tuple[Any, str, dict | None]] = []

    for instance in session.new:
        cls = type(instance)
        if cls not in _ENTITY_LABELS or cls is AuditLog:
            continue
        snapshot = _snapshot_for_create(instance, _SENSITIVE_FIELDS.get(cls, ()))
        pending.append((instance, "create", snapshot))

    for instance in session.dirty:
        cls = type(instance)
        if cls not in _ENTITY_LABELS or cls is AuditLog:
            continue
        if not session.is_modified(instance, include_collections=False):
            continue
        diff = _diff_for_update(instance, _SENSITIVE_FIELDS.get(cls, ()))
        if not diff:
            continue
        pending.append((instance, "update", diff))

    for instance in session.deleted:
        cls = type(instance)
        if cls not in _ENTITY_LABELS or cls is AuditLog:
            continue
        # Deletes need the id captured before the row vanishes — read it now.
        pending.append((instance, "delete", {"_captured_id": _entity_id(instance)}))

    return pending


def _before_flush(session: Session, _flush_context, _instances) -> None:
    """Stage pending audit entries on the session for materialisation later.

    Run-time invariants:
    - Multiple before_flush calls in the same flush should accumulate.
    - The AuditLog inserts emitted by after_flush trigger another before_flush
      cycle; the class filter inside _collect_pending makes that a no-op.
    """
    new_pending = _collect_pending(session)
    if not new_pending:
        return
    bucket: list = session.info.setdefault(_PENDING_KEY, [])
    bucket.extend(new_pending)


def _after_flush(session: Session, _flush_context) -> None:
    """Now that ids are populated, materialise queued AuditLog rows."""
    pending = session.info.pop(_PENDING_KEY, None)
    if not pending:
        return
    user_id = get_current_user_id()
    entries: list[AuditLog] = []
    for instance, action, data in pending:
        cls = type(instance)
        label = _ENTITY_LABELS.get(cls)
        if label is None:
            continue
        if action == "delete":
            entity_id = data.get("_captured_id") if isinstance(data, dict) else None
            payload = None
        else:
            entity_id = _entity_id(instance)
            payload = data
        entries.append(
            AuditLog(
                user_id=user_id,
                action=action,
                entity=label,
                entity_id=entity_id,
                data=payload,
            )
        )
    if entries:
        session.add_all(entries)


def register_audit_listeners() -> None:
    """Attach the SQLAlchemy event listeners used by the audit service.

    Idempotent: re-registration during testing or hot reload is a no-op.
    """
    if not event.contains(Session, "before_flush", _before_flush):
        event.listen(Session, "before_flush", _before_flush)
    if not event.contains(Session, "after_flush", _after_flush):
        event.listen(Session, "after_flush", _after_flush)


def unregister_audit_listeners() -> None:
    """Detach the SQLAlchemy event listeners.

    Useful in tests where one module's fixture registers them and a
    later module hits an SQLite schema that doesn't include
    ``audit_logs``. Idempotent — safe to call when the listeners
    aren't attached.
    """
    if event.contains(Session, "before_flush", _before_flush):
        event.remove(Session, "before_flush", _before_flush)
    if event.contains(Session, "after_flush", _after_flush):
        event.remove(Session, "after_flush", _after_flush)
