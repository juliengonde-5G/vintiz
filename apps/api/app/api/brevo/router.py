"""Webhook public Brevo → Vintiz.

Brevo poste ici les événements de désinscription (clic sur le lien
« se désinscrire » d'un email, opt-out SMS, hard-bounce…). On les
reflète sur le client correspondant (``email_optin = False`` /
``sms_optin = False``) + on trace l'évènement dans le ledger Consent
avec source ``brevo_webhook``.

Authentification : par token partagé (``BREVO_WEBHOOK_TOKEN`` env)
passé en query string ou en header ``X-Brevo-Token``. Configurer la
même valeur côté Brevo (URL du webhook = ``…?token=…``). Sans token
défini → l'endpoint refuse l'événement plutôt que d'accepter une
injection arbitraire.
"""
from __future__ import annotations

import logging
import os
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services import brevo_contacts

router = APIRouter(prefix="/brevo", tags=["brevo"])
_log = logging.getLogger("vintiz.brevo.webhook")


def _check_token(token: str | None, header_token: str | None) -> None:
    expected = (os.getenv("BREVO_WEBHOOK_TOKEN") or "").strip()
    if not expected:
        # Pas de token configuré ⇒ on refuse plutôt que de laisser passer
        # n'importe quoi. La synchro côté Brevo reste possible (push) ; seul
        # le retour webhook est désactivé tant que le token n'est pas posé.
        raise HTTPException(403, "Webhook désactivé — définissez BREVO_WEBHOOK_TOKEN")
    provided = (token or header_token or "").strip()
    if provided != expected:
        raise HTTPException(403, "Token webhook invalide")


@router.post("/webhook")
async def webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    token: str | None = Query(None),
    x_brevo_token: Annotated[str | None, Header(alias="X-Brevo-Token")] = None,
):
    """Reçoit un événement Brevo (JSON) et applique l'opt-out correspondant."""
    _check_token(token, x_brevo_token)
    try:
        payload = await request.json()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"JSON invalide: {exc}") from exc

    # Brevo poste soit un objet, soit une liste (selon le type d'évènement).
    events = payload if isinstance(payload, list) else [payload]
    applied = 0
    skipped = 0
    for evt in events:
        if not isinstance(evt, dict):
            skipped += 1
            continue
        try:
            res = await brevo_contacts.apply_webhook_event(db, evt)
            if res.get("applied"):
                applied += 1
            else:
                skipped += 1
        except Exception as exc:  # noqa: BLE001 — pas d'échec global
            _log.warning("Brevo webhook event failed: %s", exc)
            skipped += 1

    return {"applied": applied, "skipped": skipped, "total": len(events)}
