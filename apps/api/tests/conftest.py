import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import engine
from app.main import app
from app.models import Base


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def _create_tables():
    """Create all tables before each test so endpoints have a valid schema.

    The FastAPI lifespan handler does this in production, but ASGITransport
    bypasses lifespan, so we recreate the schema here. Cheap on SQLite.
    Only requested by fixtures that actually need the DB (e.g. ``client``).
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client(_create_tables):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
