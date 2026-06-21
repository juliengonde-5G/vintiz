"""Reference pricing grid — floor prices per category × brand bucket.

Backs the "grille tarifaire de référence" : the boutique's laminated floor-price
chart. For each category it holds a ``standard`` floor (mid/basic/unknown
brands) and a ``premium`` floor "à partir de" (premium/luxury brands). The grid
is advisory — :func:`check` tells the UI whether a chosen sale price is below
the applicable floor so it can raise a non-blocking notification.

Defaults come from :data:`REFERENCE_GRID_DEFAULTS` (transcribed from the Vintiz
sheet) and are auto-filled for matching categories the first time the admin page
is opened, then editable per category.
"""

from __future__ import annotations

import unicodedata

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.price_reference import PriceReference
from app.models.product import Category

# ---------------------------------------------------------------------------
# Vintiz reference grid (category → standard floor, premium "à partir de" floor)
# Transcribed from the laminated "GRILLE TARIFAIRE VINTIZ" sheet.
# ---------------------------------------------------------------------------
# (canonical_name, standard_price, premium_price, note)
REFERENCE_GRID_DEFAULTS: list[tuple[str, float, float, str | None]] = [
    ("BASKET", 8, 15, None),
    ("BIJOUX", 2, 5, None),
    ("BLOUSON", 12, 15, None),
    ("BONNET/CHAPEAU", 4, 6, None),
    ("BOTTE/BOTTINE/CHAUSSURE", 10, 12, "Synthétique 10 € / cuir à partir de 12 €"),
    ("CARACO/DEBARDEUR", 4, 5, None),
    ("CEINTURES", 3, 6, None),
    ("CHEMISIER/TEE-SHIRT MC", 5, 6, "Manches courtes"),
    ("CHEMISIER/TEE-SHIRT ML", 6, 7, "Manches longues"),
    ("ECHARPES", 3, 5, None),
    ("FOULARD", 2.5, 3, None),
    ("FOURRURE COURTE", 12, 15, None),
    ("FOURRURE LONGUE", 18, 25, None),
    ("GILET/PULL/SWEAT", 6, 8, None),
    ("IMPERMEABLE", 15, 18, None),
    ("JUPE", 5, 7, None),
    ("MANTEAU COURT", 15, 20, None),
    ("MANTEAU LONG", 18, 25, None),
    ("MAILLOT DE BAIN", 4, 6, None),
    ("MAILLOT DE BAIN HAUT", 2, 3, None),
    ("MAILLOT DE BAIN BAS", 2, 3, None),
    ("PANTALON/JEAN", 9, 15, None),
    ("ROBE", 10, 15, None),
    ("SAC A MAIN", 7, 10, None),
    ("SHORT/BERMUDA", 4, 5, None),
    ("VESTE", 10, 12, None),
]

# Brand tiers that count as "premium" for the reference grid (the rest — mid,
# basic, unknown, no brand — fall in the "standard" bucket).
_PREMIUM_TIERS = {"premium", "luxury"}


def _norm(value: str | None) -> str:
    """Accent-stripped, upper-cased, whitespace-collapsed comparison key."""
    if not value:
        return ""
    nfkd = unicodedata.normalize("NFKD", value)
    no_accent = "".join(c for c in nfkd if not unicodedata.combining(c))
    out = no_accent.upper().replace("-", " ").replace("_", " ")
    return " ".join(out.split())


def _singularize(token: str) -> str:
    """Drop a trailing plural 'S' from each word so ROBES ~ ROBE."""
    return " ".join(w[:-1] if len(w) > 3 and w.endswith("S") else w for w in token.split())


def _aliases(canonical: str) -> set[str]:
    """Every normalized spelling a DB category could use for ``canonical``.

    Splits on '/' so "GILET/PULL/SWEAT" also matches a category named just
    "Pull", and adds singular variants (ROBES → ROBE)."""
    keys: set[str] = set()
    norm_full = _norm(canonical)
    for piece in (canonical, *canonical.split("/")):
        n = _norm(piece)
        if n:
            keys.add(n)
            keys.add(_singularize(n))
    keys.add(norm_full)
    keys.add(_singularize(norm_full))
    return {k for k in keys if k}


# Precompute alias → default index for fast matching.
_ALIAS_INDEX: dict[str, int] = {}
for _i, (_name, *_rest) in enumerate(REFERENCE_GRID_DEFAULTS):
    for _alias in _aliases(_name):
        # First writer wins; more specific canonical names are listed once, so
        # collisions (e.g. between the two CHEMISIER rows on the shared head)
        # simply keep the earliest — the suffixed alias still disambiguates.
        _ALIAS_INDEX.setdefault(_alias, _i)


def default_for_name(category_name: str | None) -> dict | None:
    """Reference floors from the Vintiz grid that match ``category_name``."""
    n = _norm(category_name)
    if not n:
        return None
    idx = _ALIAS_INDEX.get(n)
    if idx is None:
        idx = _ALIAS_INDEX.get(_singularize(n))
    if idx is None:
        return None
    name, standard, premium, note = REFERENCE_GRID_DEFAULTS[idx]
    return {
        "canonical": name,
        "standard_price": float(standard),
        "premium_price": float(premium),
        "note": note,
    }


async def brand_bucket(db: AsyncSession, brand: str | None) -> str:
    """'premium' for premium/luxury brands, otherwise 'standard'."""
    if not brand:
        return "standard"
    from app.services import brand_tiers

    tier = await brand_tiers.get_brand_tier(db, brand)
    return "premium" if tier in _PREMIUM_TIERS else "standard"


def _row(ref: PriceReference) -> dict:
    return {
        "standard_price": float(ref.standard_price) if ref.standard_price is not None else None,
        "premium_price": float(ref.premium_price) if ref.premium_price is not None else None,
        "note": ref.note,
    }


async def get_reference(db: AsyncSession, category_id) -> PriceReference | None:
    return (
        await db.execute(select(PriceReference).where(PriceReference.category_id == category_id))
    ).scalar_one_or_none()


async def effective_reference(db: AsyncSession, category_id, category_name: str | None = None) -> dict | None:
    """The applicable floors for a category: stored row if any, else the Vintiz
    default matched by name. Returns ``None`` when neither exists."""
    ref = await get_reference(db, category_id)
    if ref is not None and (ref.standard_price is not None or ref.premium_price is not None):
        data = _row(ref)
        data["source"] = "configured"
        return data
    if category_name is None:
        category_name = (
            await db.execute(select(Category.name).where(Category.id == category_id))
        ).scalar_one_or_none()
    default = default_for_name(category_name)
    if default is None:
        return None
    return {
        "standard_price": default["standard_price"],
        "premium_price": default["premium_price"],
        "note": default["note"],
        "source": "default",
    }


async def check(db: AsyncSession, category_id, brand: str | None, price: float | None) -> dict:
    """Compare a sale price against the applicable reference floor.

    Returns a structure the UI can show as a non-blocking notification::

        {has_reference, below, floor, bucket, standard_floor, premium_floor,
         note, source}
    """
    category_name = (
        await db.execute(select(Category.name).where(Category.id == category_id))
    ).scalar_one_or_none()
    ref = await effective_reference(db, category_id, category_name)
    if ref is None:
        return {
            "has_reference": False, "below": False, "floor": None, "bucket": "standard",
            "standard_floor": None, "premium_floor": None, "note": None, "source": None,
            "category_name": category_name,
        }
    bucket = await brand_bucket(db, brand)
    standard_floor = ref.get("standard_price")
    premium_floor = ref.get("premium_price")
    # Applicable floor: the bucket's value, falling back to the other bucket when
    # one is unset (a single configured floor still guards both buckets).
    if bucket == "premium":
        floor = premium_floor if premium_floor is not None else standard_floor
    else:
        floor = standard_floor if standard_floor is not None else premium_floor
    below = price is not None and floor is not None and float(price) < float(floor)
    return {
        "has_reference": True,
        "below": below,
        "floor": floor,
        "bucket": bucket,
        "standard_floor": standard_floor,
        "premium_floor": premium_floor,
        "note": ref.get("note"),
        "source": ref.get("source"),
        "category_name": category_name,
    }


async def upsert(db: AsyncSession, category_id, *, standard_price, premium_price, note=None) -> PriceReference:
    ref = await get_reference(db, category_id)
    if ref is None:
        ref = PriceReference(category_id=category_id)
        db.add(ref)
    ref.standard_price = standard_price
    ref.premium_price = premium_price
    ref.note = note
    await db.flush()
    return ref


async def delete_reference(db: AsyncSession, category_id) -> bool:
    ref = await get_reference(db, category_id)
    if ref is None:
        return False
    await db.delete(ref)
    await db.flush()
    return True


async def list_for_admin(db: AsyncSession) -> list[dict]:
    """Every category with its stored reference (if any) + the Vintiz default
    that matches its name, for the admin grid editor."""
    cats = (await db.execute(select(Category).order_by(Category.name))).scalars().all()
    refs = {
        r.category_id: r
        for r in (await db.execute(select(PriceReference))).scalars().all()
    }
    out: list[dict] = []
    for cat in cats:
        ref = refs.get(cat.id)
        default = default_for_name(cat.name)
        out.append({
            "category_id": str(cat.id),
            "category_name": cat.name,
            "standard_price": float(ref.standard_price) if ref and ref.standard_price is not None else None,
            "premium_price": float(ref.premium_price) if ref and ref.premium_price is not None else None,
            "note": ref.note if ref else None,
            "configured": ref is not None,
            "default_standard": default["standard_price"] if default else None,
            "default_premium": default["premium_price"] if default else None,
            "default_note": default["note"] if default else None,
            "has_default": default is not None,
        })
    return out


async def seed_defaults(db: AsyncSession, *, overwrite: bool = False) -> int:
    """Pre-fill reference rows from the Vintiz grid for every category whose
    name matches a default. Skips already-configured categories unless
    ``overwrite``. Returns the number of rows written."""
    cats = (await db.execute(select(Category))).scalars().all()
    existing = {
        r.category_id: r
        for r in (await db.execute(select(PriceReference))).scalars().all()
    }
    written = 0
    for cat in cats:
        default = default_for_name(cat.name)
        if default is None:
            continue
        ref = existing.get(cat.id)
        if ref is not None and not overwrite:
            continue
        if ref is None:
            ref = PriceReference(category_id=cat.id)
            db.add(ref)
        ref.standard_price = default["standard_price"]
        ref.premium_price = default["premium_price"]
        ref.note = default["note"]
        written += 1
    if written:
        await db.flush()
    return written


async def has_any(db: AsyncSession) -> bool:
    return (
        await db.execute(select(PriceReference.id).limit(1))
    ).scalar_one_or_none() is not None
