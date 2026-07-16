"""Tests for the bulk CSV import service (P3-006)."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base
from app.models.product import Category, Product, ProductPhoto, ProductStatus
from app.models.user import User
from app.services.csv_import import ImportCsvService


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    tables = [
        User.__table__,
        Category.__table__,
        Product.__table__,
        ProductPhoto.__table__,
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


async def _make_category(session: AsyncSession, name: str) -> Category:
    cat = Category(name=name)
    session.add(cat)
    await session.flush()
    return cat


# ---------------------------------------------------------------------------
# Header validation
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_missing_required_columns_raises(session):
    csv_bytes = b"name\nRobe\n"
    with pytest.raises(ValueError) as exc:
        await ImportCsvService(session).import_csv(csv_bytes)
    assert "sale_price" in str(exc.value)


@pytest.mark.anyio
async def test_no_header_raises(session):
    with pytest.raises(ValueError):
        await ImportCsvService(session).import_csv(b"")


@pytest.mark.anyio
async def test_handles_excel_bom(session):
    """Excel saves CSVs with a UTF-8 BOM. Must not fool the parser."""
    await _make_category(session, "Robes")
    csv_bytes = "﻿name,sale_price,category_name\nRobe noire,49,Robes\n".encode("utf-8")
    summary = await ImportCsvService(session).import_csv(csv_bytes)
    assert summary.imported == 1
    assert summary.errors == []


# ---------------------------------------------------------------------------
# Per-row validation
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_imports_minimal_rows(session):
    await _make_category(session, "Robes")
    csv_bytes = (
        "name,sale_price,category_name\n"
        "Robe noire,49.00,Robes\n"
        "Robe rouge,55,Robes\n"
    ).encode("utf-8")

    summary = await ImportCsvService(session).import_csv(csv_bytes)
    assert summary.total_rows == 2
    assert summary.imported == 2
    assert summary.errors == []
    assert summary.skipped == 0

    rows = (await session.execute(select(Product))).scalars().all()
    assert len(rows) == 2
    assert all(p.status == ProductStatus.received for p in rows)


@pytest.mark.anyio
async def test_skips_existing_barcode(session):
    cat = await _make_category(session, "Robes")
    session.add(Product(
        barcode="EXISTING-1", name="Old", category_id=cat.id,
        sale_price=10.0, status=ProductStatus.display,
    ))
    await session.flush()

    csv_bytes = (
        "name,sale_price,category_name,barcode\n"
        "Robe doublon,49,Robes,EXISTING-1\n"
        "Robe nouvelle,30,Robes,FRESH-2\n"
    ).encode("utf-8")
    summary = await ImportCsvService(session).import_csv(csv_bytes)
    assert summary.imported == 1
    assert summary.skipped == 1
    assert summary.errors == []


@pytest.mark.anyio
async def test_dedupes_within_same_upload(session):
    """Two rows with the same barcode in the same CSV — second is skipped."""
    await _make_category(session, "Robes")
    csv_bytes = (
        "name,sale_price,category_name,barcode\n"
        "Robe A,49,Robes,DUP\n"
        "Robe B,55,Robes,DUP\n"
    ).encode("utf-8")
    summary = await ImportCsvService(session).import_csv(csv_bytes)
    assert summary.imported == 1
    assert summary.skipped == 1


@pytest.mark.anyio
async def test_resolves_category_by_name(session):
    await _make_category(session, "Robes")
    csv_bytes = (
        "name,sale_price,category_name\nRobe,49,Robes\n"
    ).encode("utf-8")
    summary = await ImportCsvService(session).import_csv(csv_bytes)
    assert summary.imported == 1


@pytest.mark.anyio
async def test_unknown_category_name_is_an_error(session):
    """Categories are never auto-created — typos report a clear error."""
    csv_bytes = (
        "name,sale_price,category_name\nRobe,49,Roebs\n"
    ).encode("utf-8")
    summary = await ImportCsvService(session).import_csv(csv_bytes)
    assert summary.imported == 0
    assert len(summary.errors) == 1
    assert "Roebs" in summary.errors[0].message


@pytest.mark.anyio
async def test_resolves_category_by_id_when_supplied(session):
    cat = await _make_category(session, "Robes")
    csv_bytes = (
        f"name,sale_price,category_id\nRobe,49,{cat.id}\n"
    ).encode("utf-8")
    summary = await ImportCsvService(session).import_csv(csv_bytes)
    assert summary.imported == 1


@pytest.mark.anyio
async def test_invalid_category_id_reports_error(session):
    csv_bytes = (
        f"name,sale_price,category_id\nRobe,49,{uuid.uuid4()}\n"
    ).encode("utf-8")
    summary = await ImportCsvService(session).import_csv(csv_bytes)
    assert summary.imported == 0
    assert len(summary.errors) == 1
    assert "does not exist" in summary.errors[0].message


@pytest.mark.anyio
async def test_blank_name_reports_error(session):
    await _make_category(session, "Robes")
    csv_bytes = (
        "name,sale_price,category_name\n,49,Robes\n"
    ).encode("utf-8")
    summary = await ImportCsvService(session).import_csv(csv_bytes)
    assert summary.imported == 0
    assert summary.errors[0].message == "name is required"


@pytest.mark.anyio
async def test_invalid_sale_price_reports_error(session):
    await _make_category(session, "Robes")
    csv_bytes = (
        "name,sale_price,category_name\nRobe,not-a-number,Robes\n"
    ).encode("utf-8")
    summary = await ImportCsvService(session).import_csv(csv_bytes)
    assert summary.imported == 0
    assert "sale_price" in summary.errors[0].message


@pytest.mark.anyio
async def test_french_comma_decimal_accepted(session):
    await _make_category(session, "Robes")
    csv_bytes = (
        "name,sale_price,category_name\nRobe,49,90,Robes\n"
    ).encode("utf-8")
    # The comma split would also break csv parsing — wrap in quotes.
    csv_bytes = (
        'name,sale_price,category_name\nRobe,"49,90",Robes\n'
    ).encode("utf-8")
    summary = await ImportCsvService(session).import_csv(csv_bytes)
    assert summary.imported == 1
    saved = (await session.execute(select(Product))).scalar_one()
    assert float(saved.sale_price) == 49.90


@pytest.mark.anyio
async def test_unknown_status_reports_error(session):
    await _make_category(session, "Robes")
    csv_bytes = (
        "name,sale_price,category_name,status\nRobe,49,Robes,bogus\n"
    ).encode("utf-8")
    summary = await ImportCsvService(session).import_csv(csv_bytes)
    assert summary.imported == 0
    assert "bogus" in summary.errors[0].message


# ---------------------------------------------------------------------------
# Dry run + line numbers
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_dry_run_does_not_persist(session):
    await _make_category(session, "Robes")
    csv_bytes = (
        "name,sale_price,category_name\nRobe,49,Robes\n"
    ).encode("utf-8")
    summary = await ImportCsvService(session).import_csv(csv_bytes, dry_run=True)
    assert summary.imported == 1
    rows = (await session.execute(select(Product))).scalars().all()
    assert rows == []


@pytest.mark.anyio
async def test_error_line_numbers_are_one_based_with_header(session):
    await _make_category(session, "Robes")
    csv_bytes = (
        "name,sale_price,category_name\n"
        "Robe valide,49,Robes\n"
        ",30,Robes\n"   # line 3
    ).encode("utf-8")
    summary = await ImportCsvService(session).import_csv(csv_bytes)
    assert summary.imported == 1
    assert len(summary.errors) == 1
    assert summary.errors[0].line == 3
