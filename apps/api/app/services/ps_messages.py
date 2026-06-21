"""Persist + send a Personal Shopper selection to a client.

Records a :class:`PersonalShopperMessage` (the narrative + the products
proposed, with a snapshot) and, when a channel is requested, sends it through
the email/SMS gateway and mirrors a ``CommunicationLog`` row so the selection
shows up in the client's Communications tab too.

The send is best-effort: a gateway failure is recorded as ``status="failed"``
on the message row (it is not lost) rather than raising."""

from __future__ import annotations

import html
import logging

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client
from app.models.communications import CommunicationLog
from app.models.personal_shopper import PersonalShopperMessage

logger = logging.getLogger("vintiz")

_DEFAULT_SUBJECT = "Votre sélection Personal Shopper Vintiz"


def serialize(msg: PersonalShopperMessage) -> dict:
    return {
        "id": str(msg.id),
        "subject": msg.subject,
        "message": msg.message,
        "product_ids": list(msg.product_ids or []),
        "products": list(msg.products_snapshot or []),
        "channel": msg.channel,
        "status": msg.status,
        "backend": msg.backend,
        "algo_version": msg.algo_version,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    }


def _render_html(client: Client, narrative: str, products: list[dict]) -> str:
    name = (client.first_name or "").strip()
    greeting = f"<p>Bonjour {html.escape(name)},</p>" if name else "<p>Bonjour,</p>"
    body = "".join(
        f"<p>{html.escape(line)}</p>" for line in (narrative or "").splitlines() if line.strip()
    )
    items = ""
    for p in products or []:
        label = html.escape(str(p.get("name") or "Pièce"))
        brand = html.escape(str(p.get("brand") or ""))
        price = p.get("sale_price")
        price_str = f" — {float(price):.2f} €" if price is not None else ""
        brand_str = f" ({brand})" if brand else ""
        items += f"<li>{label}{brand_str}{price_str}</li>"
    products_block = f"<ul>{items}</ul>" if items else ""
    return (
        f"{greeting}{body}{products_block}"
        "<p>À très vite chez Vintiz Vernon.</p>"
        "<p style='color:#8B8B86;font-size:12px'>Vous recevez ce message car vous êtes "
        "membre du programme Personal Shopper. Gérez vos préférences depuis votre espace client.</p>"
    )


async def create_and_send(
    db: AsyncSession,
    client: Client,
    *,
    message: str,
    product_ids: list[str],
    products: list[dict] | None = None,
    channel: str = "email",
    subject: str | None = None,
    algo_version: str | None = None,
    sent_by_id=None,
) -> PersonalShopperMessage:
    """Persist a Personal Shopper selection and (optionally) send it.

    ``channel`` ∈ {email, sms, none}. ``none`` only records the selection
    (e.g. presented in store). Returns the persisted row with its final status.
    """
    channel = channel if channel in ("email", "sms", "none") else "email"
    subject = (subject or _DEFAULT_SUBJECT).strip()[:255]
    products = products or []

    row = PersonalShopperMessage(
        client_id=client.id,
        subject=subject,
        message=message or "",
        product_ids=[str(p) for p in (product_ids or [])],
        products_snapshot=products,
        channel=channel,
        status="draft",
        algo_version=algo_version,
        sent_by_id=sent_by_id,
    )
    db.add(row)
    await db.flush()

    backend: str | None = None
    status = "draft"
    detail: str | None = None
    body_html: str | None = None

    if channel == "email":
        if not client.email:
            status = "failed"
            detail = "client sans email"
        else:
            try:
                from app.services.email_gateway import EmailMessage, send_email

                body_html = _render_html(client, message, products)
                outcome = send_email(EmailMessage(
                    to=client.email,
                    to_name=f"{client.first_name} {client.last_name}".strip() or None,
                    subject=subject,
                    html=body_html,
                    tags=["personal-shopper"],
                ))
                status = outcome.status
                backend = outcome.backend
            except Exception as exc:  # noqa: BLE001
                logger.warning("PS message email failed for client_id=%s: %s", client.id, exc)
                status = "failed"
                detail = str(exc)[:200]
    elif channel == "sms":
        if not client.phone:
            status = "failed"
            detail = "client sans téléphone"
        else:
            try:
                from app.services.sms_gateway import SMSMessage, send_sms

                sms_out = send_sms(SMSMessage(to=client.phone, body=(message or "")[:480]))
                status = sms_out.status
                backend = sms_out.backend
            except Exception as exc:  # noqa: BLE001
                logger.warning("PS message sms failed for client_id=%s: %s", client.id, exc)
                status = "failed"
                detail = str(exc)[:200]
    else:  # none
        status = "saved"

    row.status = status
    row.backend = backend

    # Mirror into the communication log (so it shows in the Communications tab),
    # except for the "none" channel which was never actually sent.
    if channel in ("email", "sms"):
        db.add(CommunicationLog(
            client_id=client.id,
            channel=channel,
            kind="personal_shopper",
            to_address=client.email if channel == "email" else client.phone,
            subject=subject,
            status=status,
            backend=backend,
            detail=detail,
            template_key=None,
            body_html=body_html,
        ))

    await db.flush()
    return row


async def list_for_client(db: AsyncSession, client_id, *, limit: int = 20) -> list[dict]:
    rows = (
        await db.execute(
            select(PersonalShopperMessage)
            .where(PersonalShopperMessage.client_id == client_id)
            .order_by(desc(PersonalShopperMessage.created_at))
            .limit(limit)
        )
    ).scalars().all()
    return [serialize(r) for r in rows]


async def last_for_client(db: AsyncSession, client_id) -> dict | None:
    row = (
        await db.execute(
            select(PersonalShopperMessage)
            .where(PersonalShopperMessage.client_id == client_id)
            .order_by(desc(PersonalShopperMessage.created_at))
            .limit(1)
        )
    ).scalar_one_or_none()
    return serialize(row) if row else None


async def count_for_client(db: AsyncSession, client_id) -> int:
    return int(
        (
            await db.execute(
                select(func.count())
                .select_from(PersonalShopperMessage)
                .where(PersonalShopperMessage.client_id == client_id)
            )
        ).scalar_one()
    )
