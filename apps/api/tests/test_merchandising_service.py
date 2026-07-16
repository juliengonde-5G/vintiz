"""Tests for the merchandising service (P2-005 / P2-006 / P2-007 / P2-008)."""

import json
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base
from app.models.merchandising import WindowDisplayProposal
from app.models.product import Category, Gender, Product, ProductPhoto, ProductStatus
from app.models.store import FurnitureItem, StoreZone, ZoneProduct, ZoneTag
from app.models.user import User
from app.services.merchandising import (
    MerchandisingService,
    classify_size,
    score_bucket,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    tables = [
        User.__table__,
        Category.__table__,
        StoreZone.__table__,
        ZoneTag.__table__,
        FurnitureItem.__table__,
        ZoneProduct.__table__,
        Product.__table__,
        ProductPhoto.__table__,
        WindowDisplayProposal.__table__,
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_zone(
    session: AsyncSession,
    *,
    name: str,
    capacity: int = 30,
    product_types: str | None = None,
    display_order: int = 0,
    match_genders: list | None = None,
    match_colors: list | None = None,
    match_size_classes: list | None = None,
    min_trend_score: float | None = None,
    assignment_priority: int = 100,
    auto_assign: bool = True,
) -> StoreZone:
    z = StoreZone(
        name=name,
        capacity=capacity,
        product_types=product_types,
        display_order=display_order,
        pos_x=10, pos_y=10, width=20, height=20,
        shape="rounded",
        match_genders=match_genders,
        match_colors=match_colors,
        match_size_classes=match_size_classes,
        min_trend_score=min_trend_score,
        assignment_priority=assignment_priority,
        auto_assign=auto_assign,
    )
    session.add(z)
    await session.flush()
    return z


async def _make_category(
    session: AsyncSession, name: str, gender: Gender = Gender.mixte
) -> Category:
    c = Category(name=name, gender=gender)
    session.add(c)
    await session.flush()
    return c


async def _make_product(
    session: AsyncSession,
    *,
    name: str,
    category: Category,
    zone_id=None,
    sale_price: float = 49.0,
    trend_score: float | None = 50.0,
    status: ProductStatus = ProductStatus.displayed,
    brand: str | None = "Sandro",
    color: str | None = "noir",
    size: str | None = None,
) -> Product:
    p = Product(
        barcode=f"P-{uuid.uuid4().hex[:8]}",
        name=name,
        category_id=category.id,
        sale_price=sale_price,
        status=status,
        zone_id=zone_id,
        trend_score=trend_score,
        brand=brand,
        color=color,
        size=size,
    )
    session.add(p)
    await session.flush()
    return p


# ---------------------------------------------------------------------------
# score_bucket
# ---------------------------------------------------------------------------


def test_score_bucket_thresholds():
    assert score_bucket(80) == "hot"
    assert score_bucket(60) == "warm"
    assert score_bucket(30) == "slow"
    assert score_bucket(10) == "cold"
    assert score_bucket(None) == "unknown"


# ---------------------------------------------------------------------------
# zone_occupancy (P2-005)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_zone_occupancy_returns_one_row_per_zone_with_counts(session):
    cat = await _make_category(session, "Robes")
    z1 = await _make_zone(session, name="Femme habillée", capacity=20, product_types="robes, jupes", display_order=1)
    z2 = await _make_zone(session, name="Vitrine femme", capacity=10, product_types="robes", display_order=0)
    await _make_product(session, name="A", category=cat, zone_id=z1.id, trend_score=80)
    await _make_product(session, name="B", category=cat, zone_id=z1.id, trend_score=40)
    await _make_product(session, name="C", category=cat, zone_id=z2.id, trend_score=90)

    rows = await MerchandisingService(session).zone_occupancy()
    assert len(rows) == 2
    by_name = {r["name"]: r for r in rows}
    assert by_name["Femme habillée"]["n_products"] == 2
    assert by_name["Femme habillée"]["occupancy_pct"] == 10.0
    assert by_name["Femme habillée"]["avg_score"] == 60.0
    assert by_name["Femme habillée"]["score_bucket"] == "warm"
    # Window detection via name keyword
    assert by_name["Vitrine femme"]["is_window"] is True
    assert by_name["Femme habillée"]["is_window"] is False


@pytest.mark.anyio
async def test_zone_occupancy_handles_zero_zones(session):
    rows = await MerchandisingService(session).zone_occupancy()
    assert rows == []


# ---------------------------------------------------------------------------
# suggest_zone (P2-006)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_suggest_hot_product_routes_to_window(session):
    cat = await _make_category(session, "Robes", Gender.femme)
    window = await _make_zone(
        session, name="Vitrine femme", capacity=4,
        min_trend_score=75, assignment_priority=10,
    )
    rack = await _make_zone(
        session, name="Rack robes", capacity=30, product_types="robes",
        assignment_priority=60,
    )
    hot = await _make_product(
        session, name="Robe Hermes", category=cat, trend_score=85,
        status=ProductStatus.tagged,
    )

    suggestion = await MerchandisingService(session).suggest_zone(hot)
    assert suggestion.should_go_to_window is True
    assert suggestion.primary_zone_id == str(window.id)
    assert suggestion.alternative_zone_id == str(rack.id)


@pytest.mark.anyio
async def test_suggest_falls_back_when_window_full(session):
    cat = await _make_category(session, "Robes", Gender.femme)
    window = await _make_zone(
        session, name="Vitrine femme", capacity=2,
        min_trend_score=75, assignment_priority=10,
    )
    rack = await _make_zone(
        session, name="Rack robes", capacity=30, product_types="robes",
        assignment_priority=60,
    )
    # Fill the window
    for _ in range(2):
        await _make_product(
            session, name="Filler", category=cat, zone_id=window.id,
            status=ProductStatus.displayed,
        )
    hot = await _make_product(
        session, name="Robe Hermes", category=cat, trend_score=85,
        status=ProductStatus.tagged,
    )

    suggestion = await MerchandisingService(session).suggest_zone(hot)
    assert suggestion.should_go_to_window is False
    assert suggestion.primary_zone_id == str(rack.id)


@pytest.mark.anyio
async def test_suggest_picks_least_loaded_category_match(session):
    cat = await _make_category(session, "Robes")
    less_loaded = await _make_zone(
        session, name="Femme A", capacity=20, product_types="robes",
        display_order=2,
    )
    more_loaded = await _make_zone(
        session, name="Femme B", capacity=20, product_types="robes",
        display_order=1,
    )
    # Saturate B more than A
    for _ in range(10):
        await _make_product(
            session, name="X", category=cat, zone_id=more_loaded.id,
            status=ProductStatus.displayed,
        )
    for _ in range(2):
        await _make_product(
            session, name="X", category=cat, zone_id=less_loaded.id,
            status=ProductStatus.displayed,
        )

    warm = await _make_product(
        session, name="Robe", category=cat, trend_score=55,
        status=ProductStatus.tagged,
    )
    suggestion = await MerchandisingService(session).suggest_zone(warm)
    assert suggestion.primary_zone_id == str(less_loaded.id)
    assert suggestion.should_go_to_window is False


@pytest.mark.anyio
async def test_suggest_with_no_category_match_falls_back(session):
    """A category that no zone declares → fall back to least-loaded zone."""
    cat = await _make_category(session, "Bijoux")  # no zone covers bijoux
    rack = await _make_zone(session, name="Rack robes", capacity=30, product_types="robes")
    p = await _make_product(
        session, name="Collier", category=cat, trend_score=40,
        status=ProductStatus.tagged,
    )
    suggestion = await MerchandisingService(session).suggest_zone(p)
    assert suggestion.primary_zone_id == str(rack.id)
    assert "défaut" in suggestion.rationale.lower()


@pytest.mark.anyio
async def test_suggest_with_no_zones_returns_no_suggestion(session):
    cat = await _make_category(session, "Robes")
    p = await _make_product(
        session, name="Robe", category=cat, status=ProductStatus.tagged,
    )
    suggestion = await MerchandisingService(session).suggest_zone(p)
    assert suggestion.primary_zone_id is None
    assert "Aucune zone" in suggestion.rationale


# ---------------------------------------------------------------------------
# suggest_zone — règles conditionnelles (refonte zonage 2026-05)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_suggest_woman_color_routes_to_color_zone(session):
    robes = await _make_category(session, "Robes", Gender.femme)
    await _make_zone(session, name="Tendance", min_trend_score=70, assignment_priority=40)
    entree = await _make_zone(
        session, name="Entrée", capacity=85,
        match_genders=["femme"], match_colors=["rose", "rouge"],
        assignment_priority=60,
    )
    await _make_zone(
        session, name="Droite 2", capacity=155,
        match_genders=["femme"], match_colors=["vert", "noir", "marron"],
        assignment_priority=62,
    )
    p = await _make_product(
        session, name="Robe rouge", category=robes, color="rouge",
        trend_score=40, size="M", status=ProductStatus.tagged,
    )
    s = await MerchandisingService(session).suggest_zone(p)
    assert s.primary_zone_id == str(entree.id)
    assert s.should_go_to_window is False


@pytest.mark.anyio
async def test_suggest_trendy_routes_to_vitrine_then_tendance(session):
    robes = await _make_category(session, "Robes", Gender.femme)
    vitrine = await _make_zone(
        session, name="Vitrine", capacity=8,
        min_trend_score=75, assignment_priority=10,
    )
    tendance = await _make_zone(
        session, name="Tendance", capacity=200,
        min_trend_score=70, assignment_priority=40,
    )
    await _make_zone(
        session, name="Entrée", match_genders=["femme"],
        match_colors=["rouge"], assignment_priority=60,
    )
    p = await _make_product(
        session, name="Robe rouge tendance", category=robes, color="rouge",
        trend_score=82, status=ProductStatus.tagged,
    )
    s = await MerchandisingService(session).suggest_zone(p)
    assert s.primary_zone_id == str(vitrine.id)
    assert s.should_go_to_window is True
    assert s.alternative_zone_id == str(tendance.id)


@pytest.mark.anyio
async def test_suggest_mens_polo_priority_list_capacity_aware(session):
    polo = await _make_category(session, "Polo", Gender.homme)
    rond = await _make_zone(
        session, name="Portant Rond Homme", capacity=2,
        match_genders=["homme"],
        product_types=json.dumps(["polo", "chemise", "veste"]),
        assignment_priority=30,
    )
    plein = await _make_zone(
        session, name="Portant Homme", capacity=2,
        match_genders=["homme"],
        product_types=json.dumps(["polo", "t-shirt", "short"]),
        assignment_priority=31,
    )
    mur = await _make_zone(
        session, name="Hommes", capacity=50,
        match_genders=["homme"], assignment_priority=32,
    )

    def _polo():
        return _make_product(
            session, name="Polo", category=polo, color="bleu",
            trend_score=40, status=ProductStatus.tagged,
        )

    # Vide → Portant Rond Homme (prio 30, catégorie polo).
    s1 = await MerchandisingService(session).suggest_zone(await _polo())
    assert s1.primary_zone_id == str(rond.id)

    # Rond Homme plein → Portant Homme.
    for _ in range(2):
        await _make_product(session, name="x", category=polo, zone_id=rond.id, status=ProductStatus.displayed)
    s2 = await MerchandisingService(session).suggest_zone(await _polo())
    assert s2.primary_zone_id == str(plein.id)

    # Les deux portants pleins → Hommes (fourre-tout).
    for _ in range(2):
        await _make_product(session, name="x", category=polo, zone_id=plein.id, status=ProductStatus.displayed)
    s3 = await MerchandisingService(session).suggest_zone(await _polo())
    assert s3.primary_zone_id == str(mur.id)


@pytest.mark.anyio
async def test_suggest_mens_shoes_to_chaussures_h(session):
    chauss = await _make_category(session, "Chaussures", Gender.homme)
    await _make_zone(
        session, name="Chaussures droite femme", capacity=48,
        match_genders=["femme"], product_types=json.dumps(["chaussures"]),
        assignment_priority=20,
    )
    ch_h = await _make_zone(
        session, name="Chaussures H", capacity=28,
        match_genders=["homme"], product_types=json.dumps(["chaussures"]),
        assignment_priority=21,
    )
    p = await _make_product(
        session, name="Sneakers homme", category=chauss, color="blanc",
        trend_score=40, status=ProductStatus.tagged,
    )
    s = await MerchandisingService(session).suggest_zone(p)
    assert s.primary_zone_id == str(ch_h.id)


@pytest.mark.anyio
async def test_suggest_large_size_woman_beats_color_zone(session):
    robes = await _make_category(session, "Robes", Gender.femme)
    droite3 = await _make_zone(
        session, name="Droite 3", capacity=115,
        match_genders=["femme"], match_size_classes=["grande"],
        assignment_priority=50,
    )
    await _make_zone(
        session, name="Entrée", capacity=85,
        match_genders=["femme"], match_colors=["rouge"],
        assignment_priority=60,
    )
    p = await _make_product(
        session, name="Robe XL rouge", category=robes, color="rouge",
        size="XL", trend_score=40, status=ProductStatus.tagged,
    )
    s = await MerchandisingService(session).suggest_zone(p)
    assert s.primary_zone_id == str(droite3.id)


@pytest.mark.anyio
async def test_suggest_color_overflow_to_lower_priority(session):
    robes = await _make_category(session, "Robes", Gender.femme)
    entree = await _make_zone(
        session, name="Entrée", capacity=1,
        match_genders=["femme"], match_colors=["rose", "rouge"],
        assignment_priority=60,
    )
    portant1 = await _make_zone(
        session, name="Portant 1", capacity=10,
        match_genders=["femme"], match_colors=["rouge", "jaune", "orange"],
        assignment_priority=63,
    )
    await _make_product(
        session, name="filler", category=robes, color="rouge",
        zone_id=entree.id, status=ProductStatus.displayed,
    )
    p = await _make_product(
        session, name="Robe rouge", category=robes, color="rouge",
        trend_score=40, status=ProductStatus.tagged,
    )
    s = await MerchandisingService(session).suggest_zone(p)
    assert s.primary_zone_id == str(portant1.id)


@pytest.mark.anyio
async def test_suggest_skips_zone_with_auto_assign_false(session):
    robes = await _make_category(session, "Robes", Gender.femme)
    await _make_zone(
        session, name="Entrée (off)", capacity=85,
        match_genders=["femme"], match_colors=["rouge"],
        assignment_priority=60, auto_assign=False,
    )
    portant1 = await _make_zone(
        session, name="Portant 1", capacity=10,
        match_genders=["femme"], match_colors=["rouge"],
        assignment_priority=63,
    )
    p = await _make_product(
        session, name="Robe rouge", category=robes, color="rouge",
        trend_score=40, status=ProductStatus.tagged,
    )
    s = await MerchandisingService(session).suggest_zone(p)
    assert s.primary_zone_id == str(portant1.id)


def test_classify_size_mapping():
    assert classify_size("XS") == "petite"
    assert classify_size("S") == "petite"
    assert classify_size("M") == "standard"
    assert classify_size("L") == "standard"
    assert classify_size("XL") == "grande"
    assert classify_size("XXL") == "grande"
    assert classify_size("36") == "petite"
    assert classify_size("40") == "standard"
    assert classify_size("44") == "grande"
    assert classify_size("grande taille") == "grande"
    assert classify_size(None) is None
    assert classify_size("") is None
    assert classify_size("Taille unique") is None


# ---------------------------------------------------------------------------
# locate_product (P2-008)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_locate_by_exact_barcode(session):
    cat = await _make_category(session, "Robes")
    zone = await _make_zone(session, name="Femme A", product_types="robes")
    p = await _make_product(
        session, name="Trench beige", category=cat, zone_id=zone.id,
    )
    # Force a specific barcode so the test is deterministic
    p.barcode = "EXACT123"
    await session.flush()

    rows = await MerchandisingService(session).locate_product("EXACT123")
    assert len(rows) == 1
    assert rows[0]["zone_name"] == "Femme A"


@pytest.mark.anyio
async def test_locate_by_fuzzy_name(session):
    cat = await _make_category(session, "Vestes")
    zone = await _make_zone(session, name="Vestes femme", product_types="vestes")
    await _make_product(
        session, name="Trench beige Burberry", category=cat, zone_id=zone.id,
    )

    rows = await MerchandisingService(session).locate_product("trench")
    assert len(rows) == 1
    assert "Trench" in rows[0]["name"]
    assert rows[0]["zone_name"] == "Vestes femme"


@pytest.mark.anyio
async def test_locate_returns_zone_null_for_unassigned_products(session):
    cat = await _make_category(session, "Sacs")
    p = await _make_product(session, name="Sac orphan", category=cat)
    p.zone_id = None
    await session.flush()

    rows = await MerchandisingService(session).locate_product("orphan")
    assert len(rows) == 1
    assert rows[0]["zone_id"] is None
    assert rows[0]["zone_name"] is None


@pytest.mark.anyio
async def test_locate_empty_query_returns_empty_list(session):
    rows = await MerchandisingService(session).locate_product("   ")
    assert rows == []


# ---------------------------------------------------------------------------
# propose_weekly_window (P2-007)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_propose_weekly_window_diversifies_by_category(session):
    cat_robes = await _make_category(session, "Robes")
    cat_pulls = await _make_category(session, "Pulls")
    cat_sacs = await _make_category(session, "Sacs")

    # Three robes with descending scores
    await _make_product(session, name="Robe 1", category=cat_robes, trend_score=90)
    await _make_product(session, name="Robe 2", category=cat_robes, trend_score=85)
    await _make_product(session, name="Robe 3", category=cat_robes, trend_score=80)
    # One pull, one sac with lower scores
    await _make_product(session, name="Pull", category=cat_pulls, trend_score=70)
    await _make_product(session, name="Sac", category=cat_sacs, trend_score=60)

    proposal = await MerchandisingService(session).propose_weekly_window(target_pieces=8)
    items = proposal.proposal["items"]
    # Diversification: at most one Robe in the first three picks before
    # we top up with the rest.
    cats = [i["product_id"] for i in items]
    assert len(cats) >= 3
    # Position labels are stamped
    assert items[0]["position"] == "central"
    assert items[1]["position"] in ("left", "right")
    assert items[2]["position"] in ("left", "right")


@pytest.mark.anyio
async def test_propose_weekly_window_is_idempotent_per_iso_week(session):
    cat = await _make_category(session, "Robes")
    await _make_product(session, name="Robe", category=cat, trend_score=80)

    svc = MerchandisingService(session)
    a = await svc.propose_weekly_window()
    b = await svc.propose_weekly_window()
    # Same row upserted, not a duplicate.
    assert a.id == b.id
    assert a.iso_week == b.iso_week


@pytest.mark.anyio
async def test_propose_weekly_window_theme_when_brand_dominates(session):
    cat = await _make_category(session, "Robes")
    cat2 = await _make_category(session, "Pulls")
    await _make_product(
        session, name="Robe", category=cat, brand="Sandro", trend_score=80,
    )
    await _make_product(
        session, name="Pull", category=cat2, brand="Sandro", trend_score=75,
    )
    proposal = await MerchandisingService(session).propose_weekly_window()
    assert "Sandro" in proposal.proposal["theme"]


@pytest.mark.anyio
async def test_propose_weekly_window_skips_unavailable_products(session):
    cat = await _make_category(session, "Robes")
    sold = await _make_product(
        session, name="Sold one", category=cat,
        status=ProductStatus.sold, trend_score=95,
    )
    on_floor = await _make_product(
        session, name="Floor", category=cat,
        status=ProductStatus.displayed, trend_score=70,
    )
    proposal = await MerchandisingService(session).propose_weekly_window()
    item_ids = [i["product_id"] for i in proposal.proposal["items"]]
    assert str(sold.id) not in item_ids
    assert str(on_floor.id) in item_ids


@pytest.mark.anyio
async def test_accept_window_proposal_stamps_user_and_time(session):
    user = User(
        username="manager", email="m@vintiz.fr",
        password_hash="x" * 60, role="manager", is_active=True,
    )
    session.add(user)
    cat = await _make_category(session, "Robes")
    await _make_product(session, name="Robe", category=cat, trend_score=80)

    svc = MerchandisingService(session)
    proposal = await svc.propose_weekly_window()
    accepted = await svc.accept_window_proposal(proposal.id, user.id)
    assert accepted.accepted_at is not None
    assert accepted.accepted_by_user_id == user.id


@pytest.mark.anyio
async def test_iso_week_key_format():
    # Pinned date so the test isn't time-of-year-dependent.
    when = datetime(2026, 4, 26, tzinfo=timezone.utc)  # Sunday → ISO week 17
    key = MerchandisingService.iso_week_key(when)
    assert key == "2026-W17"
