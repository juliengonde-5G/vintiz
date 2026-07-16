"""Admin bootstrap endpoint (table creation).

Seed and test-data endpoints have been removed: production data is loaded via
manual operations only. The remaining endpoint creates the database schema on a
freshly provisioned environment.
"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, status

from app.core.config import settings
from app.core.database import engine
from app.models.base import Base


router = APIRouter(tags=["admin"])


@router.post("/create-tables")
async def create_tables(
    x_admin_key: str = Header(..., alias="X-Admin-Key"),
):
    """Create all database tables. Protected by a dedicated X-Admin-Key header.

    Reads the expected key from the ADMIN_BOOTSTRAP_KEY environment variable.
    Refuses to run unless ADMIN_BOOTSTRAP_KEY is explicitly set (no longer
    aliases SECRET_KEY, which would have allowed anyone with the JWT signing
    key to forge admin operations).
    """
    if settings.is_production:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Endpoint disabled in production; use Alembic migrations.",
        )
    import hmac
    import os

    expected = os.getenv("ADMIN_BOOTSTRAP_KEY", "") or settings.ADMIN_BOOTSTRAP_KEY
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ADMIN_BOOTSTRAP_KEY is not configured on the server.",
        )
    if not hmac.compare_digest(x_admin_key, expected):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin key",
        )

    # Eager import every model so Base.metadata sees them all.
    import app.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    return {"status": "ok", "message": "All database tables created."}
