"""Product life-cycle service (P1-006).

Centralises every status change so the transitions are validated against
a finite-state machine, the right life-cycle anchor (received_at /
displayed_at) is stamped, and the matching analytics event lands in
``events_log``. The audit log listener (P1-013) still records the row-
level diff for free.

Legal vocabulary used by the audit V1 §2.2.6:

    received → sorted → tagged → displayed →
      ├── sold                (terminal — paid)
      ├── donated             (terminal — commercial gesture)
      ├── returned_to_sorting (terminal — sent back to Solidarité Textiles)
      └── discounted → deep_discounted → returned_to_sorting

Legacy ``stock`` / ``display`` are accepted as transition targets too —
existing callers (POS, seed) keep working.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.events import EventSource, EventType
from app.models.product import Product, ProductStatus
from app.services.events import EventService


# Forward-only finite-state machine. Keep terminal states (sold, donated,
# returned_to_sorting) without outgoing edges so an audit reads cleanly.
_VALID_TRANSITIONS: dict[ProductStatus, set[ProductStatus]] = {
    ProductStatus.received: {
        ProductStatus.sorted,
        ProductStatus.returned_to_sorting,
    },
    ProductStatus.sorted: {
        ProductStatus.tagged,
        ProductStatus.returned_to_sorting,
    },
    ProductStatus.tagged: {
        ProductStatus.displayed,
        ProductStatus.stock,
        ProductStatus.returned_to_sorting,
    },
    ProductStatus.stock: {
        ProductStatus.displayed,
        ProductStatus.display,
        ProductStatus.tagged,
        ProductStatus.returned_to_sorting,
    },
    ProductStatus.display: {
        ProductStatus.displayed,
        ProductStatus.discounted,
        ProductStatus.sold,
        ProductStatus.donated,
        ProductStatus.returned_to_sorting,
        ProductStatus.stock,
    },
    ProductStatus.displayed: {
        ProductStatus.discounted,
        ProductStatus.sold,
        ProductStatus.donated,
        ProductStatus.returned_to_sorting,
        ProductStatus.stock,
    },
    ProductStatus.discounted: {
        ProductStatus.deep_discounted,
        ProductStatus.sold,
        ProductStatus.donated,
        ProductStatus.returned_to_sorting,
    },
    ProductStatus.deep_discounted: {
        ProductStatus.sold,
        ProductStatus.donated,
        ProductStatus.returned_to_sorting,
    },
    # Legacy 'returned' was a catch-all; allow rebooking it onto the
    # new flow so historical rows can be cleaned up.
    ProductStatus.returned: {
        ProductStatus.sorted,
        ProductStatus.returned_to_sorting,
    },
    # Terminal states have no outgoing edges.
    ProductStatus.sold: set(),
    ProductStatus.donated: set(),
    ProductStatus.returned_to_sorting: set(),
}

TERMINAL_STATES = {
    ProductStatus.sold,
    ProductStatus.donated,
    ProductStatus.returned_to_sorting,
    ProductStatus.rejected,
}

# Map a destination state to the analytics event we emit (when applicable).
_TRANSITION_EVENT: dict[ProductStatus, EventType] = {
    ProductStatus.donated: EventType.product_donated,
    ProductStatus.returned_to_sorting: EventType.product_returned_to_sorting,
    ProductStatus.discounted: EventType.product_markdown_applied,
    ProductStatus.deep_discounted: EventType.product_markdown_applied,
    # 'sold' is already emitted by the POS create_transaction flow.
}


class ProductLifecycleService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def is_valid_transition(
        current: ProductStatus, target: ProductStatus
    ) -> bool:
        if current == target:
            return True
        return target in _VALID_TRANSITIONS.get(current, set())

    async def transition(
        self,
        product: Product,
        target: ProductStatus,
        *,
        user_id=None,
        reason: str | None = None,
        new_price: Decimal | float | None = None,
        record_location: bool = True,
        move_source: str = "lifecycle",
    ) -> Product:
        """Move ``product`` to ``target`` after validating the FSM edge.

        For markdowns (``discounted`` / ``deep_discounted``) callers can
        supply ``new_price``; the service then appends a row to
        ``markdown_history`` so the price ledger stays auditable.

        Unless ``record_location=False``, the status change is also historised
        in ``product_location_events`` (réserve↔rayon = flux vertical, sorties).
        ``move_product`` sets it to ``False`` to write a single combined event
        when a piece is moved between réserve and a specific zone at once.
        """
        current = product.status
        if not self.is_valid_transition(current, target):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid transition: {current.value} → {target.value}. "
                    f"Allowed targets from {current.value}: "
                    f"{sorted(s.value for s in _VALID_TRANSITIONS.get(current, set()))}"
                ),
            )

        now = datetime.now(timezone.utc)

        # Stamp life-cycle anchors when the matching state is entered for
        # the first time.
        if target == ProductStatus.received and product.received_at is None:
            product.received_at = now
        if (
            target in {ProductStatus.displayed, ProductStatus.display}
            and product.displayed_at is None
        ):
            product.displayed_at = now

        # Markdown bookkeeping.
        if target in {ProductStatus.discounted, ProductStatus.deep_discounted}:
            if new_price is None:
                raise HTTPException(
                    status_code=400,
                    detail="A markdown transition requires `new_price`",
                )
            from_price = float(product.sale_price)
            to_price = float(new_price)
            if to_price >= from_price:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Markdown new_price ({to_price}) must be strictly "
                        f"lower than current sale_price ({from_price})"
                    ),
                )
            history = list(product.markdown_history or [])
            history.append({
                "at": now.isoformat(),
                "from_price": from_price,
                "to_price": to_price,
                "reason": reason,
                "to_status": target.value,
            })
            product.markdown_history = history
            product.sale_price = to_price

        product.status = target
        await self.db.flush()

        # Emit analytics event (best effort — EventService swallows errors).
        event_type = _TRANSITION_EVENT.get(target)
        if event_type is not None:
            meta: dict = {"reason": reason, "from_status": current.value}
            if event_type == EventType.product_markdown_applied:
                # last entry in history has the from_price/to_price/at
                last = (product.markdown_history or [])[-1]
                meta.update({
                    "from_price": last["from_price"],
                    "to_price": last["to_price"],
                })
            await EventService(self.db).emit(
                event_type,
                source=EventSource.admin,
                product_id=product.id,
                user_id=user_id,
                meta=meta,
            )

        # Historise the physical relocation (vertical flow / exits). Zone is
        # untouched by a pure status transition, so from_zone == to_zone.
        if record_location and current != target:
            from app.services.stock_movement import record_move

            await record_move(
                self.db,
                product,
                from_status=current,
                to_status=target,
                from_zone_id=product.zone_id,
                to_zone_id=product.zone_id,
                user_id=user_id,
                reason=reason,
                source=move_source,
            )

        return product
