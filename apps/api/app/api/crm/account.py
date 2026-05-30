"""Public ``/account/*`` endpoints for the magic-link client space.

Extracted from the monolithic ``crm/router.py`` (Sprint 3 #12) so each
sub-domain owns its endpoints. The mounting URL prefix (``/api/crm``) is
kept by the parent router; this sub-router declares no prefix so existing
URLs stay byte-identical.

Boundaries:
- All endpoints here are PUBLIC (no auth header required).
- Most accept ``email`` either as a query param or in the body and
  resolve the client via ``_resolve_public_client``.
- The wallet endpoints serve binary payloads (signed Apple .pkpass,
  Google JWT URL, QR PNG); they're co-located here because they all
  go through the same magic-link space.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.client import (
    Client,
    Consent,
    ConsentPurpose,
    LoyaltyAccount,
)
from app.models.pos import Transaction

logger = logging.getLogger("vintiz")

router = APIRouter(tags=["crm"])


class AccountActionRequest(BaseModel):
    email: str

class PersonalShopperToggleRequest(BaseModel):
    email: str
    enabled: bool
    # Trace explicite du contexte du consentement RGPD (art. 7-1 RGPD :
    # le responsable de traitement doit pouvoir démontrer que le
    # consentement a été donné). `source` est journalisé tel quel dans
    # `consents.source`. Valeurs typiques :
    #   - "site_ps_consent_screen_grant"   (écran consent /account/shopper, accepté)
    #   - "site_ps_consent_screen_decline" (écran consent /account/shopper, refusé)
    #   - "site_account_settings"          (toggle depuis /account/rgpd)
    #   - "account_self_service"           (legacy, valeur par défaut)
    source: str | None = None

class PersonalShopperSearchRequest(BaseModel):
    email: str
    q: str

_CONSENT_LABELS = {
    ConsentPurpose.email_marketing: "Newsletter Vintiz",
    ConsentPurpose.sms_marketing: "SMS commerciaux",
    ConsentPurpose.profiling: "Profilage Personal Shopper",
    ConsentPurpose.trend_alerts: "Alertes nouveautés tendance",
    ConsentPurpose.data_sharing: "Partage de données B2B",
}

class ConsentToggleRequest(BaseModel):
    email: str
    granted: bool

class OnboardingRequest(BaseModel):
    """Layered onboarding payload (PS 360 V1).

    Every field is optional so a customer can submit any subset of layers —
    L1 alone (genre/âge), L2 alone (visual likes), L3 alone (détaillé), or a
    full pass. Invalid enum values are rejected with 422 by the ``Literal``s.
    """

    # Layer 1 — déclaratif (obligatoire côté UI, tolérant côté API).
    gender: Literal["femme", "homme", "mixte"] | None = None
    age_band: Literal["<25", "25-34", "35-44", "45-54", "55+"] | None = None
    # Layer 2 — cold-start visuel : ids des pièces "j'aime".
    liked_product_ids: list[str] = []
    # Layer 3 — détaillé (facultatif).
    liked_style_keys: list[str] = []
    preferred_occasions: list[str] = []
    preferred_price_buckets: list[str] = []
    preferred_categories: list[str] = []
    preferred_brands: list[str] = []

class PublicOnboardingRequest(OnboardingRequest):
    email: str

class LoyaltySubscribeRequest(BaseModel):
    """Self-service loyalty subscription from the espace client (#3).

    The client already exists (magic-link login resolved a Client row), so we
    only need the email + the RGPD opt-ins. Name fields are optional overrides
    used only if the stored client somehow has none."""
    email: str
    optin_newsletter: bool = False
    optin_profiling: bool = False
    optin_sms: bool = False
    first_name: str | None = None
    last_name: str | None = None

class AccountRegisterRequest(BaseModel):
    """Self-service account creation from the public site.

    Privacy by design: the endpoint always responds 200 ("check your email")
    and never reveals whether the email already existed. A new Client row is
    created when needed; in all cases a magic-link (code + clickable link) is
    sent so the visitor proves ownership of the address before the session is
    granted. No password is ever stored.
    """
    email: str
    first_name: str | None = None
    last_name: str | None = None
    optin_newsletter: bool = False
    optin_sms: bool = False



def _normalize_email(value: str) -> str:
    cleaned = value.strip().lower()
    if "@" not in cleaned or "." not in cleaned.split("@", 1)[-1]:
        raise HTTPException(status_code=400, detail="Adresse email invalide")
    return cleaned

async def _resolve_public_client(db: AsyncSession, email: str) -> Client:
    cleaned = _normalize_email(email)
    row = await db.execute(select(Client).where(Client.email == cleaned))
    client = row.scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=404, detail="Aucun compte trouvé")
    return client

async def _record_consent_toggle(
    db: AsyncSession,
    client: Client,
    purpose: ConsentPurpose,
    granted: bool,
    source: str | None = None,
) -> None:
    db.add(
        Consent(
            client_id=client.id,
            purpose=purpose,
            granted=granted,
            policy_version="v2-2026-04",
            source=source or "account_self_service",
        )
    )
    await db.flush()

@router.post("/account/register", status_code=202)
async def public_account_register(
    request: AccountRegisterRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Create a client account from the public site (self-service).

    Always returns 202 with the same body — never discloses whether the email
    already existed (anti-enumeration, like magic-link/request). Flow:

    1. Normalise the email; create a ``Client`` if none exists (no duplicate).
    2. Record the RGPD opt-ins the visitor checked (newsletter / SMS).
    3. Issue a magic-link (6-digit code + clickable link) so the visitor
       confirms ownership and lands logged-in — no password, no code to type
       if they use the link.
    """
    from app.services.magic_link import issue

    cleaned = _normalize_email(request.email)
    row = await db.execute(select(Client).where(Client.email == cleaned))
    client = row.scalar_one_or_none()
    created = False
    if client is None:
        client = Client(
            first_name=(request.first_name or "").strip() or "Cliente",
            last_name=(request.last_name or "").strip() or "Vintiz",
            email=cleaned,
            email_optin=request.optin_newsletter,
            sms_optin=request.optin_sms,
        )
        db.add(client)
        await db.flush()
        created = True
        # RGPD consent ledger for the boxes ticked at sign-up.
        if request.optin_newsletter:
            await _record_consent_toggle(
                db, client, ConsentPurpose.email_marketing, True,
                source="site_self_register",
            )
        if request.optin_sms:
            await _record_consent_toggle(
                db, client, ConsentPurpose.sms_marketing, True,
                source="site_self_register",
            )

    # Send the magic-link in all cases (new account OR existing email →
    # effectively a login), so the response never leaks which path ran.
    client_ip = http_request.client.host if http_request.client else None
    await issue(db, cleaned, ip=client_ip)
    await db.commit()

    logger.info("account self-register: email processed (created=%s)", created)
    return {
        "status": "ok",
        "message": (
            "Compte prêt. Vérifiez votre email : cliquez sur le lien de "
            "connexion (ou saisissez le code) pour accéder à votre espace."
        ),
    }

@router.get("/account/data-export")
async def public_account_data_export(
    email: str = Query(..., min_length=5, max_length=255),
    db: AsyncSession = Depends(get_db),
):
    """Public RGPD data export (Article 20 portability) by email lookup.

    Returns the JSON portable snapshot directly. The audit logger records the
    request via the SQLAlchemy listener; a future iteration will replace this
    with a magic-link confirmation flow to prevent email enumeration leakage.
    """
    from app.services.rgpd import RgpdService

    cleaned = _normalize_email(email)
    result = await db.execute(select(Client).where(Client.email == cleaned))
    client = result.scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=404, detail="Aucun compte trouvé")
    return await RgpdService(db).export_client_data(client)

@router.post("/account/deletion-request")
async def public_account_deletion_request(
    request: AccountActionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Public RGPD deletion request (Article 17 erasure) by email lookup.

    Stamps the soft-delete timestamp; the daily cron purges past 30 days.
    The customer can cancel by re-submitting via the same flow within the
    window (a future iteration will surface a "cancel" button on the site).
    """
    from app.services.rgpd import RgpdService

    cleaned = _normalize_email(request.email)
    result = await db.execute(select(Client).where(Client.email == cleaned))
    client = result.scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=404, detail="Aucun compte trouvé")

    if client.deletion_requested_at is not None:
        return {
            "client_email": cleaned,
            "deletion_requested_at": client.deletion_requested_at.isoformat(),
            "purge_after": (
                client.deletion_requested_at + timedelta(days=30)
            ).isoformat(),
            "already_pending": True,
        }
    requested_at = await RgpdService(db).request_deletion(client)
    await db.commit()
    return {
        "client_email": cleaned,
        "deletion_requested_at": requested_at.isoformat(),
        "purge_after": (requested_at + timedelta(days=30)).isoformat(),
        "already_pending": False,
    }

@router.post("/account/deletion-cancel")
async def public_account_deletion_cancel(
    request: AccountActionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Public cancellation of a pending deletion request (within the 30-day window)."""
    from app.services.rgpd import RgpdService

    cleaned = _normalize_email(request.email)
    result = await db.execute(select(Client).where(Client.email == cleaned))
    client = result.scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=404, detail="Aucun compte trouvé")
    if client.deletion_requested_at is None:
        return {"client_email": cleaned, "deletion_cancelled": True, "was_pending": False}
    await RgpdService(db).cancel_deletion(client)
    await db.commit()
    return {"client_email": cleaned, "deletion_cancelled": True, "was_pending": True}

@router.post("/account/personal-shopper/toggle")
async def toggle_personal_shopper(
    payload: PersonalShopperToggleRequest,
    db: AsyncSession = Depends(get_db),
):
    """Append a ``profiling`` consent row from the client space.

    Public endpoint (no JWT yet — magic-link cookie comes in PR3).
    Returns 204 on success even if the toggle is a no-op (idempotent
    UX); the underlying consent ledger keeps the full history.
    """
    from fastapi import Response

    client = await _resolve_public_client(db, payload.email)
    await _record_consent_toggle(
        db,
        client,
        ConsentPurpose.profiling,
        payload.enabled,
        source=payload.source,
    )
    await db.commit()
    return Response(status_code=204)

@router.post("/account/trend-alerts/toggle")
async def toggle_trend_alerts(
    payload: PersonalShopperToggleRequest,
    db: AsyncSession = Depends(get_db),
):
    """Subscribe / unsubscribe from the trend product alerts (PR2)."""
    from fastapi import Response

    client = await _resolve_public_client(db, payload.email)
    await _record_consent_toggle(
        db,
        client,
        ConsentPurpose.trend_alerts,
        payload.enabled,
        source=payload.source,
    )
    await db.commit()
    return Response(status_code=204)

@router.post("/account/personal-shopper/search")
async def personal_shopper_search(
    payload: PersonalShopperSearchRequest,
    db: AsyncSession = Depends(get_db),
):
    """Free-text search of the live inventory (PR2 sémantique).

    Gated like the rest of the Personal Shopper: the client must be
    a loyalty member with profiling consent granted.
    """
    from app.services.loyalty import loyalty_active
    from app.services.personal_shopper_search import search

    client = await _resolve_public_client(db, payload.email)
    if not loyalty_active(client):
        raise HTTPException(status_code=403, detail="loyalty_required")

    consent_row = await db.execute(
        select(Consent)
        .where(
            Consent.client_id == client.id,
            Consent.purpose == ConsentPurpose.profiling,
        )
        .order_by(Consent.created_at.desc())
        .limit(1)
    )
    consent = consent_row.scalar_one_or_none()
    if consent is None or not consent.granted:
        raise HTTPException(status_code=403, detail="profiling_consent_required")

    return await search(db, payload.q)

@router.get("/account/personal-shopper/live")
async def personal_shopper_live(
    email: str = Query(..., min_length=5, max_length=255),
    top_n: int = 8,
    db: AsyncSession = Depends(get_db),
):
    """Live recommendation feed for the espace client (gated).

    Mirrors :func:`public_personal_shopper_v2` but returns the bare
    products payload the public site renders without the Claude
    narrative — the narrative is a manager-side concern.
    """
    from app.services.personal_shopper import (
        PersonalShopperGatedError,
        PersonalShopperService,
    )

    client = await _resolve_public_client(db, email)
    try:
        result = await PersonalShopperService(db).recommend(
            client.id, top_n=max(1, min(top_n, 10))
        )
    except PersonalShopperGatedError as exc:
        raise HTTPException(status_code=403, detail=exc.reason)
    await db.commit()
    return result

@router.get("/account/coupons")
async def public_account_coupons(
    email: str = Query(..., min_length=5, max_length=255),
    db: AsyncSession = Depends(get_db),
):
    """List active coupons attached to the customer (PR3 espace client)."""
    from app.models.coupon import Coupon

    client = await _resolve_public_client(db, email)
    rows = await db.execute(
        select(Coupon)
        .where(
            Coupon.client_id == client.id,
            Coupon.is_active.is_(True),
            Coupon.redeemed_at.is_(None),
        )
        .order_by(Coupon.valid_until.asc())
    )
    coupons = rows.scalars().all()
    now = datetime.now(timezone.utc)

    def _is_expired(valid_until):
        if valid_until is None:
            return False
        # SQLite drops tzinfo — treat naive datetimes as UTC.
        if valid_until.tzinfo is None:
            valid_until = valid_until.replace(tzinfo=timezone.utc)
        return valid_until < now

    return [
        {
            "code": c.code,
            "discount_type": c.discount_type.value,
            "discount_value": float(c.discount_value or 0),
            "source": c.source.value if c.source else None,
            "valid_from": c.valid_from.isoformat() if c.valid_from else None,
            "valid_until": c.valid_until.isoformat() if c.valid_until else None,
            "expired": _is_expired(c.valid_until),
            "notes": c.notes,
        }
        for c in coupons
    ]

@router.get("/account/transactions")
async def public_account_transactions(
    email: str = Query(..., min_length=5, max_length=255),
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """Paginated history of the customer's purchases (PR3 espace client)."""
    from app.models.pos import TransactionItem
    from sqlalchemy.orm import selectinload

    client = await _resolve_public_client(db, email)
    rows = await db.execute(
        select(Transaction)
        .options(selectinload(Transaction.items).selectinload(TransactionItem.product))
        .where(Transaction.client_id == client.id)
        .order_by(Transaction.created_at.desc())
        .limit(max(1, min(limit, 100)))
    )
    transactions = rows.scalars().all()
    return [
        {
            "id": str(t.id),
            "transaction_number": t.transaction_number,
            "transaction_type": t.transaction_type.value,
            "total_ttc": float(t.total_ttc or 0),
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "items": [
                {
                    "name": (it.product.name if it.product else "Article"),
                    "quantity": int(it.quantity or 0),
                    "line_total": float(it.line_total or 0),
                }
                for it in (t.items or [])[:10]
            ],
        }
        for t in transactions
    ]

@router.get("/account/consents")
async def public_account_consents(
    email: str = Query(..., min_length=5, max_length=255),
    db: AsyncSession = Depends(get_db),
):
    """Human-readable consent state across all RGPD purposes (PR3 espace client).

    For each ``ConsentPurpose``, returns the latest decision (granted /
    revoked) with the source + timestamp. Purposes never opted into
    surface as ``granted: false`` so the UI can render an explicit
    "désactivé" state rather than nothing.
    """
    client = await _resolve_public_client(db, email)
    rows = await db.execute(
        select(Consent)
        .where(Consent.client_id == client.id)
        .order_by(Consent.created_at.desc())
    )
    history = rows.scalars().all()

    latest: dict[ConsentPurpose, Consent] = {}
    for row in history:
        latest.setdefault(row.purpose, row)

    out = []
    for purpose in ConsentPurpose:
        row = latest.get(purpose)
        out.append({
            "purpose": purpose.value,
            "label": _CONSENT_LABELS.get(purpose, purpose.value),
            "granted": bool(row.granted) if row else False,
            "source": row.source if row else None,
            "policy_version": row.policy_version if row else None,
            "recorded_at": row.created_at.isoformat() if row and row.created_at else None,
        })
    return out

@router.post("/account/consents/{purpose}")
async def public_account_consent_toggle(
    purpose: str,
    payload: ConsentToggleRequest,
    db: AsyncSession = Depends(get_db),
):
    """Append a consent ledger row for any purpose from the espace client.

    Mirrors :func:`toggle_personal_shopper` and :func:`toggle_trend_alerts`
    but for the generic /account/rgpd page.
    """
    from fastapi import Response

    try:
        consent_purpose = ConsentPurpose(purpose)
    except ValueError:
        raise HTTPException(status_code=404, detail="unknown_purpose")

    client = await _resolve_public_client(db, payload.email)
    db.add(
        Consent(
            client_id=client.id,
            purpose=consent_purpose,
            granted=payload.granted,
            policy_version="v2-2026-04",
            source="account_self_service",
        )
    )
    if consent_purpose in (ConsentPurpose.email_marketing, ConsentPurpose.sms_marketing):
        # Mirror legacy boolean flag (kept for the cron jobs that still
        # consult ``Client.email_optin`` / ``sms_optin``).
        flag = "email_optin" if consent_purpose == ConsentPurpose.email_marketing else "sms_optin"
        setattr(client, flag, payload.granted)
    await db.commit()
    return Response(status_code=204)

class GiftMarkRequest(BaseModel):
    email: str
    is_gift: bool = True


@router.post("/account/transactions/{transaction_id}/gift")
async def public_mark_transaction_gift(
    transaction_id: uuid.UUID,
    payload: GiftMarkRequest,
    db: AsyncSession = Depends(get_db),
):
    """Client-side « c'était un cadeau » toggle on a past purchase (§4.3/§5.2).

    Excludes the purchase from the taste profile (kept for CA + loyalty) and
    refreshes the centroid + qualification so the espace client reflects the
    change right away. 404 if the transaction isn't the caller's."""
    client = await _resolve_public_client(db, payload.email)
    row = await db.execute(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.client_id == client.id,
        )
    )
    tx = row.scalar_one_or_none()
    if tx is None:
        raise HTTPException(status_code=404, detail="Transaction introuvable")
    tx.is_gift = payload.is_gift
    tx.exclude_from_taste = payload.is_gift
    await db.flush()

    from app.services.customer_qualification import compute_qualification
    from app.services.embeddings import EmbeddingService

    await EmbeddingService(db).recompute_taste_profile(client.id)
    await compute_qualification(db, client.id)
    await db.commit()
    return {"transaction_id": str(transaction_id), "is_gift": tx.is_gift}


@router.post("/account/onboarding")
async def public_submit_onboarding(
    request: PublicOnboardingRequest,
    db: AsyncSession = Depends(get_db),
):
    """Public: same as the authenticated endpoint, identified by email."""
    from app.services.onboarding import cold_start_taste_profile

    cleaned = _normalize_email(request.email)
    result = await db.execute(select(Client).where(Client.email == cleaned))
    client = result.scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=404, detail="Aucun compte trouvé")

    profile = await cold_start_taste_profile(
        db, client,
        gender=request.gender,
        age_band=request.age_band,
        liked_style_keys=request.liked_style_keys,
        preferred_occasions=request.preferred_occasions,
        preferred_price_buckets=request.preferred_price_buckets,
        preferred_categories=request.preferred_categories,
        preferred_brands=request.preferred_brands,
        liked_product_ids=request.liked_product_ids,
    )

    # Completing the Personal Shopper questionnaire is an explicit profiling
    # opt-in (the page states the purpose). Record it so the live selection
    # works right after onboarding instead of hitting a 403 gate. Idempotent:
    # only add a grant row when the latest decision isn't already "granted".
    latest = await db.execute(
        select(Consent)
        .where(
            Consent.client_id == client.id,
            Consent.purpose == ConsentPurpose.profiling,
        )
        .order_by(Consent.created_at.desc())
        .limit(1)
    )
    current = latest.scalar_one_or_none()
    if current is None or not current.granted:
        await _record_consent_toggle(
            db, client, ConsentPurpose.profiling, True, source="site_onboarding"
        )

    await db.commit()
    return {
        "client_email": cleaned,
        # ``profile`` is None when only layer 1 (genre/âge) was submitted — no
        # centroid yet, but the declarative fields were still persisted.
        "profile_id": str(profile.id) if profile else None,
        "algo_version": profile.algo_version if profile else None,
        "gender_profile": client.gender_profile,
        "age_band": client.age_band,
    }


@router.get("/account/loyalty/status")
async def public_loyalty_status(
    email: str = Query(..., min_length=5, max_length=255),
    db: AsyncSession = Depends(get_db),
):
    """Membership state for the espace client (#3) — drives the subscribe CTA."""
    from app.services.loyalty import loyalty_active
    from app.services.loyalty_config import get_subscription_config

    client = await _resolve_public_client(db, email)
    cfg = await get_subscription_config(db)
    number = (
        client.loyalty_account.membership_number
        if client.loyalty_account
        else None
    )
    return {
        "active": loyalty_active(client),
        "membership_number": number,
        "mode": cfg.effective_mode(),
        "price_cents": cfg.price_cents,
        "expires_at": client.loyalty_expires_at.isoformat()
        if client.loyalty_expires_at
        else None,
    }


@router.post("/account/loyalty/subscribe")
async def public_loyalty_subscribe(
    request: LoyaltySubscribeRequest,
    db: AsyncSession = Depends(get_db),
):
    """Self-service loyalty subscription from the espace client (#3).

    The client must already exist (magic-link login). Idempotent: returns the
    existing membership if there's already an account. The card is issued in
    the currently active mode (free / paid / first_purchase); no online
    payment is taken — a paid mode is simply surfaced so the boutique can
    settle it on the next visit."""
    from app.services.loyalty import (
        LoyaltyDuplicateError,
        loyalty_active,
        subscribe,
    )
    from app.services.loyalty_config import get_subscription_config

    client = await _resolve_public_client(db, request.email)
    if client.loyalty_account is not None:
        return {
            "membership_number": client.loyalty_account.membership_number,
            "mode": client.loyalty_subscription_mode,
            "active": loyalty_active(client),
            "expires_at": client.loyalty_expires_at.isoformat()
            if client.loyalty_expires_at
            else None,
            "already_member": True,
        }

    cfg = await get_subscription_config(db)
    mode = cfg.effective_mode()
    try:
        _client, account = await subscribe(
            db,
            first_name=client.first_name or request.first_name or "Cliente",
            last_name=client.last_name or request.last_name or "Vintiz",
            email=client.email,
            postal_code=None,
            mode=mode,
            optin_newsletter=request.optin_newsletter,
            optin_profiling=request.optin_profiling,
            source="site_self_service",
        )
    except LoyaltyDuplicateError as exc:
        return {
            "membership_number": exc.membership_number,
            "mode": client.loyalty_subscription_mode,
            "active": True,
            "already_member": True,
        }
    await db.commit()
    return {
        "membership_number": account.membership_number,
        "mode": mode,
        "active": True,
        "expires_at": _client.loyalty_expires_at.isoformat()
        if _client.loyalty_expires_at
        else None,
        "already_member": False,
    }


@router.get("/account/wallet")
async def public_wallet_pass(
    email: str = Query(..., min_length=5, max_length=255),
    db: AsyncSession = Depends(get_db),
):
    """Return the loyalty Wallet pass payload by client email.

    Generic 404 on unknown email — same shape as ``/clients/lookup`` so
    we don't expose enumeration. The payload contains the Apple
    ``pass.json`` and the Google ``LoyaltyObject`` plus the metadata the
    front needs to render a preview card.
    """
    from app.services.wallet import (
        apple_wallet_available,
        build_pass_by_email,
        google_wallet_available,
        payload_to_dict,
    )

    email_clean = email.strip().lower()
    if "@" not in email_clean or "." not in email_clean.split("@", 1)[-1]:
        raise HTTPException(status_code=400, detail="Adresse email invalide")
    pass_payload = await build_pass_by_email(db, email_clean)
    if pass_payload is None:
        raise HTTPException(status_code=404, detail="Compte introuvable")
    out = payload_to_dict(pass_payload)
    out["apple_signed_available"] = apple_wallet_available()
    out["google_save_available"] = google_wallet_available()
    return out

@router.get("/account/wallet/apple")
async def download_apple_pass(
    email: str = Query(..., min_length=5, max_length=255),
    db: AsyncSession = Depends(get_db),
):
    """Download a signed ``.pkpass`` archive (Apple Wallet).

    Returns 200 with the binary when the dev certs are configured, or 503
    with a JSON explaining how to activate it. The fallback QR endpoint
    remains available either way.
    """
    from fastapi.responses import Response
    from app.services.wallet import build_pass_by_email, build_apple_pkpass

    email_clean = email.strip().lower()
    if "@" not in email_clean:
        raise HTTPException(status_code=400, detail="Adresse email invalide")
    pass_payload = await build_pass_by_email(db, email_clean)
    if pass_payload is None:
        raise HTTPException(status_code=404, detail="Compte introuvable")
    pkpass = build_apple_pkpass(pass_payload)
    if pkpass is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Apple Wallet pass non configuré : posez WALLET_APPLE_P12_PATH, "
                "WALLET_APPLE_P12_PASSWORD, WALLET_APPLE_WWDR_PATH et WALLET_TEAM_IDENTIFIER. "
                "En attendant, utilisez l'export QR via /api/crm/account/wallet/qr.png."
            ),
        )
    filename = f"vintiz-{pass_payload.membership_number}.pkpass"
    return Response(
        content=pkpass,
        media_type="application/vnd.apple.pkpass",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

@router.get("/account/wallet/google")
async def download_google_pass(
    email: str = Query(..., min_length=5, max_length=255),
    db: AsyncSession = Depends(get_db),
):
    """Redirect the browser to the Google Wallet save URL.

    Returns 503 when the Service Account JSON is not configured.
    """
    from fastapi.responses import RedirectResponse
    from app.services.wallet import build_pass_by_email, build_google_save_url

    email_clean = email.strip().lower()
    if "@" not in email_clean:
        raise HTTPException(status_code=400, detail="Adresse email invalide")
    pass_payload = await build_pass_by_email(db, email_clean)
    if pass_payload is None:
        raise HTTPException(status_code=404, detail="Compte introuvable")
    save_url = build_google_save_url(pass_payload)
    if not save_url:
        raise HTTPException(
            status_code=503,
            detail=(
                "Google Wallet non configuré : posez WALLET_GOOGLE_SERVICE_ACCOUNT_JSON "
                "et WALLET_GOOGLE_ISSUER_ID."
            ),
        )
    return RedirectResponse(url=save_url, status_code=302)

@router.get("/account/wallet/qr.png")
async def download_wallet_qr(
    email: str = Query(..., min_length=5, max_length=255),
    db: AsyncSession = Depends(get_db),
):
    """Always-on PNG fallback : QR code encoding the membership URL."""
    from fastapi.responses import Response
    from app.services.wallet import build_pass_by_email, build_qr_png

    email_clean = email.strip().lower()
    if "@" not in email_clean:
        raise HTTPException(status_code=400, detail="Adresse email invalide")
    pass_payload = await build_pass_by_email(db, email_clean)
    if pass_payload is None:
        raise HTTPException(status_code=404, detail="Compte introuvable")
    png = build_qr_png(pass_payload)
    if png is None:
        raise HTTPException(
            status_code=500,
            detail="Génération QR indisponible (paquet 'qrcode' manquant)",
        )
    filename = f"vintiz-{pass_payload.membership_number}-qr.png"
    return Response(
        content=png,
        media_type="image/png",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )

