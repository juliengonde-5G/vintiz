"""Domain exception hierarchy for Vintiz.

Services raise these instead of HTTPException so they remain decoupled from
the HTTP layer. Routers (and the global exception handler) catch them and
translate to the appropriate HTTP status code.

Usage in a service::

    from app.core.exceptions import ResourceNotFound
    raise ResourceNotFound("Product", product_id)

Usage in a router::

    from app.core.exceptions import ResourceNotFound
    try:
        product = await service.get(...)
    except ResourceNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
"""

from __future__ import annotations


class VintizError(Exception):
    """Base class for all domain exceptions."""


# ---------------------------------------------------------------------------
# Generic CRUD
# ---------------------------------------------------------------------------


class ResourceNotFound(VintizError):
    def __init__(self, resource: str, identifier=None) -> None:
        msg = f"{resource} not found"
        if identifier is not None:
            msg += f": {identifier}"
        super().__init__(msg)
        self.resource = resource
        self.identifier = identifier


class ResourceConflict(VintizError):
    """The operation conflicts with existing state (e.g. duplicate)."""


# ---------------------------------------------------------------------------
# Business rules
# ---------------------------------------------------------------------------


class InvalidState(VintizError):
    """FSM transition is not allowed from the current state."""


class InsufficientBalance(VintizError):
    """Avoir / loyalty credit is too low for the requested amount."""


class InvalidOperation(VintizError):
    """The requested operation is not valid in this context."""


# ---------------------------------------------------------------------------
# POS / transactions
# ---------------------------------------------------------------------------


class CartEmpty(VintizError):
    """A transaction was submitted with no items."""


class PaymentShortfall(VintizError):
    """Total payments are less than total TTC."""

    def __init__(self, paid, total) -> None:
        super().__init__(f"Insufficient payment: {paid} < {total}")
        self.paid = paid
        self.total = total


class ProductNotAvailable(VintizError):
    """Product is not in a sellable status."""

    def __init__(self, name: str, current_status: str) -> None:
        super().__init__(
            f"Product '{name}' is not available for sale (status: {current_status})"
        )


# ---------------------------------------------------------------------------
# Refund
# ---------------------------------------------------------------------------


class RefundError(VintizError):
    """Any error during the refund flow."""


# ---------------------------------------------------------------------------
# Auth / cashier
# ---------------------------------------------------------------------------


class AuthenticationError(VintizError):
    """PIN or credential mismatch."""


class PermissionDenied(VintizError):
    """The caller does not have permission to perform this action."""
