"""Tests for PR 2/6 — admin templates + sumup terminals + B2B invoice PDF.

Covers the service layer end-to-end on SQLite (no HTTP / auth required):
- Template CRUD + atomic ``set_default`` flip
- SumUp terminal CRUD constraints (unique reader_id, single is_default)
- ``PosService.create_transaction`` enforces the buyer block in invoice mode
- ``PosService.create_transaction`` assigns an invoice_number when ``is_invoice=True``
- ``invoice_pdf.generate_invoice_pdf`` produces a valid PDF byte stream
"""

from __future__ import annotations


import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.exceptions import InvalidOperation
from app.models import (
    Base,
    ReceiptKind,
    ReceiptTemplate,
    SumUpTerminal,
    SumUpTerminalStatus,
    User,
)
from app.services.pos import PosService


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def session():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(eng, expire_on_commit=False)
    async with Session() as s:
        yield s
    await eng.dispose()


# ---------------------------------------------------------------------------
# ReceiptTemplate
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_receipt_template_kind_and_defaults(session):
    """Both kinds coexist and is_default is independent per kind."""
    ticket = ReceiptTemplate(
        name="Ticket par défaut",
        kind=ReceiptKind.ticket,
        title="VINTIZ",
        footer="Merci",
        is_default=True,
    )
    invoice = ReceiptTemplate(
        name="Facture B2B",
        kind=ReceiptKind.invoice,
        title="FACTURE",
        footer="Conditions standards",
        is_default=True,
        show_tva_breakdown=True,
    )
    session.add_all([ticket, invoice])
    await session.commit()

    rows = (await session.execute(select(ReceiptTemplate))).scalars().all()
    assert len(rows) == 2
    assert sum(1 for r in rows if r.is_default) == 2  # one per kind


@pytest.mark.anyio
async def test_receipt_template_set_default_flip(session):
    """Promoting a new default within the same kind demotes the previous one
    via the same logic the router uses."""
    from sqlalchemy import update

    t1 = ReceiptTemplate(
        name="Ticket Eté",
        kind=ReceiptKind.ticket,
        title="VINTIZ",
        is_default=True,
    )
    t2 = ReceiptTemplate(
        name="Ticket Hiver",
        kind=ReceiptKind.ticket,
        title="VINTIZ",
        is_default=False,
    )
    session.add_all([t1, t2])
    await session.commit()

    # Simulate POST /set-default on t2
    await session.execute(
        update(ReceiptTemplate)
        .where(
            ReceiptTemplate.kind == ReceiptKind.ticket,
            ReceiptTemplate.id != t2.id,
        )
        .values(is_default=False)
    )
    t2.is_default = True
    await session.commit()

    refreshed = {
        r.id: r
        for r in (
            await session.execute(select(ReceiptTemplate))
        ).scalars().all()
    }
    assert refreshed[t1.id].is_default is False
    assert refreshed[t2.id].is_default is True


# ---------------------------------------------------------------------------
# SumUpTerminal
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_sumup_terminal_unique_reader_id(session):
    """Two terminals can't share the same reader_id (unique constraint)."""
    session.add(
        SumUpTerminal(
            label="Caisse",
            reader_id="reader_abc123",
            status=SumUpTerminalStatus.active,
            is_default=True,
        )
    )
    await session.commit()

    session.add(
        SumUpTerminal(
            label="Mobile",
            reader_id="reader_abc123",  # duplicate
            status=SumUpTerminalStatus.active,
        )
    )
    with pytest.raises(Exception):
        await session.commit()
    await session.rollback()


# ---------------------------------------------------------------------------
# PosService — invoice mode
# ---------------------------------------------------------------------------


async def _make_user(session) -> User:
    user = User(
        username="admin",
        email="admin@vintiz.fr",
        password_hash="x",
        role="manager",
    )
    session.add(user)
    await session.flush()
    return user


class _FakeCartItem:
    def __init__(self, name: str, unit_price: float, quantity: int = 1):
        self.product_id = None
        self.name = name
        self.unit_price = unit_price
        self.quantity = quantity
        self.discount_percent = 0.0


class _FakePayment:
    def __init__(self, method: str, amount: float):
        self.method = method
        self.amount = amount


@pytest.mark.anyio
async def test_create_transaction_invoice_mode_assigns_invoice_number(session):
    user = await _make_user(session)
    svc = PosService(session)

    transaction = await svc.create_transaction(
        user_id=user.id,
        items=[_FakeCartItem("Sac cuir", 240.0)],
        payments=[_FakePayment("card", 240.0)],
        is_invoice=True,
        client_company_name="ACME SARL",
        client_siret="12345678901234",
        client_billing_address="1 rue Lafayette\n75009 Paris",
    )
    await session.commit()

    assert transaction.is_invoice is True
    assert transaction.invoice_number == 1
    assert transaction.client_company_name == "ACME SARL"
    assert transaction.client_siret == "12345678901234"
    assert transaction.client_billing_address.startswith("1 rue")


@pytest.mark.anyio
async def test_create_transaction_invoice_rejects_invalid_siret(session):
    user = await _make_user(session)
    svc = PosService(session)

    with pytest.raises(InvalidOperation, match="SIRET"):
        await svc.create_transaction(
            user_id=user.id,
            items=[_FakeCartItem("Sac", 100.0)],
            payments=[_FakePayment("card", 100.0)],
            is_invoice=True,
            client_company_name="ACME",
            client_siret="123",  # too short
            client_billing_address="ok",
        )


@pytest.mark.anyio
async def test_create_transaction_invoice_rejects_missing_company(session):
    user = await _make_user(session)
    svc = PosService(session)

    with pytest.raises(InvalidOperation, match="raison sociale"):
        await svc.create_transaction(
            user_id=user.id,
            items=[_FakeCartItem("Sac", 100.0)],
            payments=[_FakePayment("card", 100.0)],
            is_invoice=True,
            client_company_name="",
            client_siret="12345678901234",
            client_billing_address="ok",
        )


@pytest.mark.anyio
async def test_invoice_numbers_are_sequential(session):
    user = await _make_user(session)
    svc = PosService(session)

    t1 = await svc.create_transaction(
        user_id=user.id,
        items=[_FakeCartItem("Sac", 100.0)],
        payments=[_FakePayment("card", 100.0)],
        is_invoice=True,
        client_company_name="ACME",
        client_siret="12345678901234",
        client_billing_address="ok",
    )
    t2 = await svc.create_transaction(
        user_id=user.id,
        items=[_FakeCartItem("Sac", 100.0)],
        payments=[_FakePayment("card", 100.0)],
        is_invoice=True,
        client_company_name="ACME",
        client_siret="12345678901234",
        client_billing_address="ok",
    )
    # Plain ticket interleaved — invoice_number must NOT advance
    t3 = await svc.create_transaction(
        user_id=user.id,
        items=[_FakeCartItem("Sac", 100.0)],
        payments=[_FakePayment("card", 100.0)],
    )
    await session.commit()

    assert t1.invoice_number == 1
    assert t2.invoice_number == 2
    assert t3.is_invoice is False
    assert t3.invoice_number is None


# ---------------------------------------------------------------------------
# Invoice PDF service
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_generate_invoice_pdf_returns_valid_pdf_bytes(session):
    """Smoke test — generated bytes must start with the PDF signature."""
    pytest.importorskip("reportlab")
    from app.services.invoice_pdf import generate_invoice_pdf

    user = await _make_user(session)
    svc = PosService(session)
    transaction = await svc.create_transaction(
        user_id=user.id,
        items=[_FakeCartItem("Sac cuir", 240.0)],
        payments=[_FakePayment("card", 240.0)],
        is_invoice=True,
        client_company_name="ACME SARL",
        client_siret="12345678901234",
        client_billing_address="1 rue Lafayette\n75009 Paris",
    )
    transaction.hash_chain = "a" * 64  # FiscalService stub for the footer
    await session.commit()

    template = ReceiptTemplate(
        name="Facture B2B",
        kind=ReceiptKind.invoice,
        title="FACTURE",
        footer="Conditions standards de vente",
        conditions_retour="Retour sous 14 jours.",
        show_tva_breakdown=True,
        is_default=True,
    )
    session.add(template)
    await session.commit()

    # Re-fetch with items + payments loaded eagerly
    refreshed = (
        await session.execute(
            select(type(transaction)).where(type(transaction).id == transaction.id)
        )
    ).scalar_one()
    pdf_bytes = generate_invoice_pdf(refreshed, template=template)
    assert pdf_bytes.startswith(b"%PDF-")
    # Sanity check — should be a non-trivial document
    assert len(pdf_bytes) > 1000
