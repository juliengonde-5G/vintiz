"""Remap store_zones to the 11 zones from plan.jpg (Petits Prix, Extra,
Chaussures F/H, Portants Standards 1/2, Hommes, Tendance, Vitrine).

Revision ID: 0026
Revises: 0025
Create Date: 2026-04-27

Idempotente :
- si une zone porte exactement le nouveau nom, on met à jour ses coordonnees
  + capacite + couleur + photo_url + ordre, on ne touche pas a son id
  (les `products.zone_id` restent valides) ;
- sinon on cree la zone ;
- les anciennes zones (Vitrine gauche, Mur gauche, …) sont detachees des
  produits (Product.zone_id := NULL) puis supprimees, ainsi que leurs
  ZoneProduct, leurs ZoneTag et leurs FurnitureItem (ON DELETE / SET NULL).
"""

from alembic import op
import sqlalchemy as sa


revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# Cible : 11 zones exactes — même contenu que ai_mapping.DEFAULT_ZONES.
# Ne pas dériver via import : la migration doit rester autoportante.
# ---------------------------------------------------------------------------
TARGET_ZONES = [
    ("Petits Prix 1",        "Mur du fond cote entree — femme, prix doux",      200, "#26A695", 72, 2,  24, 12, "rect",    "shirt",    1,  "/zones/standard-1.jpeg"),
    ("Petits Prix 2",        "Mur du fond centre — femme, prix doux",           200, "#26A695", 46, 2,  24, 12, "rect",    "shirt",    2,  "/zones/standard-2.jpeg"),
    ("Extra 1",              "Mur du fond — selection extra femme",             150, "#008678", 24, 4,  20, 14, "rect",    "shirt",    3,  "/zones/extra-1.jpeg"),
    ("Extra 2",              "Retour mur — selection extra femme",              150, "#008678", 12, 18, 12, 22, "rect",    "shirt",    4,  "/zones/extra-2.jpeg"),
    ("Chaussures F",         "Mur gauche pres des cabines — chaussures femme",   30, "#FFC5DF", 12, 42, 12, 18, "rect",    "bag",      5,  "/zones/chaussures-f.jpeg"),
    ("Portants Standards 1", "Portant central femme (haut)",                    120, "#FF97C0", 44, 28, 22, 18, "rounded", "grid",     6,  None),
    ("Portants Standards 2", "Portant central femme (bas)",                     120, "#FF97C0", 22, 58, 22, 18, "rounded", "grid",     7,  None),
    ("Chaussures H",         "Coin facade gauche — chaussures homme",            30, "#3B82F6", 22, 80, 14, 15, "rect",    "bag",      8,  "/zones/chaussures-h.jpeg"),
    ("Hommes",               "Mur facade — collection homme complete",          150, "#1E3A8A", 38, 82, 18, 13, "rect",    "shirt",    9,  "/zones/hommes.jpeg"),
    ("Tendance",             "Tete de gondole facade — tendance femme",         200, "#CC4889", 58, 80, 24, 15, "rounded", "sparkles", 10, "/zones/tendance.jpeg"),
    ("Vitrine",              "Vitrine devanture cote entree — exposition uniquement", 8, "#006B61", 84, 80, 12, 15, "rounded", "star",     11, "/zones/vitrine.jpeg"),
]


def _table_exists(name: str) -> bool:
    conn = op.get_bind()
    return conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables WHERE table_name = :t"
        ),
        {"t": name},
    ).fetchone() is not None


def upgrade() -> None:
    if not _table_exists("store_zones"):
        # Bootstrap incomplet : on laisse seed_data / DEFAULT_ZONES creer
        # la table au premier import.
        return

    conn = op.get_bind()
    target_names = [row[0] for row in TARGET_ZONES]

    # 1. Upsert chaque zone cible.
    for (name, desc, cap, color, px, py, w, h, shape, icon, order, photo) in TARGET_ZONES:
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
                         display_order, photo_url, created_at, updated_at)
                    VALUES
                        (gen_random_uuid(), :n, :d, :cap, :color,
                         :px, :py, :w, :h, :shape, :icon,
                         :ord, :photo, now(), now())
                    """
                ),
                {
                    "n": name, "d": desc, "cap": cap, "color": color,
                    "px": px, "py": py, "w": w, "h": h,
                    "shape": shape, "icon": icon, "ord": order, "photo": photo,
                },
            )
        else:
            conn.execute(
                sa.text(
                    """
                    UPDATE store_zones
                       SET description    = :d,
                           capacity       = :cap,
                           color_code     = :color,
                           pos_x          = :px,
                           pos_y          = :py,
                           width          = :w,
                           height         = :h,
                           shape          = :shape,
                           icon           = :icon,
                           display_order  = :ord,
                           photo_url      = COALESCE(:photo, photo_url),
                           updated_at     = now()
                     WHERE name = :n
                    """
                ),
                {
                    "n": name, "d": desc, "cap": cap, "color": color,
                    "px": px, "py": py, "w": w, "h": h,
                    "shape": shape, "icon": icon, "ord": order, "photo": photo,
                },
            )

    # 2. Detacher tout produit qui pointe vers une ancienne zone, puis
    #    supprimer ses children (ZoneProduct, ZoneTag, FurnitureItem) et
    #    enfin la zone elle-meme.
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
        # zone_tags has ON DELETE CASCADE, furniture_items SET NULL — safe.
        conn.execute(
            sa.text("DELETE FROM store_zones WHERE id = ANY(:ids)"),
            {"ids": legacy_ids},
        )


def downgrade() -> None:
    # Pas de downgrade — la liste « 7 zones » est obsolete (plan boutique
    # different). Si besoin de revenir en arriere, restaurer depuis backup.
    pass
