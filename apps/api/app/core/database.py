from collections.abc import AsyncGenerator
from typing import TypeVar

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")
_engine_kwargs: dict = {"pool_pre_ping": True, "echo": False}
if not _is_sqlite:
    _engine_kwargs["pool_size"] = 20
    _engine_kwargs["max_overflow"] = 10

engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


_M = TypeVar("_M")


async def get_or_404(
    db: AsyncSession,
    model: type[_M],
    pk,
    *,
    detail: str | None = None,
) -> _M:
    """Fetch a row by primary key or raise HTTPException(404).

    Replaces the ~70 occurrences of
    ``select(Model).where(Model.id == pk) → scalar_one_or_none() → raise 404``
    scattered across the routers. The detail message defaults to the model's
    Python class name (so the API surface stays consistent), or can be
    overridden when the user-facing label differs (``"Cliente"``, etc.).
    """
    obj = (await db.execute(select(model).where(model.id == pk))).scalar_one_or_none()
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail or f"{model.__name__} not found",
        )
    return obj
