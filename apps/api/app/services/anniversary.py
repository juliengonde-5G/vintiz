"""Birthday email automation (P4-008).

Daily cron picks every client whose ``birth_date.month/day`` matches
today, issues a 7-day anniversary coupon (10% off) and sends them a
warm note via the email gateway. Skips clients without ``email_optin``
or without ``email`` set.

Idempotency:
- ``issue_anniversary_coupon`` already deduplicates per calendar day, so
  a manual rerun won't double-issue.
- We rely on Brevo / SMTP transactional retries for delivery; the
  service swallows individual failures and reports a summary.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import extract, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client, ConsentPurpose
from app.services.coupon import issue_anniversary_coupon
from app.services.email_gateway import EmailDeliveryError, EmailMessage, send_email


logger = logging.getLogger("vintiz.anniversary")


def _email_html(client: Client, code: str, percent: float) -> str:
    first_name = client.first_name or "vous"
    return f"""
    <div style="font-family: Poppins, system-ui, sans-serif; color: #000; max-width: 540px;">
      <h1 style="font-family: 'Lexend Mega', sans-serif; color: #008678;">
        Joyeux anniversaire {first_name} !
      </h1>
      <p>Toute l'équipe Vintiz vous souhaite une merveilleuse journée.</p>
      <p>Pour fêter ça, profitez de <strong>−{int(percent)}%</strong> sur la
      pièce de votre choix pendant les 7 prochains jours.</p>
      <div style="background:#FFC5DF; padding:16px; border-radius:12px; text-align:center; margin:16px 0;">
        <p style="margin:0; font-size:12px; color:#000; text-transform:uppercase; letter-spacing:0.06em;">
          Code à présenter en boutique
        </p>
        <p style="margin:8px 0 0 0; font-family: 'Lexend Mega', sans-serif; font-size:24px; font-weight:700; color:#000;">
          {code}
        </p>
      </div>
      <p>À très vite à Vernon,<br/>L'équipe Vintiz</p>
    </div>
    """.strip()


def _email_text(client: Client, code: str, percent: float) -> str:
    return (
        f"Joyeux anniversaire {client.first_name} !\n\n"
        f"Pour fêter ça, profitez de -{int(percent)}% pendant 7 jours en "
        f"présentant ce code en boutique : {code}\n\n"
        f"À très vite à Vernon,\nL'équipe Vintiz"
    )


async def _candidates_today(
    db: AsyncSession, now: datetime
) -> Iterable[Client]:
    result = await db.execute(
        select(Client).where(
            Client.birth_date.is_not(None),
            Client.email.is_not(None),
            Client.email_optin.is_(True),
            Client.deletion_requested_at.is_(None),
            extract("month", Client.birth_date) == now.month,
            extract("day", Client.birth_date) == now.day,
        )
    )
    return list(result.scalars().all())


async def run_anniversary_pass(
    db: AsyncSession,
    *,
    now: datetime | None = None,
    percent_off: float = 10.0,
) -> dict:
    """Issue + send anniversary coupons for every birthday today.

    Returns a summary dict suitable for the cron log line. Does NOT
    raise — individual failures (one bad email) shouldn't kill the run.
    """
    now = now or datetime.now(timezone.utc)
    clients = list(await _candidates_today(db, now))
    if not clients:
        return {"considered": 0, "coupons": 0, "emails_sent": 0, "failures": 0}

    coupons_issued = 0
    sent = 0
    failed = 0

    for client in clients:
        try:
            coupon = await issue_anniversary_coupon(
                db, client.id, percent_off=percent_off, now=now,
            )
            # Commit each coupon as we go so a later client's crash can't
            # roll back the ones we already issued — the run becomes safe
            # to re-trigger and partial progress is durable.
            await db.commit()
            coupons_issued += 1
        except Exception:
            logger.exception("Anniversary coupon failed for client_id=%s", client.id)
            await db.rollback()
            failed += 1
            continue

        from app.services.communications import (
            log_communication,
            render_template,
        )

        first_name = client.first_name or "cliente fidèle"
        rendered = await render_template(
            db,
            "anniversary",
            {
                "prenom": first_name,
                "code_coupon": coupon.code,
                "valeur": f"{percent_off:.0f} %",
                "validite_jours": 30,
            },
            fallback_subject="🎂 Joyeux anniversaire — un cadeau Vintiz vous attend",
            fallback_html=_email_html(client, coupon.code, percent_off),
            fallback_text=_email_text(client, coupon.code, percent_off),
        )
        # RGPD (CNIL 2026) — suivi d'ouverture uniquement si consentement
        # spécifique ``email_open_tracking``.
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
            logger.exception("Anniversary email failed for client_id=%s", client.id)
            failed += 1
            detail = str(exc)
        await log_communication(
            db, client_id=client.id, channel="email", kind="anniversary",
            status=status, to_address=client.email, subject=rendered.subject,
            backend=backend, detail=detail, template_key=rendered.template_key,
        )
        await db.commit()

    return {
        "considered": len(clients),
        "coupons": coupons_issued,
        "emails_sent": sent,
        "failures": failed,
    }
