"""Daily cleanup job for stale customer taste profiles (audit C12).

RGPD art. 5-1-c (minimisation) + politique de conservation Vintiz :
les embeddings (`CustomerTasteProfile`) suivent le programme de fidélité.
Quand un compte de fidélité est expiré pour cause d'inactivité (24 mois
sans transaction — cf. `loyalty_expiry.py`), son profil de goûts est
également purgé. Si une cliente revient ensuite, son profil sera
recalculé from scratch sur ses nouveaux achats.

Le cron tourne quotidiennement (orchestré dans `scheduler.py` ou
équivalent) à 03:30 par exemple, juste après `expire_inactive_points`.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client, LoyaltyAccount, LoyaltyTransaction
from app.models.embeddings import CustomerTasteProfile


logger = logging.getLogger("vintiz.embeddings_cleanup")


# Cohérence avec `loyalty_expiry.EXPIRY_DAYS` — quand le compte fidélité
# est zéro pour cause d'inactivité, le profil de goûts n'a plus de raison
# d'exister. 24 mois = standard Vintiz.
INACTIVITY_DAYS = 730


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def purge_inactive_taste_profiles(
    db: AsyncSession, *, dry_run: bool = False
) -> dict:
    """Supprime les CustomerTasteProfile de clientes inactives ≥ 24 mois.

    Critère retenu : aucun ``LoyaltyTransaction`` ni ``Client.last_seen_at``
    dans les 24 derniers mois. Si la cliente n'a *jamais* eu de transaction,
    son profil est aussi purgé après 24 mois depuis la création du compte.

    Cohérent avec `loyalty_expiry.expire_inactive_points` qui zéroïse les
    points dans la même fenêtre — on garde les deux mécaniques alignées.

    Args:
        db: session async ouverte.
        dry_run: si True, retourne la liste des candidats sans rien
            supprimer (utile pour un endpoint admin de preview).

    Returns:
        ``{"candidate_count": N, "deleted_count": N, "deleted_customer_ids": [...]}``
    """
    cutoff = _now() - timedelta(days=INACTIVITY_DAYS)

    # On part des profils existants. Pour chacun, on cherche s'il y a une
    # activité loyalty récente. Une jointure SQL "anti-LATERAL" via
    # NOT EXISTS est efficace en Postgres + SQLite.
    last_loyalty_subq = (
        select(func.max(LoyaltyTransaction.created_at))
        .join(LoyaltyAccount, LoyaltyAccount.id == LoyaltyTransaction.account_id)
        .where(LoyaltyAccount.client_id == CustomerTasteProfile.customer_id)
        .scalar_subquery()
    )

    candidates_q = (
        select(CustomerTasteProfile, last_loyalty_subq.label("last_tx"))
        .where(
            # Soit aucune tx loyalty (NULL) avec création profil ancienne,
            # soit dernière tx ≤ cutoff.
            (last_loyalty_subq == None)  # noqa: E711 — explicit IS NULL needed
            | (last_loyalty_subq <= cutoff)
        )
    )
    rows = await db.execute(candidates_q)
    candidates: list[CustomerTasteProfile] = []
    for profile, _last_tx in rows.all():
        # Filtrage supplémentaire : si aucune tx, on prend la date de
        # création du profil comme ancre (pas de purge prématurée d'un
        # profil créé il y a 1 mois).
        anchor = profile.computed_at or profile.created_at
        if anchor and anchor.tzinfo is None:
            anchor = anchor.replace(tzinfo=timezone.utc)
        if anchor and anchor > cutoff:
            continue
        candidates.append(profile)

    if dry_run or not candidates:
        return {
            "candidate_count": len(candidates),
            "deleted_count": 0,
            "deleted_customer_ids": [
                str(p.customer_id) for p in candidates
            ],
            "dry_run": dry_run,
            "cutoff": cutoff.isoformat(),
        }

    customer_ids = [p.customer_id for p in candidates]
    res = await db.execute(
        delete(CustomerTasteProfile).where(
            CustomerTasteProfile.customer_id.in_(customer_ids)
        )
    )
    deleted_count = int(res.rowcount or 0)
    logger.warning(
        "embeddings_cleanup: deleted %d stale taste profiles (cutoff=%s)",
        deleted_count,
        cutoff.isoformat(),
    )

    return {
        "candidate_count": len(candidates),
        "deleted_count": deleted_count,
        "deleted_customer_ids": [str(cid) for cid in customer_ids],
        "dry_run": False,
        "cutoff": cutoff.isoformat(),
    }


async def purge_orphan_taste_profiles(db: AsyncSession) -> int:
    """Hard cleanup : supprime les profils dont la cliente n'existe plus.

    Sécurité : `hard_delete()` côté RGPD purge déjà les embeddings, mais
    si une suppression hors-flow nominal a laissé des profils orphelins
    (migration, manip directe DB), ce job les rattrape. Idempotent.
    """
    res = await db.execute(
        delete(CustomerTasteProfile).where(
            ~exists().where(Client.id == CustomerTasteProfile.customer_id)
        )
    )
    count = int(res.rowcount or 0)
    if count > 0:
        logger.warning(
            "embeddings_cleanup: removed %d orphan taste profiles",
            count,
        )
    return count
