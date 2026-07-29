#!/usr/bin/env python3
"""Create a brand-new Vintiz schema, then hand ownership to Alembic.

This command is intentionally limited to an empty database. Historical
migrations predate the initial schema and cannot be replayed from revision
0001 on a blank database; create_all establishes the current structural base,
then revision 0072 installs the fiscal triggers and production invariants.
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from app.core.database import engine
from app.models import Base  # imports every mapped table


BASELINE_REVISION = "0071"


async def _create_only_if_empty() -> None:
    async with engine.begin() as connection:
        # Les extensions doivent exister AVANT create_all : les modèles
        # embeddings déclarent des colonnes VECTOR (pgvector) et certains
        # défauts s'appuient sur pgcrypto. La migration 0008 crée aussi
        # ``vector``, mais create_all tourne AVANT les migrations ici.
        if engine.dialect.name == "postgresql":
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
        tables = await connection.run_sync(
            lambda sync_connection: inspect(sync_connection).get_table_names()
        )
        business_tables = [name for name in tables if name != "alembic_version"]
        if business_tables:
            raise RuntimeError(
                "Bootstrap refused: database is not empty (tables: "
                + ", ".join(sorted(business_tables)[:10])
                + ")"
            )
        await connection.run_sync(Base.metadata.create_all)
    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Initialize an empty Vintiz database before Alembic upgrade"
    )
    parser.add_argument(
        "--confirm-empty",
        action="store_true",
        help="required safety acknowledgement",
    )
    args = parser.parse_args()
    if not args.confirm_empty:
        parser.error("--confirm-empty is required")

    asyncio.run(_create_only_if_empty())
    repository_root = Path(__file__).resolve().parents[1]
    api_root = repository_root / "apps" / "api"
    if not (api_root / "alembic.ini").exists():
        # Docker image layout copies apps/api directly to /app.
        api_root = repository_root
    config = Config(str(api_root / "alembic.ini"))
    config.set_main_option("script_location", str(api_root / "alembic"))
    command.stamp(config, BASELINE_REVISION)
    print(f"Empty schema created and stamped at {BASELINE_REVISION}")


if __name__ == "__main__":
    main()
