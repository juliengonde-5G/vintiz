"""Tests pour le sandbox SumUp + transitions de statut.

Ces tests évitent toute requête HTTP réelle. Ils exercent :
- Le `SandboxStore` (add / get / list / events / reset)
- Les transitions PENDING → PAID / FAILED / CANCELLED
- L'auto-paid après le délai configuré
- Le refus d'annuler un checkout PAID (cohérence comptable)
- Le rejet d'un poll sur checkout_id inconnu (anti-forgerie)
- Le redact_sumup_error déjà couvert dans test_sumup_redaction.py

`SumUpService.create_checkout` n'est pas testé ici en path production
(httpx out-of-scope) — la sandbox couvre la logique métier.
"""

import time

import pytest

from app.services.sumup_service import (
    SandboxCheckout,
    SandboxEvent,
    SandboxStore,
    SumUpService,
    get_sandbox_store,
)


@pytest.fixture
def store():
    """Reset the module-level singleton between tests."""
    s = get_sandbox_store()
    s.reset()
    yield s
    s.reset()


@pytest.fixture
def service(monkeypatch, store):
    """SumUpService en mode sandbox (pas de clé API)."""
    monkeypatch.delenv("SUMUP_API_KEY", raising=False)
    monkeypatch.setenv("SUMUP_ENVIRONMENT", "sandbox")
    monkeypatch.setenv("SUMUP_SANDBOX_AUTO_DELAY_SEC", "5")
    return SumUpService()


# -- SandboxStore basics -------------------------------------------


def test_store_add_and_get():
    store = SandboxStore()
    co = SandboxCheckout(
        checkout_id="SBX-T1",
        reference="REF-001",
        amount=12.50,
        currency="EUR",
        description="Test",
    )
    store.add(co)
    assert store.get("SBX-T1") is co
    assert store.get("SBX-XXX") is None


def test_store_list_orders_by_created_desc():
    store = SandboxStore()
    a = SandboxCheckout("SBX-A", "REF-A", 10, "EUR", "")
    a.created_at = 1000.0
    b = SandboxCheckout("SBX-B", "REF-B", 20, "EUR", "")
    b.created_at = 2000.0
    store.add(a)
    store.add(b)
    listed = store.list()
    assert listed[0].checkout_id == "SBX-B"  # most recent first
    assert listed[1].checkout_id == "SBX-A"


def test_store_log_and_events_reverse_order():
    store = SandboxStore()
    store.log("create", "SBX-1", "PENDING")
    store.log("approve", "SBX-1", "PAID")
    events = store.events()
    assert len(events) == 2
    assert events[0].kind == "approve"  # newest first
    assert events[1].kind == "create"


def test_store_log_caps_at_max_events():
    store = SandboxStore()
    for i in range(SandboxStore.MAX_EVENTS + 50):
        store.log("poll", f"SBX-{i}", "PENDING")
    assert len(store.events(SandboxStore.MAX_EVENTS + 100)) == SandboxStore.MAX_EVENTS


def test_store_reset_clears_all():
    store = SandboxStore()
    store.add(SandboxCheckout("SBX-X", "REF-X", 10, "EUR", ""))
    store.log("create", "SBX-X", "PENDING")
    store.reset()
    assert store.get("SBX-X") is None
    assert store.events() == []


def test_singleton_returns_same_store():
    a = get_sandbox_store()
    b = get_sandbox_store()
    assert a is b


# -- SandboxCheckout.to_dict ---------------------------------------


def test_checkout_to_dict_includes_all_keys():
    co = SandboxCheckout(
        checkout_id="SBX-1",
        reference="REF-1",
        amount=15.0,
        currency="EUR",
        description="Robe",
    )
    d = co.to_dict()
    for key in (
        "checkout_id",
        "checkout_reference",
        "amount",
        "currency",
        "description",
        "status",
        "created_at",
        "updated_at",
        "auto_approve_in",
        "manual_override",
    ):
        assert key in d


def test_checkout_to_dict_auto_approve_in_calculated():
    co = SandboxCheckout(
        checkout_id="SBX-1",
        reference="REF-1",
        amount=15.0,
        currency="EUR",
        description="",
        auto_approve_at=time.time() + 5,
    )
    d = co.to_dict()
    assert d["auto_approve_in"] is not None
    assert 0 < d["auto_approve_in"] <= 5


def test_checkout_to_dict_auto_approve_none_when_not_pending():
    co = SandboxCheckout(
        checkout_id="SBX-1",
        reference="REF-1",
        amount=15.0,
        currency="EUR",
        description="",
        auto_approve_at=time.time() + 5,
        status="PAID",
    )
    d = co.to_dict()
    assert d["auto_approve_in"] is None


def test_checkout_to_dict_auto_approve_none_after_manual_override():
    co = SandboxCheckout(
        checkout_id="SBX-1",
        reference="REF-1",
        amount=15.0,
        currency="EUR",
        description="",
        auto_approve_at=time.time() + 5,
        manual_override=True,
    )
    d = co.to_dict()
    assert d["auto_approve_in"] is None


# -- SumUpService sandbox transitions ------------------------------


def test_sandbox_approve_sets_paid(service, store):
    co = SandboxCheckout("SBX-A1", "REF", 10, "EUR", "")
    store.add(co)
    out = service.sandbox_approve("SBX-A1")
    assert out["ok"] is True
    assert co.status == "PAID"
    assert co.manual_override is True


def test_sandbox_approve_unknown_returns_error(service):
    out = service.sandbox_approve("SBX-NONEXISTENT")
    assert out["ok"] is False
    assert "unknown" in out["error"].lower()


def test_sandbox_decline_sets_failed(service, store):
    co = SandboxCheckout("SBX-A2", "REF", 10, "EUR", "")
    store.add(co)
    out = service.sandbox_decline("SBX-A2")
    assert out["ok"] is True
    assert co.status == "FAILED"


def test_sandbox_decline_unknown_returns_error(service):
    out = service.sandbox_decline("SBX-NOPE")
    assert out["ok"] is False


# -- Polling unknown / forged ID -----------------------------------


@pytest.mark.anyio
async def test_poll_unknown_sandbox_id_fails(service, monkeypatch):
    """Anti-forgery: un checkout_id arbitraire ne doit pas auto-PAID."""
    out = await service.get_checkout_status("FAKE-IDXYZ")
    assert out["status"] == "FAILED"
    assert "unknown" in out.get("error", "").lower()


@pytest.mark.anyio
async def test_poll_legacy_sim_returns_paid(service):
    """Legacy SIM-* identifiers retain their backward-compat PAID."""
    out = await service.get_checkout_status("SIM-OLDREF")
    assert out["status"] == "PAID"


@pytest.mark.anyio
async def test_poll_unknown_sbx_id_fails(service):
    out = await service.get_checkout_status("SBX-NOPE")
    assert out["status"] == "FAILED"


@pytest.mark.anyio
async def test_poll_pending_returns_pending(service, store):
    co = SandboxCheckout(
        "SBX-P1", "REF", 10, "EUR", "",
        auto_approve_at=time.time() + 100,  # far future, won't trigger
    )
    store.add(co)
    out = await service.get_checkout_status("SBX-P1")
    assert out["status"] == "PENDING"


@pytest.mark.anyio
async def test_poll_auto_transitions_after_delay(service, store):
    """Une fois auto_approve_at dépassé, le poll passe en PAID."""
    co = SandboxCheckout(
        "SBX-P2", "REF", 10, "EUR", "",
        auto_approve_at=time.time() - 1,  # déjà dans le passé
    )
    store.add(co)
    out = await service.get_checkout_status("SBX-P2")
    assert out["status"] == "PAID"
    assert co.status == "PAID"


@pytest.mark.anyio
async def test_poll_does_not_auto_transition_after_manual_override(service, store):
    """Si la cliente a déjà refusé manuellement, l'auto-delay ne ressuscite pas."""
    co = SandboxCheckout(
        "SBX-P3", "REF", 10, "EUR", "",
        auto_approve_at=time.time() - 1,
        status="FAILED",
        manual_override=True,
    )
    store.add(co)
    out = await service.get_checkout_status("SBX-P3")
    assert out["status"] == "FAILED"


# -- Cancel transitions --------------------------------------------


@pytest.mark.anyio
async def test_cancel_pending_succeeds(service, store):
    co = SandboxCheckout("SBX-C1", "REF", 10, "EUR", "")
    store.add(co)
    ok = await service.cancel_checkout("SBX-C1")
    assert ok is True
    assert co.status == "CANCELLED"
    assert co.manual_override is True


@pytest.mark.anyio
async def test_cancel_paid_refused(service, store):
    """Refus de cancel sur un PAID — préserve la cohérence comptable
    (la cliente a payé chez SumUp, pas de divergence à créer)."""
    co = SandboxCheckout("SBX-C2", "REF", 10, "EUR", "", status="PAID")
    store.add(co)
    ok = await service.cancel_checkout("SBX-C2")
    assert ok is False
    assert co.status == "PAID"  # statut préservé


@pytest.mark.anyio
async def test_cancel_unknown_returns_false(service):
    ok = await service.cancel_checkout("SBX-MISSING")
    assert ok is False


@pytest.mark.anyio
async def test_cancel_legacy_sim_returns_true(service):
    """Pour SIM-*, on accepte l'annulation (no-op compat)."""
    ok = await service.cancel_checkout("SIM-LEGACY")
    assert ok is True


# -- Sandbox snapshot ---------------------------------------------


def test_sandbox_snapshot_includes_config_and_events(service, store):
    co = SandboxCheckout("SBX-S1", "REF", 10, "EUR", "")
    store.add(co)
    store.log("create", "SBX-S1", "PENDING")
    snap = service.sandbox_snapshot()
    assert "config" in snap
    assert "checkouts" in snap
    assert "events" in snap
    assert any(c["checkout_id"] == "SBX-S1" for c in snap["checkouts"])


def test_sandbox_clear_resets_store(service, store):
    co = SandboxCheckout("SBX-X", "REF", 10, "EUR", "")
    store.add(co)
    service.sandbox_clear()
    assert store.get("SBX-X") is None


# -- Multi-checkout isolation --------------------------------------


def test_multiple_checkouts_isolated(service, store):
    """Approuver A ne change pas B."""
    a = SandboxCheckout("SBX-A", "REF-A", 10, "EUR", "")
    b = SandboxCheckout("SBX-B", "REF-B", 20, "EUR", "")
    store.add(a)
    store.add(b)
    service.sandbox_approve("SBX-A")
    assert a.status == "PAID"
    assert b.status == "PENDING"
