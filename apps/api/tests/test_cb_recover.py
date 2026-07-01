"""Tests for the CB payment recovery endpoint (renforcement anti-double-débit).

GET /api/pos/payments/cb/recover interroge SumUp par la référence de la vente
(foreign_transaction_id) pour savoir si la carte a déjà été débitée — second
canal de confirmation quand le retour TPE est perdu. Ce test couvre le câblage
(route enregistrée + gate d'authentification) ; le parsing de la réponse SumUp
est un simple mapping de champs.
"""

import pytest


@pytest.mark.anyio
async def test_recover_route_registered(client):
    res = await client.get("/openapi.json")
    assert res.status_code == 200
    paths = res.json()["paths"]
    assert "/api/pos/payments/cb/recover" in paths
    assert "get" in paths["/api/pos/payments/cb/recover"]


@pytest.mark.anyio
async def test_recover_requires_auth(client):
    # Sans jeton, l'endpoint (get_current_user) refuse — jamais 200.
    res = await client.get(
        "/api/pos/payments/cb/recover",
        params={"foreign_transaction_id": "some-sale-uuid"},
    )
    assert res.status_code in (401, 403)
