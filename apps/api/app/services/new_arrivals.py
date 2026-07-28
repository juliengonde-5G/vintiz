"""Weekly "new arrivals" email (P4-009).

Friday 10:00 cron picks every email-opted client whose deletion isn't
pending, then sends them a digest of the 5 most recent products that
just hit the floor (status = ``displayed`` and ``displayed_at`` ≥
N-7 days). When the personal-shopper service has a taste profile for
the client, we use its top recommendations instead so the digest is
personalised.

Email rendering is deliberately simple (no MJML / Jinja). The template
is a hand-written string with a tiny product loop — easy to read in
the codebase, easy to tweak. Brevo + Apple Mail render basic
``<table>`` layouts reliably.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client, ConsentPurpose
from app.models.product import Product, ProductStatus
from app.services.email_gateway import EmailDeliveryError, EmailMessage, send_email


logger = logging.getLogger("vintiz.new_arrivals")


N_PRODUCTS_PER_EMAIL = 5
LOOKBACK_DAYS = 7


async def _generic_new_arrivals(
    db: AsyncSession, *, since: datetime, limit: int = N_PRODUCTS_PER_EMAIL,
) -> list[Product]:
    """Default selection: most recently displayed pieces."""
    result = await db.execute(
        select(Product)
        .where(
            Product.status == ProductStatus.displayed,
            Product.displayed_at.is_not(None),
            Product.displayed_at >= since,
        )
        .order_by(Product.displayed_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def _personalized_arrivals(
    db: AsyncSession, client_id, *, limit: int = N_PRODUCTS_PER_EMAIL
) -> list[Product] | None:
    """Run the Personal Shopper for the client; returns None on
    cold-start or any error so the caller falls back to generic."""
    try:
        from app.services.personal_shopper import PersonalShopperService

        svc = PersonalShopperService(db)
        result = await svc.recommend(client_id, top_n=limit)
        product_ids = [p.get("id") for p in result.get("products", []) if p.get("id")]
        if not product_ids:
            return None
        # Re-fetch as ORM rows so we can use the same template format
        # below regardless of the source.
        rows = await db.execute(
            select(Product).where(Product.id.in_(product_ids))
        )
        # Preserve recommendation order.
        by_id = {str(p.id): p for p in rows.scalars().all()}
        ordered = [by_id[pid] for pid in product_ids if pid in by_id]
        return ordered[:limit]
    except Exception as exc:
        logger.debug("Personal-shopper unavailable for %s: %s", client_id, exc)
        return None


def _render_html(client: Client, products: list[Product]) -> str:
    items = ""
    for product in products:
        photo = product.photo_url or ""
        photo_html = (
            f'<img src="{photo}" alt="" '
            f'style="width:100%;border-radius:8px;display:block;" />'
            if photo else ""
        )
        items += f"""
        <td style="vertical-align:top; padding:8px; width:50%;">
          {photo_html}
          <p style="margin:8px 0 0 0; font-weight:600;">{product.name}</p>
          <p style="margin:0; color:#008678; font-weight:600;">
            {float(product.sale_price):.2f} €
          </p>
        </td>"""

    return f"""
    <div style="font-family: Poppins, system-ui, sans-serif; color: #000; max-width: 540px;">
      <h1 style="font-family: 'Lexend Mega', sans-serif; color: #008678;">
        Nouveautés de la semaine
      </h1>
      <p>Bonjour {client.first_name}, voici les pièces fraîchement
      arrivées qui vous attendent à Vintiz Vernon.</p>
      <table style="border-spacing:0; width:100%;">
        <tr>{items}</tr>
      </table>
      <p style="margin-top:16px; color:#666; font-size:12px;">
        Vous recevez cet email car vous avez choisi de rester informée
        des nouveautés Vintiz. Vous pouvez vous désinscrire à tout moment
        depuis votre <a href="https://vintiz.fr/account/data">espace client</a>.
      </p>
    </div>
    """.strip()


def _render_text(client: Client, products: list[Product]) -> str:
    lines = [f"Bonjour {client.first_name},", "", "Nouveautés cette semaine :", ""]
    for product in products:
        lines.append(f"- {product.name} — {float(product.sale_price):.2f} €")
    lines.extend(["", "À très vite à Vernon,", "L'équipe Vintiz"])
    return "\n".join(lines)


async def _opted_in_clients(db: AsyncSession) -> Iterable[Client]:
    result = await db.execute(
        select(Client).where(
            Client.email.is_not(None),
            Client.email_optin.is_(True),
            Client.deletion_requested_at.is_(None),
        )
    )
    return list(result.scalars().all())


async def run_new_arrivals_pass(
    db: AsyncSession, *, now: datetime | None = None
) -> dict:
    """Pick recipients, build per-client product list, send via gateway."""
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(days=LOOKBACK_DAYS)
    generic = await _generic_new_arrivals(db, since=since)
    if not generic:
        return {"recipients": 0, "sent": 0, "failed": 0, "skipped_no_products": True}

    clients = list(await _opted_in_clients(db))
    sent = 0
    failed = 0

    for client in clients:
        products = await _personalized_arrivals(db, client.id) or generic
        if not products:
            continue
        from app.services.communications import (
            log_communication,
            render_template,
        )

        rendered = await render_template(
            db,
            "new_arrivals",
            {"prenom": client.first_name or "", "nb_pieces": len(products)},
            fallback_subject="🌿 Vintiz — les nouveautés de la semaine",
            fallback_html=_render_html(client, products),
            fallback_text=_render_text(client, products),
        )
        # RGPD (CNIL 2026) — pixel d'ouverture uniquement si consentement
        # spécifique ``email_open_tracking``. Sinon envoi marketing SANS
        # suivi individuel (track_opens=False).
        from app.services.rgpd import latest_consent_granted

        track_opens = await latest_consent_granted(
            db, client.id, ConsentPurpose.email_open_tracking
        )
        message = EmailMessage(
            to=client.email,
            to_name=f"{client.first_name} {client.last_name}".strip() or None,
            subject=rendered.subject,
            html=rendered.html,
            text=rendered.text,
            track_opens=track_opens,
        )
        status = "failed"
        backend = None
        detail = None
        try:
            outcome = send_email(message)
            status = outcome.status
            backend = outcome.backend
            detail = outcome.detail
            if outcome.status in {"sent", "simulated"}:
                sent += 1
            else:
                failed += 1
        except EmailDeliveryError as exc:
            logger.warning("New-arrivals email failed for %s: %s", client.email, exc)
            failed += 1
            detail = str(exc)
        await log_communication(
            db, client_id=client.id, channel="email", kind="new_arrivals",
            status=status, to_address=client.email, subject=rendered.subject,
            backend=backend, detail=detail, template_key=rendered.template_key,
        )

    return {
        "recipients": len(clients),
        "sent": sent,
        "failed": failed,
        "n_products": len(generic),
    }
