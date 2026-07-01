"""Test de l'export CSV mensuel (remplace le FEC mensuel, importable Pennylane).

Vérifie le format (séparateur ;, décimales virgule, dates JJ/MM/AAAA), le
regroupement des lignes d'un même Z sous un numéro d'écriture unique, et
l'équilibre débit/crédit par écriture.
"""

import uuid
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base
from app.models.accounting import AccountingExport, AccountingExportLine
from app.services.accounting_service import _PENNYLANE_CSV_COLUMNS, AccountingService


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


async def _export_with_lines(session, export_date, z_num, lines):
    exp = AccountingExport(z_report_id=uuid.uuid4(), export_date=export_date)
    session.add(exp)
    await session.flush()
    for i, (account, label, debit, credit, text) in enumerate(lines, start=1):
        session.add(AccountingExportLine(
            export_id=exp.id, line_number=i,
            account_number=account, account_label=label,
            debit=debit, credit=credit, label=text,
            piece_reference=f"Z{z_num:04d}", piece_date=export_date,
        ))
    await session.flush()
    return exp


@pytest.mark.anyio
async def test_monthly_csv_empty_month(session):
    svc = AccountingService(session)
    csv = await svc.generate_monthly_csv(2026, 7)
    header = csv.splitlines()[0]
    assert header == ";".join(_PENNYLANE_CSV_COLUMNS)
    assert len(csv.strip().splitlines()) == 1  # header only


@pytest.mark.anyio
async def test_monthly_csv_groups_and_balances(session):
    # Deux clôtures Z le même mois, chacune équilibrée.
    await _export_with_lines(session, date(2026, 7, 5), 1, [
        ("531000", "Caisse", 120.0, 0.0, "Caisse — Z0001"),
        ("707100", "Ventes", 0.0, 100.0, "Ventes — Z0001"),
        ("44571", "TVA collectée", 0.0, 20.0, "TVA — Z0001"),
    ])
    await _export_with_lines(session, date(2026, 7, 10), 2, [
        ("512000", "CB SumUp", 60.0, 0.0, "CB — Z0002"),
        ("707100", "Ventes", 0.0, 50.0, "Ventes — Z0002"),
        ("44571", "TVA collectée", 0.0, 10.0, "TVA — Z0002"),
    ])

    svc = AccountingService(session)
    csv = await svc.generate_monthly_csv(2026, 7)
    rows = [r for r in csv.splitlines() if r]
    assert rows[0] == ";".join(_PENNYLANE_CSV_COLUMNS)
    body = rows[1:]
    assert len(body) == 6  # 3 + 3 lignes

    parsed = [r.split(";") for r in body]
    col = {name: i for i, name in enumerate(_PENNYLANE_CSV_COLUMNS)}

    # Format : journal, décimales virgule, date JJ/MM/AAAA.
    assert parsed[0][col["Journal"]] == "VTE"
    assert parsed[0][col["Date"]] == "05/07/2026"
    assert parsed[0][col["Debit"]] == "120,00"
    assert parsed[0][col["Devise"]] == "EUR"

    # Chaque Z partage un unique NumeroEcriture ; les deux Z ont des numéros
    # distincts.
    ecr = [r[col["NumeroEcriture"]] for r in parsed]
    assert ecr[0] == ecr[1] == ecr[2]
    assert ecr[3] == ecr[4] == ecr[5]
    assert ecr[0] != ecr[3]
    assert ecr[0] == "202607-0001"
    assert ecr[3] == "202607-0002"

    # Équilibre débit = crédit par écriture.
    def _amt(s: str) -> float:
        return float(s.replace(",", "."))

    for group in (parsed[:3], parsed[3:]):
        deb = sum(_amt(r[col["Debit"]]) for r in group)
        cre = sum(_amt(r[col["Credit"]]) for r in group)
        assert round(deb - cre, 2) == 0.0
