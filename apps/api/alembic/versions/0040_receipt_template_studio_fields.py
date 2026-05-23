"""add presentation / email / legal fields to receipt_templates

Revision ID: 0040
Revises: 0039
Create Date: 2026-05-23

Backs the "Tickets & Factures" studio (Settings) — Pennylane-style invoice
customisation: accent colour, header note, payment terms, legal mentions,
block toggles, and a configurable invoice email (subject + body) so the PDF
facture can be mailed with a personalised message.

All columns are NULL-able or carry a server default: existing rows keep
working untouched. Idempotent.
"""

from alembic import op
import sqlalchemy as sa


revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    )
    return result.fetchone() is not None


TEMPLATE_COLUMNS = [
    ("accent_color", sa.String(9), "#0B7A6A"),
    ("header_note", sa.Text(), None),
    ("payment_terms", sa.Text(), None),
    ("legal_mentions", sa.Text(), None),
    ("email_subject", sa.String(200), None),
    ("email_body", sa.Text(), None),
    ("show_payment_block", sa.Boolean(), True),
    ("show_legal_mentions", sa.Boolean(), True),
]


def upgrade() -> None:
    for name, type_, default in TEMPLATE_COLUMNS:
        if _column_exists("receipt_templates", name):
            continue
        kwargs: dict = {"nullable": True}
        if default is not None:
            kwargs["server_default"] = (
                sa.text("true") if default is True else sa.text(f"'{default}'")
            )
        op.add_column("receipt_templates", sa.Column(name, type_, **kwargs))


def downgrade() -> None:
    for name, _type, _default in TEMPLATE_COLUMNS:
        if _column_exists("receipt_templates", name):
            op.drop_column("receipt_templates", name)
