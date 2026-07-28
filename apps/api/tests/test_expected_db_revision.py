"""Garde-fou : EXPECTED_DB_REVISION doit suivre le head Alembic.

En production, ``app.main`` refuse de démarrer si la révision de la base ne
correspond pas à ``EXPECTED_DB_REVISION`` (schéma migration-owned, NF525).
Toute nouvelle migration DOIT donc bumper cette constante. Ce test échoue si on
ajoute une migration sans mettre à jour ``app/version.py`` — ce qui, sinon,
casse le boot de l'API en prod après déploiement.
"""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from app.version import EXPECTED_DB_REVISION


def test_expected_db_revision_matches_alembic_head():
    alembic_dir = Path(__file__).resolve().parents[1] / "alembic"
    cfg = Config()
    cfg.set_main_option("script_location", str(alembic_dir))
    script = ScriptDirectory.from_config(cfg)

    heads = script.get_heads()
    assert len(heads) == 1, f"Attendu un seul head Alembic, trouvé : {heads}"
    assert EXPECTED_DB_REVISION == heads[0], (
        f"EXPECTED_DB_REVISION={EXPECTED_DB_REVISION!r} ne correspond pas au "
        f"head Alembic {heads[0]!r}. Bumper app/version.py après toute migration."
    )
