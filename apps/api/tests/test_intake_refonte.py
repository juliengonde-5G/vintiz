"""Tests for the product-intake refonte.

Covers:
- the stock / rayon placement reference on the Zebra label,
- the automatic stamping of entrée-stock / mise-en-rayon dates,
- the store-operations audit metrics + deterministic fallback narrative.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base
from app.models.product import Category, Product, ProductPhoto, ProductStatus
from app.services.store_ops_audit import (
    _fallback_narrative,
    build_store_ops_report,
    collect_metrics,
)
from app.services.zebra_zpl import (
    LabelData,
    build_label_zpl,
    product_to_label_data,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def session():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    tables = [
        Category.__table__,
        Product.__table__,
        ProductPhoto.__table__,
    ]
    async with eng.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=tables))
    Session = async_sessionmaker(eng, expire_on_commit=False)
    async with Session() as s:
        yield s
    await eng.dispose()


# ---------------------------------------------------------------------------
# Label — placement reference (mise en stock / mise en rayon)
# ---------------------------------------------------------------------------


class _StubProduct:
    """Duck-typed product for product_to_label_data without a DB row."""

    def __init__(self, status, received_at=None, shelf_date=None):
        self.name = "Robe noire"
        self.category = None
        self.size = "M"
        self.condition = "bon"
        self.sale_price = 25.0
        self.barcode = "VTZ-2026-00999"
        self.status = status
        self.received_at = received_at
        self.shelf_date = shelf_date
        self.displayed_at = None


def test_label_default_keeps_legacy_rayon_lines():
    """A LabelData without an explicit location renders the historical lines."""
    zpl = build_label_zpl(
        LabelData(
            product_name="Veste",
            category="Vestes",
            size="M",
            condition="bon",
            sale_price=12.0,
            barcode="VTZ-1",
            shelf_date=datetime(2026, 5, 14, tzinfo=timezone.utc),
        )
    )
    assert "Rayon depuis : 14/05/2026" in zpl
    assert "Démarque le :" in zpl


def test_label_stock_location_shows_entry_line():
    data = LabelData(
        product_name="Pull",
        category="Pulls",
        size="L",
        condition="bon",
        sale_price=18.0,
        barcode="VTZ-2",
        shelf_date=None,
        location="stock",
        entry_date=datetime(2026, 5, 16, tzinfo=timezone.utc),
    )
    zpl = build_label_zpl(data)
    assert "En stock depuis : 16/05/2026" in zpl
    assert "A mettre en rayon" in zpl
    # Stock items don't carry a markdown deadline.
    assert "Démarque le :" not in zpl


def test_label_condition_code_rendered_as_display():
    """A stored condition code (e.g. ``tres_bon``) prints as French text."""
    data = LabelData(
        product_name="Robe", category="Robes", size="M", condition="tres_bon",
        sale_price=30.0, barcode="VTZ-3", shelf_date=None,
    )
    zpl = build_label_zpl(data)
    assert "Très bon état" in zpl
    assert "tres_bon" not in zpl


def test_label_condition_display_string_passthrough():
    """An already-human condition string is left untouched (legacy fixtures)."""
    data = LabelData(
        product_name="Robe", category="Robes", size="M", condition="Comme neuf",
        sale_price=30.0, barcode="VTZ-4", shelf_date=None,
    )
    assert "Comme neuf" in build_label_zpl(data)


def test_product_to_label_data_derives_location_from_status():
    on_floor = product_to_label_data(
        _StubProduct(ProductStatus.displayed, shelf_date=datetime(2026, 5, 14, tzinfo=timezone.utc))
    )
    assert on_floor.location == "rayon"

    in_stock = product_to_label_data(
        _StubProduct(ProductStatus.stock, received_at=datetime(2026, 5, 16, tzinfo=timezone.utc))
    )
    assert in_stock.location == "stock"
    assert in_stock.entry_date == datetime(2026, 5, 16, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Lifecycle date stamping (entrée stock / mise en rayon)
# ---------------------------------------------------------------------------


def test_stamp_lifecycle_dates_sets_received_for_stock():
    from app.api.inventory.router import _stamp_lifecycle_dates

    p = Product(
        barcode="VTZ-S", name="x", category_id=uuid.uuid4(),
        purchase_price=0, sale_price=10, status=ProductStatus.stock,
    )
    _stamp_lifecycle_dates(p)
    assert p.received_at is not None
    # Not on the floor → no shelf date.
    assert p.shelf_date is None
    assert p.displayed_at is None


def test_stamp_lifecycle_dates_sets_shelf_for_floor():
    from app.api.inventory.router import _stamp_lifecycle_dates

    p = Product(
        barcode="VTZ-D", name="x", category_id=uuid.uuid4(),
        purchase_price=0, sale_price=10, status=ProductStatus.display,
    )
    _stamp_lifecycle_dates(p)
    assert p.received_at is not None
    assert p.shelf_date is not None
    assert p.displayed_at is not None


# ---------------------------------------------------------------------------
# Store-ops audit
# ---------------------------------------------------------------------------


async def _seed_audit_fixture(session):
    cat = Category(name="Robes")
    session.add(cat)
    await session.flush()
    now = datetime.now(timezone.utc)

    common = dict(category_id=cat.id, purchase_price=0, brand="Sandro", size="M", color="Noir")

    a = Product(barcode="A", name="A stock", sale_price=20, status=ProductStatus.stock,
                received_at=now, photo_url=None, **common)
    b = Product(barcode="B", name="B rayon sans zone", sale_price=20, status=ProductStatus.display,
                received_at=now, shelf_date=None, zone_id=None, photo_url="/uploads/products/b/1.jpg",
                **common)
    c = Product(barcode="C", name="C rayon complet", sale_price=20, status=ProductStatus.displayed,
                received_at=now, shelf_date=now, zone_id=uuid.uuid4(),
                photo_url="/uploads/products/c/1.jpg", **common)
    session.add_all([a, b, c])
    await session.flush()

    # C has an AI-analyzed photo.
    session.add(ProductPhoto(product_id=c.id, url="/uploads/products/c/1.jpg",
                             order_index=0, is_primary=True, ai_analyzed_at=now))
    await session.flush()
    return a, b, c


@pytest.mark.anyio
async def test_collect_metrics_counts_intake_health(session):
    await _seed_audit_fixture(session)
    m = await collect_metrics(session)

    assert m["active_total"] == 3
    assert m["en_stock"] == 1
    assert m["en_magasin"] == 2
    assert m["sans_photo"] == 1            # A
    assert m["sans_zone_en_rayon"] == 1    # B
    assert m["sans_date_rayon"] == 1       # B
    assert m["analyse_ia"] == 1            # C
    assert m["champs_incomplets"] == 0     # all carry brand/size/color
    assert m["stock_stagnant"] == 0        # A entered just now


@pytest.mark.anyio
async def test_build_report_uses_fallback_without_ai(session):
    await _seed_audit_fixture(session)
    report = await build_store_ops_report(session)

    assert report["ai_generated"] is False
    assert "metrics" in report and "audit" in report
    audit = report["audit"]
    assert audit["diagnostic"]
    # B's missing zone must surface as a weak point.
    assert any("zone" in w.lower() for w in audit["points_faibles"])


def test_fallback_narrative_empty_inventory():
    audit = _fallback_narrative({
        "active_total": 0, "en_stock": 0, "en_magasin": 0, "sans_photo": 0,
        "pct_sans_photo": 0, "sans_date_entree": 0, "sans_zone_en_rayon": 0,
        "sans_date_rayon": 0, "champs_incomplets": 0, "pct_champs_incomplets": 0,
        "analyse_ia": 0, "pct_analyse_ia": 0, "stock_stagnant": 0, "stagnant_days": 30,
    })
    assert audit["points_faibles"] == []
    assert audit["actions_prioritaires"] == []


@pytest.mark.anyio
async def test_store_ops_routes_registered():
    from app.main import app

    paths = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/api/ai/persona/store-ops" in paths
    assert "/api/ai/persona/store-ops/regenerate" in paths


# ---------------------------------------------------------------------------
# Pricing engine — brand awareness + justification
# ---------------------------------------------------------------------------


def test_normalize_condition_accepts_codes_and_ai_strings():
    from app.services.ai_pricing import _normalize_condition

    assert _normalize_condition("excellent") == "neuf"
    assert _normalize_condition("neuf") == "neuf"
    assert _normalize_condition("très bon état") == "tres_bon"
    assert _normalize_condition("tres_bon") == "tres_bon"
    assert _normalize_condition("correct") == "correct"
    assert _normalize_condition("bon") == "bon"
    assert _normalize_condition(None) is None


def test_fallback_brand_factor_classifies_known_labels():
    from app.services.ai_pricing import _fallback_brand_factor

    factor, label = _fallback_brand_factor("Chanel")
    assert label == "premium" and factor > 1.0
    factor, label = _fallback_brand_factor("Sandro Paris")
    assert label == "mid" and factor > 1.0
    assert _fallback_brand_factor("Marque Inconnue") == (1.0, None)
    assert _fallback_brand_factor(None) == (1.0, None)


def test_build_justification_mentions_new_price_anchor():
    from app.services.ai_pricing import _build_justification

    text = _build_justification(
        suggested=45.0, brand="Sandro", brand_label="mid", cond_code="tres_bon",
        new_price=120.0, resale_from_new=54.0, grid_suggestion=30.0,
        avg_sold_price=None, sales_count=0,
    )
    assert "120" in text and "Sandro" in text and "45" in text


@pytest.mark.anyio
async def test_get_brand_tier_substring_match():
    from app.models.brand_tier import BrandTier, BrandTierLevel
    from app.services import brand_tiers

    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(
            lambda c: Base.metadata.create_all(c, tables=[BrandTier.__table__])
        )
    Session = async_sessionmaker(eng, expire_on_commit=False)
    brand_tiers.invalidate_cache()
    try:
        async with Session() as s:
            s.add(BrandTier(name="sandro", tier=BrandTierLevel.mid))
            await s.commit()
            assert await brand_tiers.get_brand_tier(s, "SANDRO PARIS S.A.S.") == "mid"
            assert await brand_tiers.get_brand_tier(s, "Inconnue") is None
            assert await brand_tiers.get_brand_tier(s, None) is None
    finally:
        brand_tiers.invalidate_cache()
        await eng.dispose()
