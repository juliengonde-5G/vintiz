"""Smoke tests for the styled A4 invoice PDF generator.

Pure rendering — no DB. Uses a duck-typed transaction so the test stays fast
and independent of the ORM.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _fake_tx() -> SimpleNamespace:
    item1 = SimpleNamespace(
        product=SimpleNamespace(name="Veste en jean Sandro"),
        quantity=1, unit_price=60.0, line_total=60.0, discount_percent=10,
    )
    item2 = SimpleNamespace(
        product=SimpleNamespace(name="Foulard en soie"),
        quantity=2, unit_price=15.0, line_total=30.0, discount_percent=0,
    )
    pay = SimpleNamespace(method="card", amount=90.0)
    return SimpleNamespace(
        items=[item1, item2], payments=[pay],
        total_ht=75.0, total_tva=15.0, total_ttc=90.0,
        created_at=datetime(2026, 5, 21), transaction_number=142, invoice_number=7,
        client_company_name="Atelier Mode SARL",
        client_billing_address="12 rue de la Paix\n27200 Vernon",
        client_siret="123 456 789 00012",
        hash_chain="abcdef0123456789abcdef",
    )


def test_invoice_pdf_is_valid_pdf():
    from app.services.invoice_pdf import generate_invoice_pdf

    pdf = generate_invoice_pdf(_fake_tx(), template=None)
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 2000


def test_invoice_pdf_handles_missing_hash_chain_and_buyer():
    from app.services.invoice_pdf import generate_invoice_pdf

    tx = _fake_tx()
    tx.hash_chain = None
    tx.client_company_name = None
    tx.client_billing_address = None
    tx.client_siret = None
    pdf = generate_invoice_pdf(tx, template=None)
    assert pdf[:4] == b"%PDF"
