"""Embedded reporting engine — a safe, whitelisted ad-hoc query layer.

Powers the « Rapports sur-mesure » builder (a light PowerBI-style tool). The UI
never sends SQL: it picks a **dataset**, a **measure** (what to aggregate), an
optional **dimension** (what to group by, incl. a time grain) and a date range.
This module turns that spec into a parameterised SQLAlchemy aggregation over a
curated set of datasets/dimensions/measures, so the surface is safe by
construction (no arbitrary columns, no raw SQL).

Three datasets to start — ``sales`` (item-level), ``inventory`` (current stock)
and ``clients`` — each declaring its joins, its date field, its dimensions and
its measures. Adding a dataset is a dict entry; the query builder is generic.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client
from app.models.pos import Transaction, TransactionItem, TransactionType
from app.models.product import Category, Product, ProductStatus

# Statuses meaning "physically part of the live inventory" (back stock + floor).
_INVENTORY_STATUSES = [
    ProductStatus.stock, ProductStatus.received, ProductStatus.sorted,
    ProductStatus.tagged, ProductStatus.display, ProductStatus.displayed,
    ProductStatus.discounted, ProductStatus.deep_discounted,
]

_GRANULARITIES = ("day", "week", "month", "year")
CHART_TYPES = ("bar", "line", "pie", "kpi", "table")


def _time_bucket(col, granularity: str, dialect: str):
    """Portable string label that buckets a timestamp by the requested grain."""
    granularity = granularity if granularity in _GRANULARITIES else "month"
    if dialect == "postgresql":
        fmt = {
            "day": "YYYY-MM-DD", "week": 'IYYY-"W"IW', "month": "YYYY-MM", "year": "YYYY",
        }[granularity]
        return func.to_char(col, fmt)
    fmt = {
        "day": "%Y-%m-%d", "week": "%Y-W%W", "month": "%Y-%m", "year": "%Y",
    }[granularity]
    return func.strftime(fmt, col)


# ---------------------------------------------------------------------------
# Dataset registry
# ---------------------------------------------------------------------------
# Each dataset: build(cols) returns a select over the right joins + base filter;
# ``date_field`` is the timestamp used for the range filter + time dimension;
# ``dimensions`` maps key → {label, expr|None (None = time), time?}; ``measures``
# maps key → {label, expr, format}.

DATASETS: dict = {
    "sales": {
        "label": "Ventes (articles vendus)",
        "date_field": Transaction.created_at,
        "build": lambda cols: (
            select(*cols)
            .select_from(TransactionItem)
            .join(Transaction, TransactionItem.transaction_id == Transaction.id)
            .outerjoin(Product, TransactionItem.product_id == Product.id)
            .outerjoin(Category, Product.category_id == Category.id)
            .where(Transaction.transaction_type == TransactionType.sale)
        ),
        "dimensions": {
            "time": {"label": "Période", "time": True},
            "category": {"label": "Catégorie", "expr": Category.name},
            "brand": {"label": "Marque", "expr": Product.brand},
            "gender": {"label": "Genre", "expr": Product.gender},
            "color": {"label": "Couleur", "expr": Product.color},
            "size": {"label": "Taille", "expr": Product.size},
        },
        "measures": {
            "revenue": {"label": "Chiffre d'affaires", "expr": func.coalesce(func.sum(TransactionItem.line_total), 0), "format": "currency"},
            "quantity": {"label": "Quantité vendue", "expr": func.coalesce(func.sum(TransactionItem.quantity), 0), "format": "number"},
            "tickets": {"label": "Nombre de tickets", "expr": func.count(distinct(Transaction.id)), "format": "number"},
            "avg_price": {"label": "Prix moyen", "expr": func.coalesce(func.avg(TransactionItem.unit_price), 0), "format": "currency"},
        },
    },
    "inventory": {
        "label": "Stock (articles en boutique)",
        "date_field": Product.received_at,
        "build": lambda cols: (
            select(*cols)
            .select_from(Product)
            .outerjoin(Category, Product.category_id == Category.id)
            .where(Product.status.in_(_INVENTORY_STATUSES))
        ),
        "dimensions": {
            "category": {"label": "Catégorie", "expr": Category.name},
            "brand": {"label": "Marque", "expr": Product.brand},
            "status": {"label": "Statut", "expr": Product.status},
            "gender": {"label": "Genre", "expr": Product.gender},
            "color": {"label": "Couleur", "expr": Product.color},
            "size": {"label": "Taille", "expr": Product.size},
            "time": {"label": "Période d'arrivée", "time": True},
        },
        "measures": {
            "count": {"label": "Nombre d'articles", "expr": func.count(Product.id), "format": "number"},
            "stock_value": {"label": "Valeur de vente du stock", "expr": func.coalesce(func.sum(Product.sale_price), 0), "format": "currency"},
            "purchase_value": {"label": "Valeur d'achat du stock", "expr": func.coalesce(func.sum(Product.purchase_price), 0), "format": "currency"},
            "avg_trend": {"label": "Note tendance moyenne", "expr": func.coalesce(func.avg(Product.trend_score), 0), "format": "number"},
        },
    },
    "clients": {
        "label": "Clients",
        "date_field": Client.created_at,
        "build": lambda cols: (
            select(*cols)
            .select_from(Client)
            .where(Client.deletion_requested_at.is_(None))
        ),
        "dimensions": {
            "segment": {"label": "Segment RFM", "expr": Client.rfm_segment},
            "gender_profile": {"label": "Genre déclaré", "expr": Client.gender_profile},
            "age_band": {"label": "Tranche d'âge", "expr": Client.age_band},
            "time": {"label": "Période d'inscription", "time": True},
        },
        "measures": {
            "count": {"label": "Nombre de clients", "expr": func.count(Client.id), "format": "number"},
            "avoir": {"label": "Avoir cumulé", "expr": func.coalesce(func.sum(Client.avoir_credit), 0), "format": "currency"},
        },
    },
}


def catalog() -> dict:
    """The queryable surface (datasets → dimensions + measures) for the builder."""
    out = []
    for key, ds in DATASETS.items():
        out.append({
            "key": key,
            "label": ds["label"],
            "has_time": any(d.get("time") for d in ds["dimensions"].values()),
            "dimensions": [
                {"key": dk, "label": dv["label"], "time": bool(dv.get("time"))}
                for dk, dv in ds["dimensions"].items()
            ],
            "measures": [
                {"key": mk, "label": mv["label"], "format": mv.get("format", "number")}
                for mk, mv in ds["measures"].items()
            ],
        })
    return {
        "datasets": out,
        "granularities": list(_GRANULARITIES),
        "chart_types": list(CHART_TYPES),
    }


def _coerce_key(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def _num(value) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return 0.0


async def run_query(
    db: AsyncSession,
    *,
    dataset: str,
    measure: str,
    dimension: str | None = None,
    granularity: str = "month",
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    filters: dict | None = None,
    limit: int = 200,
) -> dict:
    """Execute one widget query and return ``{format, rows:[{key,value}], ...}``.

    Raises ``ValueError`` for any unknown dataset/measure/dimension so the API
    can answer 400 rather than leaking an internal error."""
    ds = DATASETS.get(dataset)
    if ds is None:
        raise ValueError(f"dataset inconnu : {dataset}")
    if measure not in ds["measures"]:
        raise ValueError(f"mesure inconnue pour {dataset} : {measure}")
    if dimension is not None and dimension not in ds["dimensions"]:
        raise ValueError(f"dimension inconnue pour {dataset} : {dimension}")

    dialect = db.bind.dialect.name if db.bind is not None else "postgresql"
    measure_def = ds["measures"][measure]
    m_expr = measure_def["expr"].label("value")
    date_field = ds["date_field"]

    dim_expr = None
    is_time = False
    if dimension is not None:
        ddef = ds["dimensions"][dimension]
        is_time = bool(ddef.get("time"))
        dim_expr = _time_bucket(date_field, granularity, dialect) if is_time else ddef["expr"]

    cols = [dim_expr.label("key"), m_expr] if dim_expr is not None else [m_expr]
    stmt = ds["build"](cols)

    if date_field is not None:
        if date_from is not None:
            stmt = stmt.where(date_field >= date_from)
        if date_to is not None:
            stmt = stmt.where(date_field < date_to)

    for fk, fv in (filters or {}).items():
        fdef = ds["dimensions"].get(fk)
        if fdef is not None and fdef.get("expr") is not None and fv is not None:
            stmt = stmt.where(fdef["expr"] == fv)

    if dim_expr is not None:
        stmt = stmt.group_by(dim_expr)
        # Time series sort chronologically; categorical sort by value desc.
        stmt = stmt.order_by(dim_expr.asc() if is_time else m_expr.desc())
        stmt = stmt.limit(max(1, min(limit, 1000)))
        result = await db.execute(stmt)
        rows = [{"key": _coerce_key(r[0]), "value": _num(r[1])} for r in result.all()]
    else:
        value = (await db.execute(stmt)).scalar_one_or_none()
        rows = [{"key": measure_def["label"], "value": _num(value)}]

    return {
        "dataset": dataset,
        "measure": measure,
        "measure_label": measure_def["label"],
        "dimension": dimension,
        "granularity": granularity if is_time else None,
        "format": measure_def.get("format", "number"),
        "rows": rows,
    }
