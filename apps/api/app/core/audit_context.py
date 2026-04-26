"""Per-request context variable that carries the current user id for audit
purposes.

SQLAlchemy event listeners that write AuditLog rows have no direct access
to the FastAPI request, so the user id is propagated via a contextvars
ContextVar set by the audit middleware (best-effort JWT decode) or, in
tests, by manually calling :func:`set_current_user_id`.
"""

import contextvars
import uuid

current_user_id_var: contextvars.ContextVar[uuid.UUID | None] = contextvars.ContextVar(
    "vintiz_current_user_id", default=None
)


def set_current_user_id(user_id: uuid.UUID | None) -> contextvars.Token:
    """Set the current user id in the per-task context. Returns the reset token."""
    return current_user_id_var.set(user_id)


def get_current_user_id() -> uuid.UUID | None:
    """Return the current user id, or None if no request is in flight."""
    return current_user_id_var.get()


def reset_current_user_id(token: contextvars.Token) -> None:
    current_user_id_var.reset(token)
