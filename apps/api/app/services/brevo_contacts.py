"""Synchronisation des clients Vintiz vers Brevo Contacts.

Vintiz tient déjà ses propres consents RGPD (Client.email_optin /
Client.sms_optin + table Consent pour la traçabilité). Brevo, lui, sert
de plateforme d'envoi (campagnes, automations, transactional). Cette
synchro garde les **deux côtés alignés** :

* nom / prénom / email / téléphone côté Brevo en miroir de Vintiz ;
* opt-in email / SMS poussés en attributs personnalisés Brevo ;
* l'absence de consent retire le contact des listes marketing (ajout à
  la blocklist Brevo) — bouton « ne plus recevoir » sur l'espace client
  ⇒ contact bloqué chez Brevo sans intervention manuelle ;
* le client réactive un consent ⇒ le contact est de nouveau autorisé.

Volontairement minimal côté Brevo : pas de gestion de listes nommées
(juste ``BREVO_LIST_EMAIL`` et ``BREVO_LIST_SMS`` optionnels). La
synchronisation INVERSE (Brevo → Vintiz) est gérée via les webhooks
``/api/brevo/webhook`` qui captent les opt-out depuis les liens email
Brevo (lien de désinscription cliqué hors site).

Le module ne raise PAS sur une erreur Brevo : il logge et continue.
La source de vérité reste la base Vintiz — Brevo est une copie poussée
en best-effort.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client

_log = logging.getLogger("vintiz.brevo.contacts")

_API_BASE = "https://api.brevo.com/v3"
_TIMEOUT = 15


def _api_key() -> str | None:
    return os.getenv("BREVO_API_KEY", "").strip() or None


def _headers(api_key: str) -> dict:
    return {
        "accept": "application/json",
        "content-type": "application/json",
        "api-key": api_key,
    }


def _email_list_ids() -> list[int]:
    raw = os.getenv("BREVO_LIST_EMAIL", "").strip()
    return [int(x) for x in raw.split(",") if x.strip().isdigit()] if raw else []


def _sms_list_ids() -> list[int]:
    raw = os.getenv("BREVO_LIST_SMS", "").strip()
    return [int(x) for x in raw.split(",") if x.strip().isdigit()] if raw else []


def _normalize_phone_e164(raw: str | None) -> str | None:
    """Renvoie le téléphone au format E.164 ou None s'il n'est pas exploitable.

    Brevo exige E.164 pour le SMS (``+33612345678``) ; un numéro français
    saisi en local (``06 12 34 56 78``) est converti, les autres formats
    déjà normalisés sont conservés tels quels. Pas de validation exhaustive
    — le but est juste de pousser un format que Brevo accepte sans
    rejeter le contact entier.
    """
    if not raw:
        return None
    digits = "".join(c for c in raw if c.isdigit() or c == "+")
    if not digits:
        return None
    if digits.startswith("+"):
        return digits
    if digits.startswith("00"):
        return "+" + digits[2:]
    # FR local : 0XXXXXXXXX → +33XXXXXXXXX
    if digits.startswith("0") and len(digits) == 10:
        return "+33" + digits[1:]
    return None


@dataclass
class SyncResult:
    ok: bool
    status_code: int | None = None
    detail: str = ""


def _call(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    api_key = _api_key()
    if not api_key:
        raise RuntimeError("BREVO_API_KEY not set")
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = Request(
        f"{_API_BASE}{path}",
        data=data,
        headers=_headers(api_key),
        method=method,
    )
    try:
        with urlopen(req, timeout=_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8", errors="replace") or "{}"
            try:
                return resp.getcode(), json.loads(raw)
            except json.JSONDecodeError:
                return resp.getcode(), {"raw": raw}
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")[:500]
        try:
            return exc.code, json.loads(raw or "{}")
        except json.JSONDecodeError:
            return exc.code, {"raw": raw}
    except URLError as exc:
        raise RuntimeError(f"Brevo network error: {exc.reason}") from exc


# ---------------------------------------------------------------------------
# Mapping Client → payload Brevo
# ---------------------------------------------------------------------------

def _contact_payload(client: Client) -> dict:
    attributes: dict = {
        "PRENOM": (client.first_name or "").strip(),
        "NOM": (client.last_name or "").strip(),
        # Attributs custom Vintiz — créables côté Brevo dans Contacts > Attributs.
        # Le sync les pousse même s'ils n'existent pas ; Brevo ignore alors
        # ceux non déclarés (= no-op silencieux). À déclarer chez Brevo pour
        # les utiliser dans les segments / campagnes.
        "EMAIL_OPTIN": bool(client.email_optin),
        "SMS_OPTIN": bool(client.sms_optin),
        "VINTIZ_CLIENT_ID": str(client.id),
    }
    phone = _normalize_phone_e164(client.phone)
    if phone:
        attributes["SMS"] = phone
    # Listes : on n'ajoute le contact à une liste marketing que s'il a
    # explicitement opt-in pour le canal correspondant.
    list_ids = []
    unlink_list_ids = []
    for lst in _email_list_ids():
        (list_ids if client.email_optin else unlink_list_ids).append(lst)
    for lst in _sms_list_ids():
        (list_ids if client.sms_optin else unlink_list_ids).append(lst)

    payload: dict = {
        "email": (client.email or "").strip().lower(),
        "attributes": attributes,
        "updateEnabled": True,  # upsert
        # Brevo emailBlacklisted = bloque tous les emails marketing ;
        # smsBlacklisted = idem SMS. C'est exactement notre opt-out.
        "emailBlacklisted": not bool(client.email_optin),
        "smsBlacklisted": not bool(client.sms_optin),
    }
    if list_ids:
        payload["listIds"] = list_ids
    if unlink_list_ids:
        payload["unlinkListIds"] = unlink_list_ids
    return payload


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------

def push_client(client: Client) -> SyncResult:
    """Pousse (upsert) un client vers Brevo. No-op si pas d'email ou pas de clé.

    Le contact est identifié par son adresse email côté Brevo. Sans email
    on ne peut pas créer de fiche : on skip silencieusement plutôt que
    d'échouer (un client peut être enregistré au POS avec seulement un
    téléphone).
    """
    if not _api_key():
        return SyncResult(ok=False, detail="BREVO_API_KEY not set")
    if not (client.email or "").strip():
        return SyncResult(ok=False, detail="client sans email — skip")

    payload = _contact_payload(client)
    try:
        # POST /contacts crée OU met à jour (updateEnabled=true). 201 = créé,
        # 204 = mis à jour, 400 = email invalide. On considère tous les 2xx
        # comme succès.
        status, body = _call("POST", "/contacts", payload)
        if 200 <= status < 300:
            return SyncResult(ok=True, status_code=status)
        _log.warning(
            "Brevo push client %s → HTTP %d: %s",
            client.email, status, str(body)[:200],
        )
        return SyncResult(ok=False, status_code=status, detail=str(body)[:200])
    except Exception as exc:  # noqa: BLE001
        _log.warning("Brevo push client %s failed: %s", client.email, exc)
        return SyncResult(ok=False, detail=str(exc)[:200])


def delete_client_email(email: str) -> SyncResult:
    """Supprime un contact de Brevo (RGPD : demande de suppression côté Vintiz)."""
    if not _api_key():
        return SyncResult(ok=False, detail="BREVO_API_KEY not set")
    if not email:
        return SyncResult(ok=False, detail="email vide")
    try:
        status, body = _call("DELETE", f"/contacts/{email}")
        if 200 <= status < 300 or status == 404:
            return SyncResult(ok=True, status_code=status)
        return SyncResult(ok=False, status_code=status, detail=str(body)[:200])
    except Exception as exc:  # noqa: BLE001
        return SyncResult(ok=False, detail=str(exc)[:200])


async def push_all_clients(db: AsyncSession, *, only_optin: bool = False) -> dict:
    """Synchronise tous les clients Vintiz vers Brevo. Renvoie un récap.

    Filtres :
    * skip les clients sans email (Brevo ne sait pas les indexer sans) ;
    * skip les clients soft-deleted (``deletion_requested_at`` non NULL) ;
    * ``only_optin=True`` ne pousse que les opt-in email OU SMS.
    """
    if not _api_key():
        return {"ok": False, "error": "BREVO_API_KEY not set", "synced": 0}
    rows = await db.execute(
        select(Client).where(
            Client.email.is_not(None),
            Client.deletion_requested_at.is_(None),
        )
    )
    clients = rows.scalars().all()
    synced, failed, skipped = 0, 0, 0
    for c in clients:
        if only_optin and not (c.email_optin or c.sms_optin):
            skipped += 1
            continue
        res = push_client(c)
        if res.ok:
            synced += 1
        else:
            failed += 1
    return {
        "ok": True,
        "total": len(clients),
        "synced": synced,
        "failed": failed,
        "skipped": skipped,
    }


# ---------------------------------------------------------------------------
# Webhook inverse : Brevo → Vintiz
# ---------------------------------------------------------------------------

async def apply_webhook_event(db: AsyncSession, payload: dict) -> dict:
    """Applique un événement webhook Brevo sur le client correspondant.

    Brevo poste un JSON pour chaque événement (cf. ``Marketing API >
    Webhooks``). On gère ici les seuls événements qui changent l'état
    consent :

    * ``unsubscribed`` (email) → ``client.email_optin = False``
    * ``hard_bounce`` → idem (l'adresse est invalide, plus de marketing)
    * ``sms_marketing_unsubscribed`` → ``client.sms_optin = False``

    Tout autre événement (open, click, delivered…) est ignoré
    silencieusement — Brevo gère lui-même son tracking.
    """
    event = (payload.get("event") or payload.get("type") or "").strip().lower()
    email = (payload.get("email") or "").strip().lower()
    if not email:
        return {"applied": False, "reason": "no email"}

    res = await db.execute(select(Client).where(Client.email == email))
    client = res.scalar_one_or_none()
    if client is None:
        return {"applied": False, "reason": "client not found"}

    changed = False
    if event in {"unsubscribed", "unsubscribe", "hard_bounce", "spam"}:
        if client.email_optin:
            client.email_optin = False
            changed = True
    elif event in {"sms_marketing_unsubscribed", "sms_unsubscribe"}:
        if client.sms_optin:
            client.sms_optin = False
            changed = True

    if changed:
        await db.flush()
        # On enregistre aussi le retrait dans la table Consent pour la
        # traçabilité RGPD (source = "brevo_webhook").
        from app.models.client import Consent, ConsentPurpose
        purpose = (
            ConsentPurpose.email_marketing
            if event in {"unsubscribed", "unsubscribe", "hard_bounce", "spam"}
            else ConsentPurpose.sms_marketing
        )
        db.add(Consent(
            client_id=client.id,
            purpose=purpose,
            granted=False,
            policy_version="brevo-webhook-v1",
            source="brevo_webhook",
        ))
        await db.flush()
    return {"applied": changed, "event": event, "client_id": str(client.id)}
