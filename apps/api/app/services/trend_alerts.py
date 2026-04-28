"""Trend product alerts (PR2 — cible client #2).

Daily cron: scan products that just joined the catalogue with a high
``trend_score`` and notify by email each opt-in customer whose taste
profile matches. Implementation knobs:

- ``TREND_SCORE_THRESHOLD`` — min ``Product.trend_score`` to qualify.
- ``MATCH_THRESHOLD`` — min cosine similarity between the customer's
  taste profile and the product embedding.
- ``ALERT_FREQUENCY_DAYS`` — frequency cap per customer (PR2 plan: 7).
- ``MAX_PRODUCTS_PER_RUN`` — safeguard against floods.

Audience selection:
1. Loyalty active (gating consistent with the Personal Shopper).
2. Latest ``trend_alerts`` consent row is ``granted=True``.
3. Latest ``profiling`` consent row is ``granted=True`` (we use the
   taste profile, so profiling consent is mandatory).
4. ``last_trend_alert_at`` is null OR older than the cap.

Each successful send updates ``Client.last_trend_alert_at`` so the next
run respects the cap.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client, Consent, ConsentPurpose
from app.models.embeddings import CustomerTasteProfile, ProductEmbedding
from app.models.product import Product, ProductStatus
from app.services.email_gateway import EmailDeliveryError, EmailMessage, send_email


logger = logging.getLogger("vintiz.trend_alerts")


TREND_SCORE_THRESHOLD = 70.0
MATCH_THRESHOLD = 0.65
ALERT_FREQUENCY_DAYS = 7
MAX_PRODUCTS_PER_RUN = 50
NEW_ARRIVAL_WINDOW_HOURS = 36  # arrived "recently"
EMBEDDING_VISUAL_WEIGHT = 0.6
EMBEDDING_TEXT_WEIGHT = 0.4


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _cosine(a, b) -> float:
    if a is None or b is None:
        return 0.0
    if len(a) == 0 or len(b) == 0 or len(a) != len(b):
        return 0.0
    dot = sum(float(x) * float(y) for x, y in zip(a, b))
    norm_a = sum(float(x) * float(x) for x in a) ** 0.5
    norm_b = sum(float(y) * float(y) for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _aware(dt: datetime | None) -> datetime | None:
    """SQLite drops tzinfo; treat naive datetimes as UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _eligible_by_cap(client: Client) -> bool:
    last = _aware(client.last_trend_alert_at)
    if last is None:
        return True
    return last < _now() - timedelta(days=ALERT_FREQUENCY_DAYS)


async def _latest_consent(
    db: AsyncSession, client_id: uuid.UUID, purpose: ConsentPurpose
) -> bool:
    row = await db.execute(
        select(Consent)
        .where(Consent.client_id == client_id, Consent.purpose == purpose)
        .order_by(desc(Consent.created_at))
        .limit(1)
    )
    consent = row.scalar_one_or_none()
    return bool(consent and consent.granted)


async def _select_recent_trending(db: AsyncSession) -> list[tuple[Product, ProductEmbedding]]:
    """Pull the freshly-arrived hot products (with embeddings)."""
    cutoff = _now() - timedelta(hours=NEW_ARRIVAL_WINDOW_HOURS)
    stmt = (
        select(Product, ProductEmbedding)
        .join(ProductEmbedding, ProductEmbedding.product_id == Product.id)
        .where(
            Product.status.in_([ProductStatus.stock, ProductStatus.display]),
            Product.trend_score >= TREND_SCORE_THRESHOLD,
            Product.created_at >= cutoff,
        )
        .order_by(desc(Product.trend_score))
        .limit(MAX_PRODUCTS_PER_RUN)
    )
    result = await db.execute(stmt)
    return [(p, e) for p, e in result.all()]


async def _select_audience(db: AsyncSession) -> list[Client]:
    """Loyalty-active clients holding a granted ``trend_alerts`` consent."""
    rows = await db.execute(
        select(Client).where(Client.loyalty_subscribed_at.is_not(None))
    )
    candidates = list(rows.scalars().all())
    audience: list[Client] = []
    for client in candidates:
        if client.loyalty_account is None:
            continue
        if not _eligible_by_cap(client):
            continue
        if not await _latest_consent(db, client.id, ConsentPurpose.trend_alerts):
            continue
        if not await _latest_consent(db, client.id, ConsentPurpose.profiling):
            continue
        # Expiry check — mirror loyalty_active() without the import dance.
        expires = _aware(client.loyalty_expires_at)
        if expires is not None and expires <= _now():
            continue
        audience.append(client)
    return audience


def _build_email(client: Client, product: Product, score: float) -> EmailMessage:
    name = client.first_name or "Bonjour"
    public_url = "https://vintiz.fr/account/shopper"
    html = (
        f"<p>Bonjour {name},</p>"
        f"<p>Une nouveauté tendance vient d'arriver chez Vintiz Vernon — "
        f"elle correspond à vos goûts.</p>"
        f"<h2 style='color:#008678'>{product.name}</h2>"
        f"<p>{product.description or ''}</p>"
        f"<p><strong>{float(product.sale_price):.2f} €</strong></p>"
        f"<p><a href='{public_url}' style='background:#008678;color:white;"
        f"padding:12px 18px;border-radius:8px;text-decoration:none'>"
        f"Voir dans mon espace</a></p>"
        f"<p style='color:#777;font-size:12px'>Pour ne plus recevoir ces alertes, "
        f"désactivez « Alertes nouveautés tendance » dans votre espace client.</p>"
    )
    return EmailMessage(
        to=client.email or "",
        subject=f"Nouveauté tendance pour vous : {product.name}",
        html=html,
        to_name=f"{client.first_name} {client.last_name}".strip(),
    )


async def run_trend_alerts(db: AsyncSession) -> dict[str, int]:
    """Send trend alerts for one cron tick. Returns a summary dict.

    Idempotent within the cap: a second invocation in the same day
    finds no eligible recipients (``last_trend_alert_at`` was just set).
    """
    products = await _select_recent_trending(db)
    if not products:
        logger.info("trend_alerts: no fresh trending products")
        return {"products": 0, "audience": 0, "matched": 0, "sent": 0, "failed": 0}

    audience = await _select_audience(db)
    if not audience:
        logger.info("trend_alerts: no eligible audience (%d candidate products)", len(products))
        return {"products": len(products), "audience": 0, "matched": 0, "sent": 0, "failed": 0}

    profiles_rows = await db.execute(
        select(CustomerTasteProfile).where(
            CustomerTasteProfile.customer_id.in_([c.id for c in audience])
        )
    )
    profiles = {p.customer_id: p for p in profiles_rows.scalars().all()}

    sent = 0
    failed = 0
    matched = 0
    for client in audience:
        profile = profiles.get(client.id)
        if profile is None:
            continue

        # Pick the best matching product for this client.
        best: tuple[Product, float] | None = None
        for product, embedding in products:
            visual = _cosine(profile.visual_centroid, embedding.visual_embedding)
            text = _cosine(profile.text_centroid, embedding.text_embedding)
            score = EMBEDDING_VISUAL_WEIGHT * visual + EMBEDDING_TEXT_WEIGHT * text
            if score >= MATCH_THRESHOLD and (best is None or score > best[1]):
                best = (product, score)

        if best is None or not client.email:
            continue

        matched += 1
        message = _build_email(client, best[0], best[1])
        try:
            send_email(message)
            sent += 1
            client.last_trend_alert_at = _now()
        except EmailDeliveryError as exc:
            failed += 1
            logger.warning("trend_alerts: send failed for %s: %s", client.email, exc)

    if sent:
        await db.flush()

    summary = {
        "products": len(products),
        "audience": len(audience),
        "matched": matched,
        "sent": sent,
        "failed": failed,
    }
    logger.info("trend_alerts: %s", summary)
    return summary
