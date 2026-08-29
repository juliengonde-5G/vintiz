"""Fidélité : débit du compteur à l'émission du chèque cadeau.

Bug relevé en boutique : le chèque fidélité (coupon ``loyalty_milestone``)
était émis au franchissement du palier mais le compteur de points n'était
jamais débité — la cliente gardait ses points ET son chèque, et chaque
palier suivant était atteint trop tôt.

La nouvelle règle (services/pos.py) débite le palier à l'émission (ligne
``redeem`` au ledger). Cette migration régularise les comptes existants :
pour chaque compte, on retire ``nb de chèques déjà consommateurs de
points × palier``, borné au solde courant (jamais de solde négatif créé
ici), avec une ligne ``adjust`` traçante. Les chèques « consommateurs de
points » sont ceux encore actifs ou déjà dépensés ; un chèque révoqué
suite à retour avait déjà vu ses points annulés par le reversal de
l'earn — il ne compte pas.

Revision ID: 0076
Revises: 0075
Create Date: 2026-08-29
"""

import uuid

import sqlalchemy as sa
from alembic import op

revision = "0076"
down_revision = "0075"
branch_labels = None
depends_on = None

_REGUL_MARKER = "Régularisation débit à l'émission"


def upgrade() -> None:
    bind = op.get_bind()

    # Palier configuré (admin/operations), repli sur le défaut historique.
    threshold_row = bind.execute(
        sa.text(
            "SELECT value FROM app_settings WHERE key = 'loyalty_voucher_threshold'"
        )
    ).fetchone()
    try:
        threshold = max(1, int(threshold_row[0])) if threshold_row else 100
    except (TypeError, ValueError):
        threshold = 100

    # ``legacy_debt`` : l'ancien chemin de remboursement (« Dette bon
    # fidélité déjà utilisé ») débitait déjà le palier d'un chèque dépensé
    # dont la vente d'origine était retournée — ces paliers-là ne doivent
    # pas être déduits une seconde fois ici.
    rows = bind.execute(
        sa.text(
            """
            SELECT la.id, la.points,
                   (
                     SELECT COUNT(*) FROM coupons c
                     WHERE c.client_id = la.client_id
                       AND c.source = 'loyalty_milestone'
                       AND (c.is_active = :true_val OR c.redeemed_at IS NOT NULL)
                   ) AS vouchers,
                   (
                     SELECT COALESCE(-SUM(lt2.points), 0)
                     FROM loyalty_transactions lt2
                     WHERE lt2.account_id = la.id
                       AND lt2.description LIKE :debt_marker
                   ) AS legacy_debt
            FROM loyalty_accounts la
            WHERE NOT EXISTS (
                SELECT 1 FROM loyalty_transactions lt
                WHERE lt.account_id = la.id
                  AND lt.description LIKE :marker
            )
            """
        ),
        {
            "true_val": True,
            "marker": f"%{_REGUL_MARKER}%",
            "debt_marker": "Dette bon fidélité déjà utilisé%",
        },
    ).fetchall()

    is_postgres = bind.dialect.name == "postgresql"
    insert_sql = sa.text(
        """
        INSERT INTO loyalty_transactions
            (id, account_id, tx_type, points, description, created_at, updated_at)
        VALUES
            (:id, :account_id, {tt}, :points, :description,
             CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """.format(tt="CAST(:tx_type AS loyalty_tx_type)" if is_postgres else ":tx_type")
    )

    for account_id, points, vouchers, legacy_debt in rows:
        points = int(points or 0)
        vouchers = int(vouchers or 0)
        legacy_debt = max(0, int(legacy_debt or 0))
        owed = max(0, vouchers * threshold - legacy_debt)
        deduction = min(max(points, 0), owed)
        if deduction <= 0:
            continue
        bind.execute(
            sa.text(
                "UPDATE loyalty_accounts SET points = points - :d WHERE id = :id"
            ),
            {"d": deduction, "id": account_id},
        )
        bind.execute(
            insert_sql,
            {
                "id": (
                    str(uuid.uuid4()) if not is_postgres else uuid.uuid4()
                ),
                "account_id": account_id,
                "tx_type": "adjust",
                "points": -deduction,
                "description": (
                    f"{_REGUL_MARKER} — {vouchers} chèque(s) déjà émis × "
                    f"{threshold} pts"
                ),
            },
        )


def downgrade() -> None:
    # Régularisation de données : irréversible proprement (les ventes
    # postérieures auront déjà consommé des paliers). No-op assumé.
    pass
