"""Markdown engine — declarative rule evaluator (P3-001).

Camille edits ``MarkdownRule`` rows from the admin. The nightly cron
calls ``run_batch`` which:
1. Loads active rules ordered by priority ASC.
2. For every product on the floor, finds the first matching rule.
3. Applies the rule's action via ``ProductLifecycleService.transition``
   so the FSM, the markdown_history ledger and the analytics events
   stay coherent.

Conditions and actions live as JSON so the UI can extend the schema
without touching code; this service is the single validator.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterable

from sqlalchemy import asc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.markdown import MarkdownRule
from app.models.product import Category, Product, ProductStatus
from app.services.product_lifecycle import ProductLifecycleService

logger = logging.getLogger("vintiz.markdown_engine")


VALID_TARGET_STATUSES = {
    "discounted": ProductStatus.discounted,
    "deep_discounted": ProductStatus.deep_discounted,
    "returned_to_sorting": ProductStatus.returned_to_sorting,
    "donated": ProductStatus.donated,
}

# Statuses that the cron is allowed to evaluate. Excludes terminals,
# pre-display work-in-progress states, and anything custom.
_ELIGIBLE_PRODUCT_STATUSES = (
    ProductStatus.display,
    ProductStatus.displayed,
    ProductStatus.discounted,
    ProductStatus.deep_discounted,
)


# ---------------------------------------------------------------------------
# Rule validation + matching
# ---------------------------------------------------------------------------


@dataclass
class RuleEvaluation:
    matched_rule: MarkdownRule | None = None
    new_price: Decimal | None = None
    target_status: ProductStatus | None = None
    reason: str | None = None


@dataclass
class BatchSummary:
    scanned: int = 0
    matched: int = 0
    applied: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    actions: list[dict] = field(default_factory=list)


def _normalize_string_list(raw: Any) -> set[str]:
    if not isinstance(raw, list):
        return set()
    return {str(item).strip().lower() for item in raw if item}


def _matches_conditions(
    product: Product,
    category: Category | None,
    conditions: dict,
    *,
    now: datetime | None = None,
) -> bool:
    """Return True if every supplied condition is satisfied."""
    if not isinstance(conditions, dict):
        return False

    now = now or datetime.now(timezone.utc)

    score = product.trend_score
    if "score_max" in conditions:
        if score is None or score >= float(conditions["score_max"]):
            return False
    if "score_min" in conditions:
        if score is None or score < float(conditions["score_min"]):
            return False

    if "age_min_days" in conditions or "age_max_days" in conditions:
        if product.displayed_at is None:
            return False
        displayed = product.displayed_at
        if displayed.tzinfo is None:
            displayed = displayed.replace(tzinfo=timezone.utc)
        age_days = max(0, (now - displayed).days)
        if "age_min_days" in conditions and age_days < int(conditions["age_min_days"]):
            return False
        if "age_max_days" in conditions and age_days > int(conditions["age_max_days"]):
            return False

    cats = _normalize_string_list(conditions.get("categories"))
    if cats:
        cat_name = (category.name if category else "").lower()
        if cat_name not in cats:
            return False

    brands = _normalize_string_list(conditions.get("brands"))
    if brands:
        brand_name = (product.brand or "").lower()
        if brand_name not in brands:
            return False

    statuses = _normalize_string_list(conditions.get("from_status"))
    if statuses:
        if product.status.value not in statuses:
            return False

    return True


def _validate_action(action: dict) -> tuple[ProductStatus, Decimal | None, str | None]:
    """Validate the action JSON. Returns (target_status, new_price, reason).

    Raises ValueError if the action is malformed; the engine catches and
    logs so a single bad rule can't kill the cron.
    """
    if not isinstance(action, dict):
        raise ValueError("action must be an object")
    target_raw = str(action.get("to_status", "")).strip().lower()
    target = VALID_TARGET_STATUSES.get(target_raw)
    if target is None:
        raise ValueError(
            f"action.to_status must be one of {sorted(VALID_TARGET_STATUSES)}"
        )

    new_price: Decimal | None = None
    if target in (ProductStatus.discounted, ProductStatus.deep_discounted):
        if "discount_pct" not in action:
            raise ValueError(
                "discount_pct is required when to_status is "
                f"{target.value}"
            )
        try:
            pct = float(action["discount_pct"])
        except (TypeError, ValueError) as exc:
            raise ValueError("discount_pct must be a number") from exc
        if not (0 < pct < 100):
            raise ValueError("discount_pct must be in (0, 100)")
        # The actual product price is plugged in by ``apply_to_product``.
    return target, new_price, action.get("reason")


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class MarkdownEngineService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_active_rules(self) -> list[MarkdownRule]:
        result = await self.db.execute(
            select(MarkdownRule)
            .where(MarkdownRule.active.is_(True))
            .order_by(asc(MarkdownRule.priority), asc(MarkdownRule.created_at))
        )
        return list(result.scalars().all())

    async def evaluate_product(
        self,
        product: Product,
        rules: Iterable[MarkdownRule] | None = None,
        *,
        now: datetime | None = None,
    ) -> RuleEvaluation:
        """Find the first rule that matches ``product`` (lowest priority wins)."""
        if rules is None:
            rules = await self.list_active_rules()

        category: Category | None = None
        if product.category_id is not None:
            cat_row = await self.db.execute(
                select(Category).where(Category.id == product.category_id)
            )
            category = cat_row.scalar_one_or_none()

        for rule in rules:
            if not _matches_conditions(product, category, rule.conditions, now=now):
                continue
            try:
                target, _, reason = _validate_action(rule.action)
            except ValueError as exc:
                logger.warning(
                    "markdown_engine: rule %s has invalid action (%s)",
                    rule.id, exc,
                )
                continue

            new_price: Decimal | None = None
            if target in (ProductStatus.discounted, ProductStatus.deep_discounted):
                pct = float(rule.action["discount_pct"])
                current = Decimal(str(product.sale_price))
                new_price = (current * (Decimal("100") - Decimal(str(pct))) / Decimal("100")).quantize(Decimal("0.01"))
                # Don't flag a no-op markdown (price already at the target).
                if new_price >= current:
                    continue
            return RuleEvaluation(
                matched_rule=rule,
                new_price=new_price,
                target_status=target,
                reason=reason or f"Markdown rule: {rule.name}",
            )

        return RuleEvaluation()

    async def apply_to_product(
        self,
        product: Product,
        evaluation: RuleEvaluation,
        *,
        user_id: uuid.UUID | None = None,
    ) -> dict:
        """Apply the matched rule via the lifecycle FSM and return a summary."""
        if evaluation.matched_rule is None or evaluation.target_status is None:
            return {"product_id": str(product.id), "applied": False}

        previous_status = product.status.value
        previous_price = float(product.sale_price)

        await ProductLifecycleService(self.db).transition(
            product,
            evaluation.target_status,
            user_id=user_id,
            reason=evaluation.reason,
            new_price=evaluation.new_price,
        )

        return {
            "product_id": str(product.id),
            "rule_id": str(evaluation.matched_rule.id),
            "rule_name": evaluation.matched_rule.name,
            "from_status": previous_status,
            "to_status": evaluation.target_status.value,
            "from_price": previous_price,
            "to_price": float(product.sale_price),
            "reason": evaluation.reason,
            "applied": True,
        }

    async def run_batch(
        self,
        *,
        dry_run: bool = False,
        user_id: uuid.UUID | None = None,
        now: datetime | None = None,
    ) -> BatchSummary:
        """Walk every eligible product, evaluate against every active rule,
        apply the first match. ``dry_run=True`` reports what would happen
        without mutating any product."""
        rules = await self.list_active_rules()
        summary = BatchSummary()

        if not rules:
            return summary

        result = await self.db.execute(
            select(Product).where(Product.status.in_(_ELIGIBLE_PRODUCT_STATUSES))
        )
        products = list(result.scalars().all())
        summary.scanned = len(products)

        for product in products:
            try:
                evaluation = await self.evaluate_product(
                    product, rules=rules, now=now
                )
            except Exception as exc:  # pragma: no cover — defensive
                summary.errors.append(f"{product.id}: {exc}")
                continue

            if evaluation.matched_rule is None:
                summary.skipped += 1
                continue
            summary.matched += 1

            if dry_run:
                summary.actions.append({
                    "product_id": str(product.id),
                    "product_name": product.name,
                    "rule_id": str(evaluation.matched_rule.id),
                    "rule_name": evaluation.matched_rule.name,
                    "from_status": product.status.value,
                    "to_status": evaluation.target_status.value if evaluation.target_status else None,
                    "from_price": float(product.sale_price),
                    "to_price": float(evaluation.new_price) if evaluation.new_price else None,
                })
                continue

            try:
                action = await self.apply_to_product(
                    product, evaluation, user_id=user_id
                )
                summary.applied += 1
                summary.actions.append(action)
            except Exception as exc:
                summary.errors.append(f"{product.id}: {exc}")

        return summary
