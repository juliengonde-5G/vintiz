"""Bulk product import from CSV (P3-006).

Camille drops a spreadsheet of new arrivals — typically exported from
the Solidarité Textiles sorting centre's tracker — and the manager
admin pushes it through this service. Each row becomes a Product;
duplicates (by barcode) are skipped, malformed rows are reported back
with their line number so Camille can fix and re-upload.

Validation rules:
- ``name`` and ``sale_price`` are required.
- Either ``category_id`` (UUID) or ``category_name`` (resolved to an
  existing category) must be supplied. Categories are NOT auto-created
  to avoid silent typos creating dozens of "Robe", "Robes", "robes…".
- ``barcode`` is optional; we generate a UUID-prefix when blank
  (matches the inventory_router /products endpoint behaviour).
- ``status`` defaults to ``received`` so freshly-imported items go
  through the proper life-cycle (P1-006).
- Numeric fields (sale_price, purchase_price, week_number) tolerate
  comma decimal separator (FR locale).

The service is fully async-friendly and idempotent on barcode: a
re-upload of the same CSV just reports those rows as "skipped — already
exists".
"""

from __future__ import annotations

import csv
import io
import uuid
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Category, Product, ProductStatus


REQUIRED_COLUMNS = {"name", "sale_price"}
OPTIONAL_COLUMNS = {
    "barcode",
    "category_id",
    "category_name",
    "brand",
    "color",
    "size",
    "condition",
    "purchase_price",
    "week_number",
    "status",
    "description",
}
ALL_COLUMNS = REQUIRED_COLUMNS | OPTIONAL_COLUMNS


@dataclass
class RowError:
    line: int  # 1-indexed including header (so line 2 = first data row)
    message: str


@dataclass
class ImportSummary:
    total_rows: int = 0
    imported: int = 0
    skipped: int = 0  # already-existing barcode
    errors: list[RowError] = field(default_factory=list)
    created_ids: list[str] = field(default_factory=list)


def _coerce_decimal(raw: str, field: str) -> Decimal:
    if raw is None or str(raw).strip() == "":
        raise ValueError(f"{field} is required")
    cleaned = str(raw).strip().replace(",", ".").replace(" ", "")
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError(f"{field} is not a valid number: {raw!r}") from exc


def _coerce_int(raw: str, field: str) -> int | None:
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return int(str(raw).strip())
    except ValueError as exc:
        raise ValueError(f"{field} must be an integer: {raw!r}") from exc


def _coerce_status(raw: str | None) -> ProductStatus:
    if raw is None or str(raw).strip() == "":
        return ProductStatus.received
    try:
        return ProductStatus(str(raw).strip().lower())
    except ValueError as exc:
        valid = ", ".join(s.value for s in ProductStatus)
        raise ValueError(
            f"status {raw!r} is not one of: {valid}"
        ) from exc


class ImportCsvService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _resolve_category(
        self,
        category_id_raw: str | None,
        category_name_raw: str | None,
        cache: dict[str, uuid.UUID],
    ) -> uuid.UUID:
        # ID first when both are supplied — the spreadsheet's authoritative.
        if category_id_raw and category_id_raw.strip():
            try:
                cat_id = uuid.UUID(category_id_raw.strip())
            except ValueError as exc:
                raise ValueError(
                    f"category_id is not a UUID: {category_id_raw!r}"
                ) from exc
            row = await self.db.execute(
                select(Category.id).where(Category.id == cat_id)
            )
            if row.scalar_one_or_none() is None:
                raise ValueError(f"category_id {cat_id} does not exist")
            return cat_id

        if category_name_raw and category_name_raw.strip():
            key = category_name_raw.strip().lower()
            if key in cache:
                return cache[key]
            row = await self.db.execute(
                select(Category.id, Category.name)
                .where(Category.name.ilike(category_name_raw.strip()))
            )
            found = row.first()
            if found is None:
                raise ValueError(
                    f"category_name {category_name_raw!r} not found — create "
                    "the category in the admin first."
                )
            cache[key] = found[0]
            return found[0]

        raise ValueError("either category_id or category_name is required")

    async def _existing_barcodes(
        self, barcodes: Iterable[str]
    ) -> set[str]:
        cleaned = [b for b in barcodes if b]
        if not cleaned:
            return set()
        result = await self.db.execute(
            select(Product.barcode).where(Product.barcode.in_(cleaned))
        )
        return {b for (b,) in result.all()}

    async def import_csv(
        self,
        csv_bytes: bytes,
        *,
        dry_run: bool = False,
    ) -> ImportSummary:
        """Parse the CSV bytes, validate, persist (unless dry_run)."""
        text = csv_bytes.decode("utf-8-sig")  # tolerate BOM from Excel
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            raise ValueError("CSV has no header row")

        normalized_fields = {
            (name or "").strip().lower() for name in reader.fieldnames
        }
        missing = REQUIRED_COLUMNS - normalized_fields
        if missing:
            raise ValueError(
                "CSV is missing required column(s): "
                + ", ".join(sorted(missing))
            )

        # Pre-pass: collect explicit barcodes to dedupe in one query.
        rows: list[dict] = []
        for raw in reader:
            rows.append({(k or "").strip().lower(): v for k, v in raw.items()})

        explicit_barcodes = [
            r.get("barcode", "").strip()
            for r in rows
            if r.get("barcode", "").strip()
        ]
        already_in_db = await self._existing_barcodes(explicit_barcodes)

        category_cache: dict[str, uuid.UUID] = {}
        summary = ImportSummary(total_rows=len(rows))

        # We hold the per-row IntegrityError barrier ourselves rather than
        # let the FK / unique constraint blow up the whole transaction.
        for index, row in enumerate(rows):
            line = index + 2  # +1 for 0-index, +1 for header
            try:
                name = (row.get("name") or "").strip()
                if not name:
                    raise ValueError("name is required")

                barcode = (row.get("barcode") or "").strip() or None
                if barcode and barcode in already_in_db:
                    summary.skipped += 1
                    continue
                if not barcode:
                    barcode = str(uuid.uuid4())[:12]

                sale_price = _coerce_decimal(row.get("sale_price"), "sale_price")
                purchase_price_raw = row.get("purchase_price")
                purchase_price = (
                    _coerce_decimal(purchase_price_raw, "purchase_price")
                    if purchase_price_raw and purchase_price_raw.strip()
                    else Decimal("0")
                )
                week_number = _coerce_int(row.get("week_number"), "week_number")
                status = _coerce_status(row.get("status"))

                category_id = await self._resolve_category(
                    row.get("category_id"),
                    row.get("category_name"),
                    category_cache,
                )

                product = Product(
                    barcode=barcode,
                    name=name,
                    category_id=category_id,
                    size=(row.get("size") or "").strip() or None,
                    color=(row.get("color") or "").strip() or None,
                    brand=(row.get("brand") or "").strip() or None,
                    purchase_price=float(purchase_price),
                    sale_price=float(sale_price),
                    status=status,
                    week_number=week_number,
                    description=(row.get("description") or "").strip() or None,
                    condition=(row.get("condition") or "").strip() or None,
                )
                if dry_run:
                    summary.imported += 1
                    continue
                self.db.add(product)
                await self.db.flush()
                summary.imported += 1
                summary.created_ids.append(str(product.id))
                # Reserve the barcode locally so a duplicate inside the
                # same upload doesn't pass the pre-pass check.
                already_in_db.add(barcode)
            except ValueError as exc:
                summary.errors.append(RowError(line=line, message=str(exc)))
            except Exception as exc:
                summary.errors.append(
                    RowError(line=line, message=f"unexpected: {exc}")
                )

        return summary
