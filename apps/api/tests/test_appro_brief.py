"""Tests for the approvisionnement brief (Personal Shopper 360 — V5, §7.3)."""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.models import Base
from app.models.client import Client
from app.models.pos import Transaction, TransactionItem, TransactionType
from app.models.product import Category, Gender, Product, ProductStatus
from app.models.user import User, UserRole
from app.services.appro_brief import build_appro_brief


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
        Client.__table__,
        Transaction.__table__,
        TransactionItem.__table__,
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


async def _cat(session: AsyncSession, name: str) -> Category:
    c = Category(name=name)
    session.add(c)
    await session.flush()
    return c


async def _product(session, cat, *, gender=Gender.femme, status=ProductStatus.display):
    p = Product(
        barcode=f"P-{uuid.uuid4().hex[:8]}",
        name=f"{cat.name} piece",
        category_id=cat.id,
        sale_price=50.0,
        status=status,
        gender=gender,
    )
    session.add(p)
    await session.flush()
    return p


# --------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_cold_start_brief_surfaces_thin_cells(session):
    # Members skew female; no transactions yet.
    for _ in range(3):
        session.add(Client(first_name="J", last_name="M", gender_profile="femme",
                            email=f"{uuid.uuid4().hex[:6]}@x.fr"))
    session.add(Client(first_name="H", last_name="M", gender_profile="homme",
                       email=f"{uuid.uuid4().hex[:6]}@x.fr"))
    robes = await _cat(session, "Robes")
    sacs = await _cat(session, "Sacs")
    # Robes well stocked, Sacs nearly empty → Sacs should be flagged first.
    for _ in range(6):
        await _product(session, robes)
    await _product(session, sacs)
    await session.flush()

    brief = await build_appro_brief(session)
    assert brief["cold_start"] is True
    assert brief["dominant_gender"] == "femme"
    assert brief["n_members_profiled"] == 4
    assert brief["lines"]
    # The thinnest cell (Sacs) is recommended before the well-stocked Robes.
    cats_in_order = [line["category"] for line in brief["lines"]]
    assert cats_in_order.index("sacs") < cats_in_order.index("robes")
    assert all(line["action"] == "demander" for line in brief["lines"])


@pytest.mark.anyio
async def test_demand_driven_brief_flags_undersupplied_category(session):
    user = User(username="s", email="s@x.fr", password_hash="x" * 60,
                role=UserRole.collaborateur, is_active=True)
    champion = Client(first_name="Julie", last_name="M", rfm_segment="champion",
                      gender_profile="femme", email="julie@x.fr")
    session.add_all([user, champion])
    await session.flush()

    robes = await _cat(session, "Robes")
    # Demand on Robes but only 1 in stock → expect a "demander" line.
    bought = await _product(session, robes, status=ProductStatus.sold)
    await _product(session, robes)  # single remaining piece

    tx = Transaction(
        transaction_number=int(uuid.uuid4().int % 1_000_000_000),
        transaction_type=TransactionType.sale, user_id=user.id,
        client_id=champion.id, total_ht=0, total_tva=0, total_ttc=50.0,
        hash_chain="x", created_at=datetime.now(timezone.utc),
    )
    session.add(tx)
    await session.flush()
    session.add(TransactionItem(
        transaction_id=tx.id, product_id=bought.id, quantity=1,
        unit_price=50.0, discount_percent=0, line_total=50.0,
    ))
    await session.flush()

    brief = await build_appro_brief(session)
    assert brief["cold_start"] is False
    robes_lines = [line for line in brief["lines"] if line["category"] == "robes"]
    assert robes_lines
    assert robes_lines[0]["action"] == "demander"
    assert robes_lines[0]["quality_hint"] == "premium"
