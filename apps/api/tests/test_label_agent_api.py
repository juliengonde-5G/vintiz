"""HTTP tests for the Raspberry Pi agent endpoints + manager auth gate.

The agent endpoints authenticate with the shared ``X-Agent-Token`` header
(no JWT), so the full claim → ack roundtrip is testable end to end.
"""

from __future__ import annotations

import base64
import uuid

import pytest

from app.core.config import settings
from app.core.database import async_session
from app.models.label_job import LabelJobStatus, LabelPrintJob


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def _seed_pending_job(**overrides) -> uuid.UUID:
    async with async_session() as s:
        job = LabelPrintJob(
            job_type="product",
            product_id=None,
            copies=overrides.get("copies", 2),
            status=LabelJobStatus.pending.value,
            payload=overrides.get(
                "payload",
                {"ref": "VTZ-2026-00142", "name": "Robe noire", "week_label": "Semaine 20"},
            ),
        )
        s.add(job)
        await s.commit()
        return job.id


@pytest.mark.anyio
async def test_agent_next_503_when_token_unset(client, monkeypatch):
    monkeypatch.setattr(settings, "RPI_AGENT_TOKEN", "")
    res = await client.get("/api/labels/agent/jobs/next")
    assert res.status_code == 503


@pytest.mark.anyio
async def test_agent_next_401_with_wrong_token(client, monkeypatch):
    monkeypatch.setattr(settings, "RPI_AGENT_TOKEN", "secret-token")
    res = await client.get(
        "/api/labels/agent/jobs/next", headers={"X-Agent-Token": "nope"}
    )
    assert res.status_code == 401


@pytest.mark.anyio
async def test_agent_claim_then_ack_roundtrip(client, monkeypatch):
    monkeypatch.setattr(settings, "RPI_AGENT_TOKEN", "secret-token")
    job_id = await _seed_pending_job(copies=2)

    res = await client.get(
        "/api/labels/agent/jobs/next?max=5",
        headers={"X-Agent-Token": "secret-token"},
    )
    assert res.status_code == 200
    jobs = res.json()["jobs"]
    mine = [j for j in jobs if j["id"] == str(job_id)]
    assert len(mine) == 1
    job = mine[0]
    assert job["copies"] == 2
    assert job["format"] == "pdf"
    assert job["ref"] == "VTZ-2026-00142"
    # The carried content is a real, decodable PDF.
    pdf = base64.b64decode(job["content_b64"])
    assert pdf[:5] == b"%PDF-"

    ack = await client.post(
        f"/api/labels/agent/jobs/{job_id}/ack",
        json={"success": True},
        headers={"X-Agent-Token": "secret-token"},
    )
    assert ack.status_code == 200
    assert ack.json()["status"] == LabelJobStatus.done.value

    # The job is persisted as done.
    async with async_session() as s:
        row = await s.get(LabelPrintJob, job_id)
        assert row.status == LabelJobStatus.done.value


@pytest.mark.anyio
async def test_agent_ack_unknown_job_404(client, monkeypatch):
    monkeypatch.setattr(settings, "RPI_AGENT_TOKEN", "secret-token")
    res = await client.post(
        f"/api/labels/agent/jobs/{uuid.uuid4()}/ack",
        json={"success": True},
        headers={"X-Agent-Token": "secret-token"},
    )
    assert res.status_code == 404


@pytest.mark.anyio
async def test_manager_label_endpoints_require_auth(client):
    pid = uuid.uuid4()
    assert (await client.get(f"/api/labels/preview/{pid}")).status_code == 401
    assert (await client.post(f"/api/labels/print/{pid}")).status_code == 401
    assert (await client.get("/api/labels/printer/status")).status_code == 401


@pytest.mark.anyio
async def test_label_routes_registered():
    from app.main import app

    paths = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/api/labels/agent/jobs/next" in paths
    assert "/api/labels/agent/jobs/{job_id}/ack" in paths
    assert "/api/labels/print/{product_id}" in paths
