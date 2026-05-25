"""Refonte zonage : 14 zones + règles d'affectation (couleur/genre/taille/
catégorie/score) éditables en base.

Revision ID: 0043
Revises: 0042
Create Date: 2026-05-25

Deux phases idempotentes :
1. ADD COLUMN IF NOT EXISTS des 6 colonnes de règles (motif 0024).
2. Upsert par nom des 14 zones cibles + suppression du legacy (motif 0026 :
   les produits pointant vers une ancienne zone — dont « Chaussures F » —
   sont détachés (zone_id := NULL) puis la zone et ses children supprimés).

Le stock est purgé côté boutique → pas d'enjeu de préservation des FK.
Garder synchronisé avec ai_mapping.DEFAULT_ZONES et ia/page.tsx ZONE_LAYOUT.
"""

import json

import sqlalchemy as sa
from alembic import op

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# Phase 1 — nouvelles colonnes (Postgres ; les tests passent par metadata).
# ---------------------------------------------------------------------------
_COLUMNS = [
    ("match_genders",       "JSONB"),
    ("match_colors",        "JSONB"),
    ("match_size_classes",  "JSONB"),
    ("min_trend_score",     "NUMERIC(5, 2)"),
    ("assignment_priority", "INTEGER NOT NULL DEFAULT 100"),
    ("auto_assign",         "BOOLEAN NOT NULL DEFAULT TRUE"),
]


# ---------------------------------------------------------------------------
# Phase 2 — 14 zones cibles. Tuple :
#   (name, desc, cap, color, px, py, w, h, shape, icon, order, photo,
#    genders, colors, size_classes, categories, min_trend, priority)
# genders/colors/size_classes → colonnes JSONB ; categories → product_types
# (colonne TEXT contenant un tableau JSON, cohérent avec l'API /front).
# ---------------------------------------------------------------------------
TARGET_ZONES = [
    ("Vitrine",                 "Vitrine devanture cote entree — exposition tendance",   8, "#006B61", 84, 80, 12, 15, "rounded", "star",     1,  "/zones/vitrine.jpeg",
        None, None, None, None, 75, 10),
    ("Chaussures droite femme", "Mur droit — chaussures femme",                         48, "#FFC5DF",  4, 22, 13, 20, "rect",    "bag",      2,  "/zones/extra-2.jpeg",
        ["femme"], None, None, ["chaussures", "chaussure", "escarpin", "botte", "basket", "sandale"], None, 20),
    ("Chaussures H",            "Coin facade gauche — chaussures homme",                28, "#3B82F6",  6, 80, 14, 15, "rect",    "bag",      3,  "/zones/chaussures-h.jpeg",
        ["homme"], None, None, ["chaussures", "chaussure", "basket", "botte", "mocassin", "sneaker"], None, 21),
    ("Portant Rond Homme",      "Portant rond homme — pieces structurees",             100, "#1E40AF", 24, 42, 16, 14, "rounded", "grid",     4,  None,
        ["homme"], None, None, ["polo", "chemise", "veste", "chemisette", "haut"], None, 30),
    ("Portant Homme",           "Portant homme — basiques",                            280, "#1E3A8A", 24, 60, 18, 15, "rounded", "grid",     5,  None,
        ["homme"], None, None, ["polo", "t-shirt", "tshirt", "tee-shirt", "bermuda", "short", "shirt"], None, 31),
    ("Hommes",                  "Mur facade — collection homme (fourre-tout)",         210, "#172554", 24, 82, 18, 13, "rect",    "shirt",    6,  "/zones/hommes.jpeg",
        ["homme"], None, None, None, None, 32),
    ("Tendance",                "Tete de gondole facade — selon scoring tendance",     200, "#CC4889", 46, 80, 24, 15, "rounded", "sparkles", 7,  "/zones/tendance.jpeg",
        None, None, None, None, 70, 40),
    ("Droite 3",                "Mur droit fond — femme grandes tailles + robes longues", 115, "#008678", 8, 4, 20, 14, "rect",  "shirt",    8,  "/zones/extra-1.jpeg",
        ["femme"], None, ["grande"], None, None, 50),
    ("Portant 2",               "Portant femme — petites tailles, jupes/chemisiers/shirts", 280, "#FF97C0", 40, 44, 18, 14, "rounded", "grid", 9, None,
        ["femme"], None, ["petite"], ["jupe", "jupes", "chemisier", "chemisiers", "shirt", "chemise"], None, 51),
    ("Entrée",                  "Entree cote droit — femme rose/rouge",                 85, "#FF6FA5", 76, 2,  20, 12, "rect",    "shirt",    10, None,
        ["femme"], ["rose", "rouge"], None, None, None, 60),
    ("Droite 1",                "Mur droit — femme bleu/blanc/violet",                 155, "#26A695", 53, 2,  20, 12, "rect",    "shirt",    11, "/zones/standard-1.jpeg",
        ["femme"], ["bleu", "blanc", "violet"], None, None, None, 61),
    ("Droite 2",                "Mur droit centre — femme vert/noir/marron",           155, "#1A7A6A", 30, 2,  20, 12, "rect",    "shirt",    12, "/zones/standard-2.jpeg",
        ["femme"], ["vert", "noir", "marron"], None, None, None, 62),
    ("Portant 1",               "Portant femme — rouge/jaune/orange/marron",            10, "#F59E0B", 44, 26, 16, 13, "rounded", "grid",     13, None,
        ["femme"], ["rouge", "jaune", "orange", "marron"], None, None, None, 63),
    ("Portant Rond Femme",      "Portant rond femme — pieces structurees",             100, "#EC4899", 64, 28, 16, 14, "rounded", "grid",     14, None,
        ["femme"], None, None, ["chemisier", "veste", "chemisette", "haut"], None, 70),
]


def _table_exists(name: str) -> bool:
    conn = op.get_bind()
    return conn.execute(
        sa.text("SELECT 1 FROM information_schema.tables WHERE table_name = :t"),
        {"t": name},
    ).fetchone() is not None


def upgrade() -> None:
    # --- Phase 1 : colonnes de règles -------------------------------------
    for col, definition in _COLUMNS:
        op.execute(
            sa.text(
                f"ALTER TABLE store_zones ADD COLUMN IF NOT EXISTS {col} {definition}"
            )
        )

    if not _table_exists("store_zones"):
        return

    # --- Phase 2 : upsert des 14 zones + purge du legacy ------------------
    conn = op.get_bind()
    target_names = [row[0] for row in TARGET_ZONES]

    for (name, desc, cap, color, px, py, w, h, shape, icon, order, photo,
         genders, colors, sizes, cats, min_trend, prio) in TARGET_ZONES:
        params = {
            "n": name, "d": desc, "cap": cap, "color": color,
            "px": px, "py": py, "w": w, "h": h,
            "shape": shape, "icon": icon, "ord": order, "photo": photo,
            "mg": json.dumps(genders) if genders is not None else None,
            "mc": json.dumps(colors) if colors is not None else None,
            "ms": json.dumps(sizes) if sizes is not None else None,
            "pt": json.dumps(cats) if cats is not None else None,
            "mt": min_trend, "prio": prio,
        }
        existing = conn.execute(
            sa.text("SELECT id FROM store_zones WHERE name = :n"),
            {"n": name},
        ).fetchone()
        if existing is None:
            conn.execute(
                sa.text(
                    """
                    INSERT INTO store_zones
                        (id, name, description, capacity, color_code,
                         pos_x, pos_y, width, height, shape, icon,
                         display_order, photo_url, product_types,
                         match_genders, match_colors, match_size_classes,
                         min_trend_score, assignment_priority, auto_assign,
                         created_at, updated_at)
                    VALUES
                        (gen_random_uuid(), :n, :d, :cap, :color,
                         :px, :py, :w, :h, :shape, :icon,
                         :ord, :photo, :pt,
                         CAST(:mg AS JSONB), CAST(:mc AS JSONB), CAST(:ms AS JSONB),
                         :mt, :prio, TRUE,
                         now(), now())
                    """
                ),
                params,
            )
        else:
            conn.execute(
                sa.text(
                    """
                    UPDATE store_zones
                       SET description         = :d,
                           capacity            = :cap,
                           color_code          = :color,
                           pos_x               = :px,
                           pos_y               = :py,
                           width               = :w,
                           height              = :h,
                           shape               = :shape,
                           icon                = :icon,
                           display_order       = :ord,
                           photo_url           = COALESCE(:photo, photo_url),
                           product_types       = :pt,
                           match_genders       = CAST(:mg AS JSONB),
                           match_colors        = CAST(:mc AS JSONB),
                           match_size_classes  = CAST(:ms AS JSONB),
                           min_trend_score     = :mt,
                           assignment_priority = :prio,
                           auto_assign         = TRUE,
                           updated_at          = now()
                     WHERE name = :n
                    """
                ),
                params,
            )

    # Détacher les produits des anciennes zones (dont « Chaussures F »),
    # supprimer leurs children puis les zones absentes du nouveau set.
    rows = conn.execute(
        sa.text("SELECT id FROM store_zones WHERE name <> ALL(:names)"),
        {"names": target_names},
    ).fetchall()
    legacy_ids = [r[0] for r in rows]
    if legacy_ids:
        conn.execute(
            sa.text("UPDATE products SET zone_id = NULL WHERE zone_id = ANY(:ids)"),
            {"ids": legacy_ids},
        )
        if _table_exists("zone_products"):
            conn.execute(
                sa.text("DELETE FROM zone_products WHERE zone_id = ANY(:ids)"),
                {"ids": legacy_ids},
            )
        # zone_tags ON DELETE CASCADE, furniture_items SET NULL — safe.
        conn.execute(
            sa.text("DELETE FROM store_zones WHERE id = ANY(:ids)"),
            {"ids": legacy_ids},
        )


def downgrade() -> None:
    # On retire les colonnes de règles ; le remap des zones n'est pas annulé
    # (l'ancien set de 11 zones est obsolète — restaurer depuis backup au besoin).
    for col, _ in reversed(_COLUMNS):
        op.execute(sa.text(f"ALTER TABLE store_zones DROP COLUMN IF EXISTS {col}"))
