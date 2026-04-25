"""Shared portable column types.

`JSONType` and `UUIDType` switch between Postgres-specific and generic
implementations so the models can be used against SQLite (tests) as well as
PostgreSQL (production).
"""

from __future__ import annotations

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB, UUID

# Use Postgres JSONB when available; fall back to generic JSON elsewhere.
JSONType = JSON().with_variant(JSONB(), "postgresql")

# UUID stored natively on Postgres; SQLAlchemy emits CHAR(32) on SQLite.
UUIDType = UUID(as_uuid=True)
