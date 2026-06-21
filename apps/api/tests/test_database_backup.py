"""Tests for the database backup service (gestionnaire de base de données).

The real dump (pg_dump / sqlite iterdump) is infra, so ``dump_database`` is
monkeypatched — we unit-test the orchestration: ledger row lifecycle, size,
retention pruning, failure → alert email, config singleton, CSV export, state.
"""

import csv
import gzip
import io
import types
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models import Base
from app.models.client import Client, LoyaltyAccount
from app.models.database_backup import DatabaseBackup, DatabaseBackupConfig
from app.models.newsletter import NewsletterSubscriber
from app.models.pos import Transaction, TransactionItem, TransactionType
from app.models.product import Category, Gender, Product, ProductStatus
from app.models.user import User
from app.services import database_backup as svc


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    tables = [
        DatabaseBackup.__table__,
        DatabaseBackupConfig.__table__,
        Product.__table__,
        Category.__table__,
        Client.__table__,
        LoyaltyAccount.__table__,
        Transaction.__table__,
        TransactionItem.__table__,
        User.__table__,
        NewsletterSubscriber.__table__,
    ]
    async with eng.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=tables))
    yield eng
    await eng.dispose()


@pytest.fixture
async def session(engine):
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        yield s


@pytest.fixture
def backup_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "BACKUP_DIR", str(tmp_path))
    return tmp_path


# ---------------------------------------------------------------------------
# Config singleton
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_config_get_or_create_and_upsert(session):
    cfg = await svc.get_config(session)
    assert cfg.retention_days == 30
    assert cfg.enabled is True

    # Idempotent: a second call returns the same singleton row.
    cfg2 = await svc.get_config(session)
    assert cfg2.id == cfg.id

    updated = await svc.upsert_config(session, {"retention_days": 7, "alert_email": "a@b.fr", "enabled": False})
    assert updated.retention_days == 7
    assert updated.alert_email == "a@b.fr"
    assert updated.enabled is False
    # Retention is clamped to >= 1.
    clamped = await svc.upsert_config(session, {"retention_days": 0})
    assert clamped.retention_days == 1
    assert (await session.execute(select(func.count()).select_from(DatabaseBackupConfig))).scalar_one() == 1


# ---------------------------------------------------------------------------
# run_backup
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_run_backup_success_records_downloadable_row(session, backup_dir, monkeypatch):
    def _fake_dump(dest):
        with gzip.open(dest, "wt") as f:
            f.write("-- dummy dump\nSELECT 1;\n")

    monkeypatch.setattr(svc, "dump_database", _fake_dump)

    backup = await svc.run_backup(session, trigger="manual")
    assert backup.status == "success"
    assert backup.trigger == "manual"
    assert backup.size_bytes and backup.size_bytes > 0
    assert backup.finished_at is not None
    assert (backup_dir / backup.filename).exists()

    out = svc.serialize_backup(backup)
    assert out["downloadable"] is True


@pytest.mark.anyio
async def test_build_full_archive_bundles_db_and_config_no_photos(tmp_path, backup_dir, monkeypatch):
    """A full archive is a .tar.gz with the DB dump + JSON config — NO photos.

    Photos are excluded on purpose: their links live in the database dump, so
    the archive keeps only the reference, not the image bytes."""
    import tarfile

    # Fake DB dump.
    def _fake_dump(dest):
        with gzip.open(dest, "wt") as f:
            f.write("-- dump\nSELECT 1;\n")

    monkeypatch.setattr(svc, "dump_database", _fake_dump)

    # Fake on-disk config.
    cfg_file = tmp_path / "app_config.json"
    cfg_file.write_text('{"shop_info": {"name": "Vintiz"}}', encoding="utf-8")
    monkeypatch.setattr(svc, "_config_entries", lambda: [(cfg_file, "config/app_config.json")])

    dest = backup_dir / "vintiz_full_test.tar.gz"
    manifest = svc.build_full_archive(dest)

    assert dest.exists()
    assert manifest["format"] == "tar.gz"
    assert manifest["photos"]["included"] is False
    assert manifest["config"]["files"] == ["config/app_config.json"]
    assert manifest["database"]["bytes"] > 0

    with tarfile.open(dest, "r:gz") as tar:
        names = set(tar.getnames())
    assert "database.sql.gz" in names
    assert "config/app_config.json" in names
    assert "manifest.json" in names
    # No photo files / uploads tree in the archive.
    assert not any(n.startswith("uploads/") for n in names)

    # The temp DB dump must not be left behind next to the archive.
    assert not list(backup_dir.glob(".dbdump_*"))


@pytest.mark.anyio
async def test_run_backup_full_produces_tar_archive(session, backup_dir, tmp_path, monkeypatch):
    """Default config (include_files=True) → a 'full' .tar.gz with a manifest."""
    def _fake_dump(dest):
        with gzip.open(dest, "wt") as f:
            f.write("dump")

    monkeypatch.setattr(svc, "dump_database", _fake_dump)
    monkeypatch.setattr(svc, "_config_entries", lambda: [])

    backup = await svc.run_backup(session, trigger="auto")
    assert backup.status == "success"
    assert backup.kind == "full"
    assert backup.filename.endswith(".tar.gz")
    assert backup.manifest and backup.manifest["format"] == "tar.gz"
    assert backup.manifest["photos"]["included"] is False
    assert (backup_dir / backup.filename).exists()

    out = svc.serialize_backup(backup)
    assert out["kind"] == "full"
    assert out["downloadable"] is True


@pytest.mark.anyio
async def test_run_backup_db_only_when_include_files_disabled(session, backup_dir, monkeypatch):
    """include_files=False keeps the legacy DB-only .sql.gz behaviour."""
    await svc.upsert_config(session, {"include_files": False})

    def _fake_dump(dest):
        with gzip.open(dest, "wt") as f:
            f.write("dump")

    monkeypatch.setattr(svc, "dump_database", _fake_dump)

    backup = await svc.run_backup(session, trigger="manual")
    assert backup.status == "success"
    assert backup.kind == "db"
    assert backup.filename.endswith(".sql.gz")
    assert backup.manifest is None


@pytest.mark.anyio
async def test_run_backup_failure_records_failed_and_alerts(session, backup_dir, monkeypatch):
    await svc.upsert_config(session, {"alert_email": "ops@vintiz.fr"})

    def _boom(dest):
        raise RuntimeError("pg_dump introuvable")

    sent: list = []

    def _fake_send_email(msg):
        sent.append(msg)
        return types.SimpleNamespace(status="sent", backend="test", message_id="x", sent_at="")

    monkeypatch.setattr(svc, "dump_database", _boom)
    monkeypatch.setattr("app.services.email_gateway.send_email", _fake_send_email)

    backup = await svc.run_backup(session, trigger="auto")
    assert backup.status == "failed"
    assert "pg_dump" in (backup.error or "")
    assert not (backup_dir / backup.filename).exists()  # partial file cleaned up
    # An alert email was sent to the configured recipient.
    assert len(sent) == 1
    assert sent[0].to == "ops@vintiz.fr"


@pytest.mark.anyio
async def test_run_backup_failure_without_recipient_does_not_crash(session, backup_dir, monkeypatch):
    # No alert_email + no env fallback → must not raise, just records failed.
    monkeypatch.setattr(settings, "BACKUP_ALERT_EMAIL", "")
    monkeypatch.setattr(settings, "SMTP_FROM", "")

    def _boom(dest):
        raise RuntimeError("disk full")

    monkeypatch.setattr(svc, "dump_database", _boom)
    backup = await svc.run_backup(session, trigger="auto")
    assert backup.status == "failed"


# ---------------------------------------------------------------------------
# Retention
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_apply_retention_prunes_old_backups(session, backup_dir):
    old_file = backup_dir / "vintiz_old.sql.gz"
    old_file.write_bytes(b"old")
    recent_file = backup_dir / "vintiz_recent.sql.gz"
    recent_file.write_bytes(b"new")

    old = DatabaseBackup(
        filename="vintiz_old.sql.gz", path=str(old_file), status="success",
        trigger="auto", created_at=datetime.now(timezone.utc) - timedelta(days=40),
    )
    recent = DatabaseBackup(
        filename="vintiz_recent.sql.gz", path=str(recent_file), status="success",
        trigger="auto", created_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    session.add_all([old, recent])
    await session.flush()

    pruned = await svc.apply_retention(session, retention_days=30)
    assert pruned == 1
    assert not old_file.exists()
    assert recent_file.exists()
    remaining = (await session.execute(select(func.count()).select_from(DatabaseBackup))).scalar_one()
    assert remaining == 1


# ---------------------------------------------------------------------------
# Export + state
# ---------------------------------------------------------------------------


async def _make_product(session) -> Product:
    cat = Category(name="Robes", gender=Gender.femme)
    session.add(cat)
    await session.flush()
    p = Product(
        barcode=f"B-{uuid.uuid4().hex[:8]}", name="Robe noire", category_id=cat.id,
        status=ProductStatus.stock, sale_price=20, purchase_price=5,
    )
    session.add(p)
    await session.flush()
    return p


@pytest.mark.anyio
async def test_export_table_csv_products(session):
    await _make_product(session)
    filename, content = await svc.export_table_csv(session, "products")
    assert filename.startswith("vintiz_products_")
    lines = content.strip().splitlines()
    assert "barcode" in lines[0] and "sale_price" in lines[0]
    assert any("Robe noire" in line for line in lines[1:])


@pytest.mark.anyio
async def test_export_table_csv_rejects_unlisted_table(session):
    with pytest.raises(ValueError):
        await svc.export_table_csv(session, "users")  # not in the whitelist


@pytest.mark.anyio
async def test_export_table_csv_clients_enriched(session):
    """The clients export is an enriched commercial view: loyalty + transaction
    aggregates + purchased categories/brands, with test/erased clients filtered."""
    cat = Category(name="Robes", gender=Gender.femme)
    session.add(cat)
    await session.flush()
    product = Product(
        barcode=f"B-{uuid.uuid4().hex[:8]}", name="Robe noire", category_id=cat.id,
        status=ProductStatus.stock, sale_price=40, purchase_price=10, brand="Sézane",
    )
    user = User(username="caissier", email="caissier@vintiz.fr", password_hash="x")
    session.add_all([product, user])
    await session.flush()

    # Buyer: loyalty account + one sale of the product above.
    buyer = Client(first_name="Marie", last_name="Durand", email="marie@example.fr")
    session.add(buyer)
    await session.flush()
    session.add(LoyaltyAccount(client_id=buyer.id, points=120, membership_number="V000123"))
    tx = Transaction(
        transaction_number=1, transaction_type=TransactionType.sale,
        user_id=user.id, client_id=buyer.id, total_ttc=40, hash_chain="h1",
    )
    session.add(tx)
    await session.flush()
    session.add(TransactionItem(
        transaction_id=tx.id, product_id=product.id, quantity=1,
        unit_price=40, line_total=40,
    ))

    # Client with no transactions + two clients that must be excluded.
    quiet = Client(first_name="Paul", last_name="Sans", email="paul@example.fr")
    seed = Client(first_name="Seed", last_name="Bot", email="seed@example.fr", is_test=True)
    erased = Client(
        first_name="Parti", last_name="Effacé", email="erased@example.fr",
        deletion_requested_at=datetime.now(timezone.utc),
    )
    session.add_all([quiet, seed, erased])
    await session.flush()

    filename, content = await svc.export_table_csv(session, "clients")
    assert filename.startswith("vintiz_clients_")

    rows = list(csv.DictReader(io.StringIO(content), delimiter=";"))
    header = rows[0].keys() if rows else []
    for col in (
        "nb_transactions", "ca_total_ttc", "panier_moyen_ttc", "premiere_visite",
        "derniere_visite", "categories_achetees", "marques_achetees",
        "membership_number", "loyalty_points",
    ):
        assert col in header

    by_email = {r["email"]: r for r in rows}
    # Test client + RGPD-erased client are filtered out.
    assert "seed@example.fr" not in by_email
    assert "erased@example.fr" not in by_email

    # Buyer aggregates are populated.
    m = by_email["marie@example.fr"]
    assert m["nb_transactions"] == "1"
    assert m["membership_number"] == "V000123"
    assert m["loyalty_points"] == "120"
    assert float(m["ca_total_ttc"]) == 40.0
    assert float(m["panier_moyen_ttc"]) == 40.0
    assert "Robes" in m["categories_achetees"]
    assert "Sézane" in m["marques_achetees"]
    assert m["premiere_visite"] and m["derniere_visite"]

    # Client without transactions: zero count, empty aggregate strings.
    q = by_email["paul@example.fr"]
    assert q["nb_transactions"] == "0"
    assert float(q["ca_total_ttc"]) == 0.0
    assert q["categories_achetees"] == ""
    assert q["marques_achetees"] == ""


@pytest.mark.anyio
async def test_database_state_reports_counts_and_backup(session, backup_dir, monkeypatch):
    await _make_product(session)

    def _fake_dump(dest):
        with gzip.open(dest, "wt") as f:
            f.write("dump")

    monkeypatch.setattr(svc, "dump_database", _fake_dump)
    await svc.run_backup(session, trigger="manual")

    state = await svc.database_state(session)
    assert state["table_counts"]["products"] == 1
    assert state["backup_count"] == 1
    assert state["last_backup"]["status"] == "success"
    assert state["last_success_at"] is not None
    assert "products" in state["exportable_tables"]
