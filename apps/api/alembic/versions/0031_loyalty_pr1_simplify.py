"""Loyalty PR1: drop tier, add membership_number V######, magic_link_tokens, loyalty config.

- Drop loyalty_accounts.tier (and loyalty_tier enum if present).
- Add loyalty_accounts.membership_number (unique, V + 6 digits, backfilled).
- Add clients.loyalty_subscribed_at, loyalty_expires_at, loyalty_subscription_mode.
- Create magic_link_tokens (OTP storage, hashed).
- Seed app_settings rows for the 3 loyalty subscription modes.

Revision ID: 0031
Revises: 0030
Create Date: 2026-04-28

Downgrade reinstates a tier column with default "bronze" but historical
tier values are NOT preserved (see plan Q1).
"""

from __future__ import annotations

import secrets

from alembic import op
import sqlalchemy as sa


revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"
    uuid_type = sa.dialects.postgresql.UUID(as_uuid=True) if is_pg else sa.String(36)
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # ------------------------------------------------------------------
    # 1. Drop loyalty_accounts.tier
    # ------------------------------------------------------------------
    if "loyalty_accounts" in existing_tables:
        loyalty_cols = {c["name"] for c in inspector.get_columns("loyalty_accounts")}
        if "tier" in loyalty_cols:
            op.drop_column("loyalty_accounts", "tier")
        if is_pg:
            op.execute("DROP TYPE IF EXISTS loyalty_tier")

    # ------------------------------------------------------------------
    # 2. Add membership_number (nullable → backfill → NOT NULL + unique)
    # ------------------------------------------------------------------
    if "loyalty_accounts" in existing_tables:
        loyalty_cols = {c["name"] for c in inspector.get_columns("loyalty_accounts")}
        if "membership_number" not in loyalty_cols:
            op.add_column(
                "loyalty_accounts",
                sa.Column("membership_number", sa.String(8), nullable=True),
            )
            rows = bind.execute(
                sa.text("SELECT id FROM loyalty_accounts WHERE membership_number IS NULL")
            ).fetchall()
            used: set[str] = set(
                r[0] for r in bind.execute(
                    sa.text("SELECT membership_number FROM loyalty_accounts WHERE membership_number IS NOT NULL")
                ).fetchall()
            )
            for (lid,) in rows:
                while True:
                    mn = "V" + f"{secrets.randbelow(1_000_000):06d}"
                    if mn not in used:
                        used.add(mn)
                        break
                bind.execute(
                    sa.text(
                        "UPDATE loyalty_accounts SET membership_number = :m WHERE id = :i"
                    ),
                    {"m": mn, "i": lid},
                )
            op.alter_column("loyalty_accounts", "membership_number", nullable=False)
            op.create_unique_constraint(
                "uq_loyalty_accounts_membership_number",
                "loyalty_accounts",
                ["membership_number"],
            )

    # ------------------------------------------------------------------
    # 3. Client: subscription metadata
    # ------------------------------------------------------------------
    if "clients" in existing_tables:
        client_cols = {c["name"] for c in inspector.get_columns("clients")}
        if "loyalty_subscribed_at" not in client_cols:
            op.add_column(
                "clients",
                sa.Column("loyalty_subscribed_at", sa.DateTime(timezone=True), nullable=True),
            )
        if "loyalty_expires_at" not in client_cols:
            op.add_column(
                "clients",
                sa.Column("loyalty_expires_at", sa.DateTime(timezone=True), nullable=True),
            )
        if "loyalty_subscription_mode" not in client_cols:
            op.add_column(
                "clients",
                sa.Column("loyalty_subscription_mode", sa.String(20), nullable=True),
            )

    # ------------------------------------------------------------------
    # 4. magic_link_tokens table
    # ------------------------------------------------------------------
    if "magic_link_tokens" not in existing_tables:
        op.create_table(
            "magic_link_tokens",
            sa.Column(
                "id",
                uuid_type,
                primary_key=True,
                server_default=sa.text("gen_random_uuid()") if is_pg else None,
            ),
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
            sa.Column("email", sa.String(255), nullable=False),
            sa.Column("token_hash", sa.String(128), nullable=False),
            sa.Column("code_hash", sa.String(128), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
            sa.Column("ip", sa.String(45), nullable=True),
            sa.UniqueConstraint("token_hash", name="uq_magic_link_tokens_token_hash"),
        )
        op.create_index(
            "ix_magic_link_tokens_email_created",
            "magic_link_tokens",
            ["email", "created_at"],
        )

    # ------------------------------------------------------------------
    # 5. Seed app_settings for loyalty subscription config
    # ------------------------------------------------------------------
    if "app_settings" in existing_tables:
        defaults = [
            ("loyalty_subscription_mode", "free", "Mode souscription fidelite: free | paid | first_purchase"),
            ("loyalty_subscription_price_cents", "500", "Prix souscription en centimes (mode paid)"),
            ("loyalty_first_purchase_threshold_cents", "3000", "Seuil offert au 1er achat en centimes (mode first_purchase)"),
        ]
        for key, value, desc in defaults:
            existing = bind.execute(
                sa.text("SELECT 1 FROM app_settings WHERE key = :k"),
                {"k": key},
            ).fetchone()
            if existing is None:
                if is_pg:
                    bind.execute(
                        sa.text(
                            "INSERT INTO app_settings (id, key, value, description, created_at, updated_at) "
                            "VALUES (gen_random_uuid(), :k, :v, :d, now(), now())"
                        ),
                        {"k": key, "v": value, "d": desc},
                    )
                else:
                    import uuid as _uuid
                    bind.execute(
                        sa.text(
                            "INSERT INTO app_settings (id, key, value, description, created_at, updated_at) "
                            "VALUES (:i, :k, :v, :d, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                        ),
                        {"i": str(_uuid.uuid4()), "k": key, "v": value, "d": desc},
                    )


def downgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "magic_link_tokens" in existing_tables:
        try:
            op.drop_index("ix_magic_link_tokens_email_created", table_name="magic_link_tokens")
        except Exception:
            pass
        op.drop_table("magic_link_tokens")

    if "clients" in existing_tables:
        client_cols = {c["name"] for c in inspector.get_columns("clients")}
        for col in ("loyalty_subscription_mode", "loyalty_expires_at", "loyalty_subscribed_at"):
            if col in client_cols:
                op.drop_column("clients", col)

    if "loyalty_accounts" in existing_tables:
        loyalty_cols = {c["name"] for c in inspector.get_columns("loyalty_accounts")}
        if "membership_number" in loyalty_cols:
            try:
                op.drop_constraint(
                    "uq_loyalty_accounts_membership_number",
                    "loyalty_accounts",
                    type_="unique",
                )
            except Exception:
                pass
            op.drop_column("loyalty_accounts", "membership_number")
        if "tier" not in loyalty_cols:
            op.add_column(
                "loyalty_accounts",
                sa.Column(
                    "tier",
                    sa.String(50),
                    nullable=False,
                    server_default="bronze",
                ),
            )

    if "app_settings" in existing_tables:
        for key in (
            "loyalty_subscription_mode",
            "loyalty_subscription_price_cents",
            "loyalty_first_purchase_threshold_cents",
        ):
            bind.execute(sa.text("DELETE FROM app_settings WHERE key = :k"), {"k": key})
