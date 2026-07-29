"""Create product_scan_logs (historique des lectures douchette).

Chaque scan POS (hit ou miss) laisse une ligne pour reconstituer le panier
d'une vente CB « orpheline » (paiement encaissé, vente jamais validée).
Outil de diagnostic, pas un registre fiscal — rétention 7 jours (purge
quotidienne dans app/jobs.py). FKs en SET NULL + product_name/sale_price
dénormalisés pour survivre à la suppression du produit.

Revision ID: 0073
Revises: 0072
Create Date: 2026-07-18
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0073"
down_revision = "0072"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotent : sur un bootstrap frais, ``create_all`` a déjà créé la table
    # (product_scan_logs est un modèle courant). On saute alors la création
    # pour ne pas casser le flux bootstrap+upgrade (même contrat que 0032).
    if "product_scan_logs" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "product_scan_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("barcode_raw", sa.String(length=100), nullable=False),
        sa.Column("barcode_normalized", sa.String(length=100), nullable=False),
        sa.Column("matched", sa.Boolean(), nullable=False),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "permanent_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("permanent_items.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("product_name", sa.String(length=255), nullable=True),
        sa.Column("sale_price", sa.Numeric(10, 2), nullable=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        op.f("ix_product_scan_logs_barcode_normalized"),
        "product_scan_logs",
        ["barcode_normalized"],
    )
    op.create_index(
        op.f("ix_product_scan_logs_matched"), "product_scan_logs", ["matched"]
    )
    # La purge (7 j) et les requêtes « fenêtre horaire » filtrent sur created_at.
    op.create_index(
        "ix_product_scan_logs_created_at", "product_scan_logs", ["created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_product_scan_logs_created_at", table_name="product_scan_logs")
    op.drop_index(op.f("ix_product_scan_logs_matched"), table_name="product_scan_logs")
    op.drop_index(
        op.f("ix_product_scan_logs_barcode_normalized"),
        table_name="product_scan_logs",
    )
    op.drop_table("product_scan_logs")
