"""Communication helpers — template rendering, send logging, defaults seed.

- ``render_template(db, key, context, fallback_*)`` → resolves an admin
  ``MessageTemplate`` and substitutes ``{variable}`` placeholders, falling
  back to the caller's hard-coded text when the template is missing/inactive
  (a disabled template must never block a send).
- ``log_communication(db, ...)`` → writes one ``CommunicationLog`` row. Called
  at sender sites because the email/SMS gateways are stateless (no db).
- ``seed_default_templates(db)`` → idempotent insert of the editable defaults.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.communications import CommunicationLog, MessageTemplate

logger = logging.getLogger("vintiz.communications")


class _SafeDict(dict):
    """str.format_map helper: leaves unknown {placeholders} untouched."""

    def __missing__(self, key: str) -> str:  # noqa: D401
        return "{" + key + "}"


def _fmt(text: str | None, context: dict) -> str | None:
    if text is None:
        return None
    try:
        return text.format_map(_SafeDict(context))
    except (ValueError, IndexError):
        # Malformed braces in an admin-edited template → return as-is rather
        # than crash the send.
        return text


@dataclass
class RenderedMessage:
    subject: str | None
    html: str | None
    text: str | None
    template_key: str | None  # None when the fallback was used


async def render_template(
    db: AsyncSession,
    key: str,
    context: dict,
    *,
    fallback_subject: str | None = None,
    fallback_html: str | None = None,
    fallback_text: str | None = None,
) -> RenderedMessage:
    """Render the active template for ``key``; fall back to the passed text.

    Defensive: if the ``message_templates`` table is absent (migration not yet
    applied) the lookup is treated as "no template" → caller's fallback. A
    template must never break or block a send.
    """
    tpl = None
    try:
        row = await db.execute(
            select(MessageTemplate).where(MessageTemplate.key == key)
        )
        tpl = row.scalar_one_or_none()
    except Exception as exc:  # pragma: no cover — missing table / migration lag
        logger.warning("render_template: lookup failed for %s: %s", key, exc)
        await db.rollback()
    if tpl is None or not tpl.is_active:
        return RenderedMessage(
            subject=_fmt(fallback_subject, context),
            html=_fmt(fallback_html, context),
            text=_fmt(fallback_text, context),
            template_key=None,
        )
    return RenderedMessage(
        subject=_fmt(tpl.subject, context) or _fmt(fallback_subject, context),
        html=_fmt(tpl.body_html, context) or _fmt(fallback_html, context),
        text=_fmt(tpl.body_text, context) or _fmt(fallback_text, context),
        template_key=tpl.key,
    )


async def log_communication(
    db: AsyncSession,
    *,
    client_id: uuid.UUID | None,
    channel: str,
    kind: str,
    status: str,
    to_address: str | None = None,
    subject: str | None = None,
    backend: str | None = None,
    detail: str | None = None,
    template_key: str | None = None,
    body_html: str | None = None,
) -> None:
    """Append a CommunicationLog row. Best-effort: never raise into a send path."""
    try:
        db.add(
            CommunicationLog(
                client_id=client_id,
                channel=channel,
                kind=kind,
                status=status,
                to_address=to_address,
                subject=subject,
                backend=backend,
                detail=(detail or "")[:2000] or None,
                template_key=template_key,
                body_html=body_html,
            )
        )
        await db.flush()
    except Exception as exc:  # pragma: no cover — logging must not break sends
        logger.warning("communication log failed (kind=%s): %s", kind, exc)
        try:
            await db.rollback()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Default templates (editable in the admin afterwards)
# ---------------------------------------------------------------------------

DEFAULT_TEMPLATES: list[dict] = [
    {
        "key": "anniversary",
        "channel": "email",
        "label": "Anniversaire",
        "description": "Variables : {prenom}, {code_coupon}, {valeur}, {validite_jours}",
        "subject": "🎂 Joyeux anniversaire {prenom} !",
        "body_html": (
            "<p>Joyeux anniversaire {prenom} ! Pour fêter ça, profitez de "
            "<strong>{valeur}</strong> avec le code <strong>{code_coupon}</strong> "
            "(valable {validite_jours} jours).</p>"
            "<p>À très vite chez Vintiz Vernon.</p>"
        ),
        "body_text": (
            "Joyeux anniversaire {prenom} ! Profitez de {valeur} avec le code "
            "{code_coupon} (valable {validite_jours} jours). À très vite chez Vintiz."
        ),
    },
    {
        "key": "new_arrivals",
        "channel": "email",
        "label": "Nouveautés de la semaine",
        "description": "Variables : {prenom}, {nb_pieces}",
        "subject": "🌿 Vintiz — les nouveautés de la semaine",
        "body_html": (
            "<p>Bonjour {prenom},</p>"
            "<p>{nb_pieces} nouvelles pièces viennent d'arriver en boutique à "
            "Vernon. Venez les découvrir avant qu'elles ne partent !</p>"
        ),
        "body_text": (
            "Bonjour {prenom}, {nb_pieces} nouvelles pièces viennent d'arriver "
            "en boutique à Vernon. Venez les découvrir !"
        ),
    },
    {
        "key": "trend_alert",
        "channel": "email",
        "label": "Alerte tendance personnalisée",
        "description": "Variables : {prenom}, {produit}, {prix}",
        "subject": "Une pièce qui vous ressemble vient d'arriver : {produit}",
        "body_html": (
            "<p>Bonjour {prenom},</p>"
            "<p>Une pièce tendance correspondant à vos goûts vient d'arriver : "
            "<strong>{produit}</strong> ({prix}). Passez l'essayer en boutique !</p>"
        ),
        "body_text": (
            "Bonjour {prenom}, une pièce qui vous ressemble vient d'arriver : "
            "{produit} ({prix}). Passez l'essayer en boutique !"
        ),
    },
    {
        "key": "consent_confirmation",
        "channel": "email",
        "label": "Confirmation de consentement (profilage)",
        "description": "Variables : {prenom}",
        "subject": "Votre Personal Shopper Vintiz est activé",
        "body_html": (
            "<p>Bonjour {prenom},</p>"
            "<p>Vous avez activé votre Personal Shopper. Nous analysons vos "
            "préférences pour vous proposer des pièces qui vous ressemblent. "
            "Vous pouvez retirer ce consentement à tout moment depuis votre "
            "espace client.</p>"
        ),
        "body_text": (
            "Bonjour {prenom}, votre Personal Shopper est activé. Vous pouvez "
            "retirer ce consentement à tout moment depuis votre espace client."
        ),
    },
    {
        "key": "voucher_issued",
        "channel": "email",
        "label": "Bon cadeau crédité (zone Événementiel)",
        "description": (
            "Variables : {prenom}, {label_bon}, {code_bon}, {valable_a_partir_de}, "
            "{valide_jusqu_au}"
        ),
        "subject": "🎟 Vintiz — votre bon « {label_bon} »",
        "body_html": (
            "<p>Bonjour {prenom},</p>"
            "<p>Nous avons le plaisir de créditer sur votre fiche un bon "
            "<strong>« {label_bon} »</strong>.</p>"
            "<ul>"
            "<li>Code : <strong>{code_bon}</strong></li>"
            "<li>Utilisable à partir du {valable_a_partir_de} (pas le jour de "
            "l'émission)</li>"
            "<li>Valable jusqu'au {valide_jusqu_au}</li>"
            "<li>1 bon par personne — non cumulable</li>"
            "</ul>"
            "<p>À très vite chez Vintiz Vernon.</p>"
        ),
        "body_text": (
            "Bonjour {prenom},\n\n"
            "Un bon « {label_bon} » a été crédité sur votre fiche.\n"
            "Code : {code_bon}\n"
            "Utilisable à partir du {valable_a_partir_de}.\n"
            "Valable jusqu'au {valide_jusqu_au}.\n"
            "1 bon par personne — non cumulable.\n\n"
            "À très vite chez Vintiz Vernon."
        ),
    },
    {
        "key": "welcome_subscription",
        "channel": "email",
        "label": "Bienvenue — adhésion fidélité",
        "description": "Variables : {prenom}, {numero_carte}, {mode_adhesion}",
        "subject": "🌿 Bienvenue chez Vintiz, {prenom} !",
        "body_html": (
            "<p>Bonjour {prenom},</p>"
            "<p>Bienvenue dans le programme de fidélité <strong>Vintiz Vernon</strong>. "
            "Votre carte est créée :</p>"
            "<ul>"
            "<li>Numéro : <strong>{numero_carte}</strong></li>"
            "<li>Adhésion : {mode_adhesion}</li>"
            "<li>1 € dépensé = 1 point — 1 point = 0,10 € de remise</li>"
            "</ul>"
            "<p>Retrouvez votre solde, vos avantages et vos préférences depuis "
            "votre espace client.</p>"
            "<p>À très vite en boutique !</p>"
        ),
        "body_text": (
            "Bonjour {prenom},\n\n"
            "Bienvenue dans le programme de fidélité Vintiz Vernon.\n"
            "Numéro de carte : {numero_carte}\n"
            "Adhésion : {mode_adhesion}\n"
            "1 € dépensé = 1 point — 1 point = 0,10 € de remise.\n\n"
            "À très vite en boutique !"
        ),
    },
    {
        "key": "welcome_account",
        "channel": "email",
        "label": "Bienvenue — création de compte (espace client)",
        "description": "Variables : {prenom}",
        "subject": "🌿 Bienvenue chez Vintiz, {prenom} !",
        "body_html": (
            "<p>Bonjour {prenom},</p>"
            "<p>Votre espace client Vintiz Vernon est prêt. Vous y retrouverez "
            "vos achats, vos avantages fidélité, vos préférences et la gestion "
            "de vos données (RGPD).</p>"
            "<p>Vous recevez en parallèle un email avec votre lien magique de "
            "connexion (sans mot de passe).</p>"
            "<p>À très vite en boutique !</p>"
        ),
        "body_text": (
            "Bonjour {prenom},\n\n"
            "Votre espace client Vintiz Vernon est prêt.\n"
            "Un email avec votre lien magique de connexion vient d'être envoyé "
            "séparément.\n\n"
            "À très vite en boutique !"
        ),
    },
]


async def seed_default_templates(db: AsyncSession) -> int:
    """Insert any missing default template (idempotent). Returns count added."""
    added = 0
    for spec in DEFAULT_TEMPLATES:
        exists = await db.execute(
            select(MessageTemplate.id).where(MessageTemplate.key == spec["key"])
        )
        if exists.scalar_one_or_none() is not None:
            continue
        db.add(MessageTemplate(**spec))
        added += 1
    if added:
        await db.flush()
    return added
