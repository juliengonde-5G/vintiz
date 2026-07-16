"""Regression tests for the PostgreSQL/asyncpg execution shape of migration 0072."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path


class _RecordingConnection:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def execute(self, statement) -> None:
        self.statements.append(str(statement).strip())


def _load_migration():
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "0072_security_loyalty_nf525.py"
    )
    spec = importlib.util.spec_from_file_location("migration_0072", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upgrade_executes_one_top_level_command_per_call(monkeypatch):
    """asyncpg rejects multiple top-level commands in one prepared statement."""
    migration = _load_migration()
    connection = _RecordingConnection()
    monkeypatch.setattr(migration.op, "get_bind", lambda: connection)

    migration.upgrade()

    assert len(connection.statements) >= 30
    assert sum(sql.startswith("CREATE TRIGGER") for sql in connection.statements) == 6
    assert sum(
        sql.startswith("CREATE OR REPLACE FUNCTION")
        for sql in connection.statements
    ) == 5
    for sql in connection.statements:
        # Semicolons inside a dollar-quoted PL/pgSQL function body are part of
        # that one CREATE FUNCTION command. Any semicolon left outside the body
        # would signal a second command and reproduce the production failure.
        outside_function_body = re.sub(r"\$\$.*?\$\$", "", sql, flags=re.DOTALL)
        assert ";" not in outside_function_body, sql
