"""POS refonte SumUp-like — fondation : routine caisse + facture B2B + NF525 intangible.

Couvre les 4 axes du plan :

1. ``receipt_templates`` — templates de tickets / factures configurables en
   /settings (titre, footer, conditions de retour, mention TVA détaillée,
   show_loyalty_footer). Snapshot via ``transactions.template_id``.
2. ``payment_attempts`` — chaque tentative de paiement (CB initiate, cash
   submit, cheque, avoir) loggée même si la vente n'aboutit pas. Permet
   l'historique complet "/admin/transactions" et le debug CB échouée
   sans polluer la chaîne NF525.
3. ``cash_movements`` — entrées / sorties de cash en cours de journée
   (dépôt banque, paiement fournisseur, prélèvement perso, top-up float).
   Lit dans le calcul de l'expected_amount à la clôture.
4. ``sumup_terminals`` — registre multi-terminaux Solo (Lenovo dock + S11
   Ultra mobile). Garde la rétro-compat env var quand la table est vide.

Enrichit aussi :
- ``transactions`` : 6 colonnes facture B2B (is_invoice, invoice_number,
  client_siret, client_company_name, client_billing_address, template_id)
  + invoice_number_seq (PG seulement)
- ``cash_drawers`` : 4 colonnes routine caisse (opening_breakdown JSONB,
  closing_breakdown JSONB, closing_note TEXT, allowed_discrepancy NUMERIC)
- ``z_reports`` : 7 colonnes intangibilité NF525 (is_locked, locked_at,
  locked_by_user_id, pdf_content BYTEA, pdf_sha256, emailed_at, emailed_to)

Toutes les modifications sont **additives + nullable** : la prod en cours
continue à fonctionner avec l'ancien code (PR 1 n'active rien). Le
câblage API/UI suit en PR 2-6.

Revision ID: 0035
Revises: 0034
Create Date: 2026-05-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def _enum(*values: str) -> sa.types.TypeEngine:
    """Portable enum : ENUM postgres, plain VARCHAR sur SQLite (tests)."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return sa.Enum(*values, name=f"_enum_{abs(hash(values))}")
    return sa.String(length=40)


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column in {c["name"] for c in inspector.get_columns(table)}


def _index_exists(table: str, name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return name in {idx["name"] for idx in inspector.get_indexes(table)}


def _table_exists(table: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table in set(inspector.get_table_names())


# ---------------------------------------------------------------------------
# Common columns helper — id + created_at + updated_at, like ``Base``.
# ---------------------------------------------------------------------------

def _audit_columns(uuid_type) -> list[sa.Column]:
    return [
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()" if op.get_bind().dialect.name == "postgresql" else "CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()" if op.get_bind().dialect.name == "postgresql" else "CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"
    uuid_type = (
        sa.dialects.postgresql.UUID(as_uuid=True) if is_pg else sa.String(length=36)
    )

    # -----------------------------------------------------------------------
    # 1. receipt_templates
    # -----------------------------------------------------------------------
    if not _table_exists("receipt_templates"):
        op.create_table(
            "receipt_templates",
            *_audit_columns(uuid_type),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column(
                "kind",
                sa.Enum("ticket", "invoice", name="receipt_kind") if is_pg else sa.String(length=40),
                nullable=False,
            ),
            sa.Column("title", sa.String(length=120), nullable=False),
            sa.Column("footer", sa.Text(), nullable=False, server_default=""),
            sa.Column("conditions_retour", sa.Text(), nullable=True),
            sa.Column(
                "show_tva_breakdown", sa.Boolean(), nullable=False, server_default=sa.text("false")
            ),
            sa.Column(
                "show_loyalty_footer", sa.Boolean(), nullable=False, server_default=sa.text("true")
            ),
            sa.Column(
                "is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")
            ),
            sa.Column(
                "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
            ),
        )
        op.create_index(
            "ix_receipt_templates_kind_active",
            "receipt_templates",
            ["kind", "is_active"],
        )

    # -----------------------------------------------------------------------
    # 2. payment_attempts
    # -----------------------------------------------------------------------
    if not _table_exists("payment_attempts"):
        op.create_table(
            "payment_attempts",
            *_audit_columns(uuid_type),
            sa.Column(
                "method",
                # Reuse existing payment_method enum on PG ; portable string on SQLite
                sa.Enum("cash", "card", "cheque", "transfer", "avoir", name="payment_method", create_type=False) if is_pg else sa.String(length=40),
                nullable=False,
            ),
            sa.Column("amount", sa.Numeric(10, 2), nullable=False),
            sa.Column(
                "status",
                sa.Enum(
                    "pending",
                    "succeeded",
                    "failed",
                    "cancelled",
                    name="payment_attempt_status",
                ) if is_pg else sa.String(length=40),
                nullable=False,
                server_default="pending",
            ),
            sa.Column(
                "cashier_id",
                uuid_type,
                sa.ForeignKey("users.id"),
                nullable=True,
            ),
            sa.Column(
                "drawer_id",
                uuid_type,
                sa.ForeignKey("cash_drawers.id"),
                nullable=True,
            ),
            sa.Column(
                "transaction_id",
                uuid_type,
                sa.ForeignKey("transactions.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("sumup_checkout_id", sa.String(length=100), nullable=True),
            sa.Column("error_detail", sa.Text(), nullable=True),
            sa.Column("cancelled_reason", sa.Text(), nullable=True),
        )
        op.create_index(
            "ix_payment_attempts_created_at",
            "payment_attempts",
            ["created_at"],
        )
        op.create_index(
            "ix_payment_attempts_status",
            "payment_attempts",
            ["status"],
        )
        op.create_index(
            "ix_payment_attempts_drawer_id",
            "payment_attempts",
            ["drawer_id"],
        )

    # -----------------------------------------------------------------------
    # 3. cash_movements
    # -----------------------------------------------------------------------
    if not _table_exists("cash_movements"):
        op.create_table(
            "cash_movements",
            *_audit_columns(uuid_type),
            sa.Column(
                "drawer_id",
                uuid_type,
                sa.ForeignKey("cash_drawers.id"),
                nullable=False,
            ),
            sa.Column(
                "direction",
                sa.Enum("in", "out", name="cash_movement_direction") if is_pg else sa.String(length=10),
                nullable=False,
            ),
            sa.Column("amount", sa.Numeric(10, 2), nullable=False),
            sa.Column(
                "reason",
                sa.Enum(
                    "bank_deposit",
                    "supplier_payment",
                    "personal_withdrawal",
                    "float_top_up",
                    "other",
                    name="cash_movement_reason",
                ) if is_pg else sa.String(length=40),
                nullable=False,
                server_default="other",
            ),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column(
                "user_id",
                uuid_type,
                sa.ForeignKey("users.id"),
                nullable=False,
            ),
            sa.Column(
                "cashier_id",
                uuid_type,
                sa.ForeignKey("users.id"),
                nullable=True,
            ),
        )
        op.create_index(
            "ix_cash_movements_drawer_id",
            "cash_movements",
            ["drawer_id"],
        )

    # -----------------------------------------------------------------------
    # 4. sumup_terminals
    # -----------------------------------------------------------------------
    if not _table_exists("sumup_terminals"):
        op.create_table(
            "sumup_terminals",
            *_audit_columns(uuid_type),
            sa.Column("label", sa.String(length=80), nullable=False),
            sa.Column(
                "reader_id",
                sa.String(length=100),
                nullable=False,
                unique=True,
            ),
            sa.Column(
                "status",
                sa.Enum(
                    "active",
                    "inactive",
                    "unknown",
                    name="sumup_terminal_status",
                ) if is_pg else sa.String(length=20),
                nullable=False,
                server_default="unknown",
            ),
            sa.Column(
                "last_heartbeat_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
            sa.Column("last_heartbeat_status", sa.String(length=40), nullable=True),
            sa.Column("location", sa.String(length=120), nullable=True),
            sa.Column(
                "is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")
            ),
            sa.Column("notes", sa.Text(), nullable=True),
        )

    # -----------------------------------------------------------------------
    # 5. transactions — 6 colonnes facture B2B
    # -----------------------------------------------------------------------
    if _table_exists("transactions"):
        if not _column_exists("transactions", "is_invoice"):
            op.add_column(
                "transactions",
                sa.Column(
                    "is_invoice", sa.Boolean(), nullable=False, server_default=sa.text("false")
                ),
            )
        if not _column_exists("transactions", "invoice_number"):
            op.add_column(
                "transactions",
                sa.Column("invoice_number", sa.Integer(), nullable=True, unique=True),
            )
        if not _column_exists("transactions", "client_siret"):
            op.add_column(
                "transactions",
                sa.Column("client_siret", sa.String(length=14), nullable=True),
            )
        if not _column_exists("transactions", "client_company_name"):
            op.add_column(
                "transactions",
                sa.Column("client_company_name", sa.String(length=255), nullable=True),
            )
        if not _column_exists("transactions", "client_billing_address"):
            op.add_column(
                "transactions",
                sa.Column("client_billing_address", sa.Text(), nullable=True),
            )
        if not _column_exists("transactions", "template_id"):
            op.add_column(
                "transactions",
                sa.Column("template_id", uuid_type, nullable=True),
            )
            if is_pg:
                op.create_foreign_key(
                    "fk_transactions_template_id",
                    "transactions",
                    "receipt_templates",
                    ["template_id"],
                    ["id"],
                    ondelete="SET NULL",
                )
        if not _index_exists("transactions", "ix_transactions_is_invoice"):
            op.create_index(
                "ix_transactions_is_invoice",
                "transactions",
                ["is_invoice"],
            )

    # invoice_number_seq — séquence dédiée NF525, séparée de
    # transaction_number_seq (ordre tickets). PostgreSQL only.
    if is_pg:
        op.execute("CREATE SEQUENCE IF NOT EXISTS invoice_number_seq START WITH 1")

    # -----------------------------------------------------------------------
    # 6. cash_drawers — routine caisse (breakdown + écart autorisé)
    # -----------------------------------------------------------------------
    if _table_exists("cash_drawers"):
        for col_name, col_type in [
            ("opening_breakdown", sa.dialects.postgresql.JSONB() if is_pg else sa.JSON()),
            ("closing_breakdown", sa.dialects.postgresql.JSONB() if is_pg else sa.JSON()),
            ("closing_note", sa.Text()),
            ("allowed_discrepancy", sa.Numeric(10, 2)),
        ]:
            if not _column_exists("cash_drawers", col_name):
                op.add_column(
                    "cash_drawers",
                    sa.Column(col_name, col_type, nullable=True),
                )

    # -----------------------------------------------------------------------
    # 7. z_reports — verrouillage intangible NF525
    # -----------------------------------------------------------------------
    if _table_exists("z_reports"):
        for col_name, col_type, col_default in [
            ("is_locked", sa.Boolean(), sa.text("false")),
            ("locked_at", sa.DateTime(timezone=True), None),
            ("pdf_sha256", sa.String(length=64), None),
            ("emailed_at", sa.DateTime(timezone=True), None),
            ("emailed_to", sa.String(length=255), None),
        ]:
            if not _column_exists("z_reports", col_name):
                op.add_column(
                    "z_reports",
                    sa.Column(
                        col_name,
                        col_type,
                        nullable=col_default is None or col_name != "is_locked",
                        server_default=col_default,
                    ),
                )
        if not _column_exists("z_reports", "locked_by_user_id"):
            op.add_column(
                "z_reports",
                sa.Column("locked_by_user_id", uuid_type, nullable=True),
            )
            if is_pg:
                op.create_foreign_key(
                    "fk_z_reports_locked_by_user",
                    "z_reports",
                    "users",
                    ["locked_by_user_id"],
                    ["id"],
                    ondelete="SET NULL",
                )
        # PDF blob — large_binary on PG = BYTEA, BLOB on SQLite.
        if not _column_exists("z_reports", "pdf_content"):
            op.add_column(
                "z_reports",
                sa.Column(
                    "pdf_content",
                    sa.LargeBinary(),
                    nullable=True,
                ),
            )

    # -----------------------------------------------------------------------
    # 8. Seed — 2 default templates (idempotent: skip if any row already)
    # -----------------------------------------------------------------------
    seed_check = bind.execute(sa.text("SELECT COUNT(*) FROM receipt_templates")).scalar()
    if (seed_check or 0) == 0:
        op.execute(
            sa.text(
                """
                INSERT INTO receipt_templates
                  (id, name, kind, title, footer, conditions_retour,
                   show_tva_breakdown, show_loyalty_footer, is_default, is_active,
                   created_at, updated_at)
                VALUES
                  (
                    """ + ("gen_random_uuid()" if is_pg else "lower(hex(randomblob(16)))") + """,
                    'Ticket boutique standard',
                    'ticket',
                    'VINTIZ — Boutique seconde main premium',
                    'Merci de votre visite ! À bientôt en boutique.',
                    'Échange ou remboursement sous 14 jours, ticket et étiquette obligatoires.',
                    false, true, true, true,
                    """ + ("now(), now()" if is_pg else "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP") + """
                  ),
                  (
                    """ + ("gen_random_uuid()" if is_pg else "lower(hex(randomblob(16)))") + """,
                    'Facture B2B standard',
                    'invoice',
                    'VINTIZ — Facture',
                    'Vintiz — 6 rue Saint-Jacques, 27200 Vernon. Mode de paiement et conditions au verso.',
                    NULL,
                    true, false, true, true,
                    """ + ("now(), now()" if is_pg else "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP") + """
                  )
                """
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    # 7. z_reports — drop NF525 columns
    if _table_exists("z_reports"):
        if is_pg:
            try:
                op.drop_constraint(
                    "fk_z_reports_locked_by_user", "z_reports", type_="foreignkey"
                )
            except Exception:
                pass
        for col in (
            "pdf_content",
            "locked_by_user_id",
            "emailed_to",
            "emailed_at",
            "pdf_sha256",
            "locked_at",
            "is_locked",
        ):
            if _column_exists("z_reports", col):
                op.drop_column("z_reports", col)

    # 6. cash_drawers
    if _table_exists("cash_drawers"):
        for col in (
            "allowed_discrepancy",
            "closing_note",
            "closing_breakdown",
            "opening_breakdown",
        ):
            if _column_exists("cash_drawers", col):
                op.drop_column("cash_drawers", col)

    # 5. transactions — drop invoice columns
    if _table_exists("transactions"):
        if is_pg:
            try:
                op.drop_constraint(
                    "fk_transactions_template_id", "transactions", type_="foreignkey"
                )
            except Exception:
                pass
        if _index_exists("transactions", "ix_transactions_is_invoice"):
            op.drop_index("ix_transactions_is_invoice", table_name="transactions")
        for col in (
            "template_id",
            "client_billing_address",
            "client_company_name",
            "client_siret",
            "invoice_number",
            "is_invoice",
        ):
            if _column_exists("transactions", col):
                op.drop_column("transactions", col)
    if is_pg:
        op.execute("DROP SEQUENCE IF EXISTS invoice_number_seq")

    # 4. sumup_terminals
    if _table_exists("sumup_terminals"):
        op.drop_table("sumup_terminals")
        if is_pg:
            op.execute("DROP TYPE IF EXISTS sumup_terminal_status")

    # 3. cash_movements
    if _table_exists("cash_movements"):
        op.drop_index("ix_cash_movements_drawer_id", table_name="cash_movements")
        op.drop_table("cash_movements")
        if is_pg:
            op.execute("DROP TYPE IF EXISTS cash_movement_direction")
            op.execute("DROP TYPE IF EXISTS cash_movement_reason")

    # 2. payment_attempts
    if _table_exists("payment_attempts"):
        for idx in (
            "ix_payment_attempts_drawer_id",
            "ix_payment_attempts_status",
            "ix_payment_attempts_created_at",
        ):
            try:
                op.drop_index(idx, table_name="payment_attempts")
            except Exception:
                pass
        op.drop_table("payment_attempts")
        if is_pg:
            op.execute("DROP TYPE IF EXISTS payment_attempt_status")

    # 1. receipt_templates
    if _table_exists("receipt_templates"):
        if _index_exists("receipt_templates", "ix_receipt_templates_kind_active"):
            op.drop_index(
                "ix_receipt_templates_kind_active", table_name="receipt_templates"
            )
        op.drop_table("receipt_templates")
        if is_pg:
            op.execute("DROP TYPE IF EXISTS receipt_kind")
