import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.anyio
@pytest.mark.parametrize("path", ["/api/v1/health", "/api/health"])
async def test_health_check(path):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(path)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data
