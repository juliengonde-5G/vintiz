"""End-to-end tests for the audit service (P1-013).

Uses a real in-memory SQLite session (sync, no asyncpg) to exercise the
SQLAlchemy event listener exactly as it runs in production. The tests
intentionally do not stub Session — the value is in proving the listener
fires for create / update / delete on whitelisted models and stays silent
on others.
"""

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.audit_context import set_current_user_id, reset_current_user_id
from app.models import Base
from app.models.audit import AuditLog
from app.models.product import Category, Product, ProductStatus
from app.models.user import User, UserRole
from app.services.audit import register_audit_listeners


@pytest.fixture(scope="module")
def engine():
    # SQLite in-memory: cheap. Only create the tables actually touched here —
    # other models (e.g. ai_tasks) use Postgres-only types like JSONB.
    eng = create_engine("sqlite:///:memory:")
    tables_needed = [
        User.__table__,
        Category.__table__,
        Product.__table__,
        AuditLog.__table__,
    ]
    Base.metadata.create_all(eng, tables=tables_needed)
    register_audit_listeners()
    return eng


@pytest.fixture
def session(engine):
    with Session(engine) as s:
        yield s
        s.rollback()


@pytest.fixture(autouse=True)
def _reset_context():
    """Make sure each test sees a clean ContextVar state."""
    handle = set_current_user_id(None)
    yield
    reset_current_user_id(handle)


def _audit_rows(session: Session, **filters) -> list[AuditLog]:
    query = session.query(AuditLog)
    for key, value in filters.items():
        query = query.filter(getattr(AuditLog, key) == value)
    return query.order_by(AuditLog.created_at.asc()).all()


def _make_user(session: Session, username: str = "sophie") -> User:
    """Insert a User without triggering an audit row (we silence the context)."""
    user = User(
        username=username,
        email=f"{username}@vintiz.fr",
        password_hash="x" * 60,
        role=UserRole.collaborateur,
        is_active=True,
    )
    session.add(user)
    session.flush()
    return user


# ---------------------------------------------------------------------------
# create / update / delete on a tracked model
# ---------------------------------------------------------------------------


def test_create_on_tracked_model_writes_audit_row(session):
    user = _make_user(session)
    set_current_user_id(user.id)
    session.query(AuditLog).delete()
    session.flush()

    category = Category(name="Robes")
    session.add(category)
    session.flush()

    product = Product(
        barcode="TEST-001",
        name="Robe noire",
        sale_price=49.0,
        category_id=category.id,
        status=ProductStatus.stock,
    )
    session.add(product)
    session.flush()

    rows = _audit_rows(session, entity="product", action="create")
    assert len(rows) == 1
    row = rows[0]
    assert row.entity_id == product.id
    assert row.user_id == user.id
    assert row.data is not None
    # snapshot fields for Product include sale_price + status
    assert row.data["sale_price"] == 49.0
    assert row.data["status"] in {"stock", "ProductStatus.stock"}


def test_update_on_tracked_model_records_diff(session):
    user = _make_user(session, "lea")
    set_current_user_id(user.id)
    category = Category(name="Pantalons")
    session.add(category)
    session.flush()
    product = Product(
        barcode="UPD-001",
        name="Jean",
        sale_price=30.0,
        category_id=category.id,
        status=ProductStatus.stock,
    )
    session.add(product)
    session.flush()

    session.query(AuditLog).delete()
    session.flush()

    product.sale_price = 25.0
    session.flush()

    rows = _audit_rows(session, entity="product", action="update")
    assert len(rows) == 1
    diff = rows[0].data
    assert "sale_price" in diff
    assert diff["sale_price"]["before"] == 30.0
    assert diff["sale_price"]["after"] == 25.0


def test_update_with_no_sensitive_field_change_does_not_log(session):
    user = _make_user(session, "noisy")
    set_current_user_id(user.id)
    category = Category(name="Sacs")
    session.add(category)
    session.flush()
    product = Product(
        barcode="NOOP-001",
        name="Sac",
        sale_price=15.0,
        category_id=category.id,
        status=ProductStatus.stock,
    )
    session.add(product)
    session.flush()

    session.query(AuditLog).delete()
    session.flush()

    # `name` is not in the Product whitelist → no audit row
    product.name = "Sac noir"
    session.flush()

    rows = _audit_rows(session, entity="product", action="update")
    assert rows == []


def test_delete_on_tracked_model_writes_audit_row(session):
    user = _make_user(session, "del")
    set_current_user_id(user.id)
    category = Category(name="Sacs")
    session.add(category)
    session.flush()
    product = Product(
        barcode="DEL-001",
        name="Vieille robe",
        sale_price=20.0,
        category_id=category.id,
        status=ProductStatus.stock,
    )
    session.add(product)
    session.flush()

    session.query(AuditLog).delete()
    session.flush()

    session.delete(product)
    session.flush()

    rows = _audit_rows(session, entity="product", action="delete")
    assert len(rows) == 1
    assert rows[0].entity_id == product.id
    assert rows[0].data is None


# ---------------------------------------------------------------------------
# Anonymous (no auth) writes still land in the table
# ---------------------------------------------------------------------------


def test_anonymous_create_logs_with_null_user_id(session):
    # No set_current_user_id → context is None
    category = Category(name="Veste")
    session.add(category)
    session.flush()
    product = Product(
        barcode="ANON-001",
        name="Anon item",
        sale_price=10.0,
        category_id=category.id,
        status=ProductStatus.stock,
    )
    session.add(product)
    session.flush()

    rows = _audit_rows(session, entity="product", action="create", entity_id=product.id)
    assert len(rows) == 1
    assert rows[0].user_id is None


# ---------------------------------------------------------------------------
# Sensitive fields are redacted (User.pin_hash / password_hash)
# ---------------------------------------------------------------------------


def test_user_pin_hash_change_is_redacted(session):
    actor = _make_user(session, "actor")
    set_current_user_id(actor.id)

    target = _make_user(session, "target")
    session.flush()

    session.query(AuditLog).delete()
    session.flush()

    target.pin_hash = "$2b$12$RealBcryptHashGoesHere..."
    session.flush()

    rows = _audit_rows(session, entity="user", action="update", entity_id=target.id)
    assert len(rows) == 1
    diff = rows[0].data
    assert "pin_hash" in diff
    # never store the actual hash — only flag presence
    assert diff["pin_hash"]["after"] in {"<set>", "<empty>"}
    assert "$2b$" not in str(diff)


# ---------------------------------------------------------------------------
# AuditLog itself is never audited (no infinite recursion)
# ---------------------------------------------------------------------------


def test_audit_log_inserts_do_not_re_trigger_listener(session):
    set_current_user_id(uuid.uuid4())
    session.query(AuditLog).delete()
    session.flush()

    # Manually insert an AuditLog → must NOT produce a meta-AuditLog.
    session.add(
        AuditLog(
            user_id=None,
            action="manual",
            entity="something",
            entity_id=None,
            data={"manual": True},
        )
    )
    session.flush()

    rows = session.query(AuditLog).all()
    assert len(rows) == 1
    assert rows[0].action == "manual"
