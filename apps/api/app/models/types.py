"""Shared portable column types.

`JSONType` and `UUIDType` switch between Postgres-specific and generic
implementations so the models can be used against SQLite (tests) as well as
PostgreSQL (production). `vector_type` returns a Vector column on Postgres
(pgvector) and a JSON-encoded list of floats on SQLite.
"""

from __future__ import annotations

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.types import TypeDecorator

# Use Postgres JSONB when available; fall back to generic JSON elsewhere.
JSONType = JSON().with_variant(JSONB(), "postgresql")

# UUID stored natively on Postgres; SQLAlchemy emits CHAR(32) on SQLite.
UUIDType = UUID(as_uuid=True)


def vector_type(dim: int) -> TypeDecorator:
    """Return a portable column type holding a fixed-length vector of floats.

    On PostgreSQL the column uses pgvector's native ``Vector(dim)`` (so
    HNSW / IVF indexes and the ``<->`` cosine operator work). On SQLite
    (tests) we serialise to JSON, which is enough for the unit tests.
    The Python value is always ``list[float]`` so service code stays
    portable.
    """
    from pgvector.sqlalchemy import Vector  # local import: optional dep

    return Vector(dim).with_variant(JSON(), "sqlite")
