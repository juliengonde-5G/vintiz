"""Seed a dedicated set of POS test products and generate a markdown
document with scannable Code128 barcode images.

Purpose
-------
For the first hardware test run of the POS setup (iPad + SumUp Solo TPE +
thermal receipt printer + cash drawer + USB barcode scanner), this script:

  1. Creates 15 deterministic products with predictable barcodes ``TEST0001``
     … ``TEST0015`` in a range of price points (0,50 € – 79 €) and categories
     (femme, homme, enfant, accessoire).
  2. Generates a Code128 PNG per product in ``docs/test_barcodes/``.
  3. Writes ``docs/POS_TEST_BARCODES.md`` embedding each barcode image,
     ready to display on a second screen (or printed on paper) for scanning.

Usage
-----

    PYTHONPATH=apps/api python scripts/seed_test_products.py

The script is idempotent: products are upserted by barcode; PNGs and the
markdown file are regenerated every run.
"""
from __future__ import annotations

import asyncio
import io
import sys
from pathlib import Path

# Ensure the api app is importable. Two layouts supported:
#   - Monorepo dev : /repo/apps/api/app/… → add /repo/apps/api to sys.path
#   - Docker image : /app/app/…           → add /app to sys.path
_here = Path(__file__).resolve().parent
for candidate in (_here.parent / "apps" / "api", _here.parent):
    if (candidate / "app" / "core" / "database.py").exists():
        if str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))
        break

import barcode as barcode_lib
from barcode.writer import ImageWriter

# SQLAlchemy / app-model imports are deferred so doc generation works even
# without the API dependencies installed (see ``regenerate_docs_only``).


REPO_ROOT = Path(__file__).resolve().parent.parent
BARCODES_DIR = REPO_ROOT / "docs" / "test_barcodes"
DOC_PATH = REPO_ROOT / "docs" / "POS_TEST_BARCODES.md"


# Test fixture: 15 products spanning price points, genders, categories.
# Barcodes are short, deterministic Code128 strings for predictable scans.
TEST_PRODUCTS = [
    # barcode,   name,                                   brand,           color,       size,   gender,   cat_hint,       price
    ("TEST0001", "Sac boutique Vintiz",                  "Vintiz",        "Kraft",     None,    "femme",  "Accessoire",    0.25),
    ("TEST0002", "T-shirt coton Uniqlo",                 "Uniqlo",        "Blanc",     "M",     "femme",  "Haut",          9.00),
    ("TEST0003", "Jean slim Zara",                       "Zara",          "Bleu",      "38",    "femme",  "Pantalon",     19.00),
    ("TEST0004", "Robe fleurie Sandro",                  "Sandro",        "Rose",      "S",     "femme",  "Robe",         49.00),
    ("TEST0005", "Blouse soie Maje",                     "Maje",          "Ivoire",    "36",    "femme",  "Haut",         39.00),
    ("TEST0006", "Veste en jean Levi's",                 "Levi's",        "Bleu",      "M",     "femme",  "Manteau",      29.00),
    ("TEST0007", "Pull cachemire A.P.C.",                "A.P.C.",        "Camel",     "S",     "femme",  "Haut",         59.00),
    ("TEST0008", "Chemise lin Cos",                      "Cos",           "Blanc",     "L",     "homme",  "Haut",         19.00),
    ("TEST0009", "Pantalon chino Massimo Dutti",         "Massimo Dutti", "Beige",     "46",    "homme",  "Pantalon",     25.00),
    ("TEST0010", "Manteau laine Ralph Lauren",           "Ralph Lauren",  "Marine",    "L",     "homme",  "Manteau",      79.00),
    ("TEST0011", "Sweat Petit Bateau 6 ans",             "Petit Bateau",  "Rose",      "6 ans", "enfant", "Haut",          9.00),
    ("TEST0012", "Robe Jacadi 4 ans",                    "Jacadi",        "Bleu",      "4 ans", "enfant", "Robe",         15.00),
    ("TEST0013", "Baskets enfant Bonpoint",              "Bonpoint",      "Blanc",     "28",    "enfant", "Chaussures",   19.00),
    ("TEST0014", "Foulard soie Hermès",                  "Hermès",        "Multi",     None,    "femme",  "Accessoire",   79.00),
    ("TEST0015", "Ceinture cuir The Kooples",            "The Kooples",   "Noir",      "90",    "homme",  "Accessoire",   15.00),
]


def generate_code128_png(data: str) -> bytes:
    """Return PNG bytes of a Code128 barcode for ``data``."""
    code = barcode_lib.get("code128", data, writer=ImageWriter())
    buf = io.BytesIO()
    code.write(buf, options={
        "module_height": 14.0,
        "module_width": 0.30,
        "font_size": 10,
        "text_distance": 3.0,
        "quiet_zone": 4.0,
        "write_text": True,
    })
    buf.seek(0)
    return buf.getvalue()


async def _pick_category(db, gender: str, hint: str):
    """Return the best-matching category for ``(gender, hint)``.

    Falls back to the first category of the requested gender, or any category.
    """
    from sqlalchemy import select
    from app.models.product import Category, Gender

    gender_enum = {
        "femme": Gender.femme,
        "homme": Gender.homme,
        "enfant": Gender.enfant,
    }.get(gender, Gender.mixte)

    result = await db.execute(select(Category).where(Category.gender == gender_enum))
    cats = list(result.scalars().all())
    if not cats:
        result = await db.execute(select(Category).limit(1))
        return result.scalar_one_or_none()
    for c in cats:
        if hint.lower() in c.name.lower():
            return c
    return cats[0]


async def _pick_zone(db):
    from sqlalchemy import select
    from app.models.store import StoreZone

    result = await db.execute(select(StoreZone).limit(1))
    return result.scalar_one_or_none()


async def upsert_test_products(db):
    """Create or update the TEST_PRODUCTS set. Returns the list of products."""
    from sqlalchemy import select
    from app.models.product import Product, ProductStatus

    zone = await _pick_zone(db)
    products: list = []

    for (bc, name, brand, color, size, gender, cat_hint, price) in TEST_PRODUCTS:
        category = await _pick_category(db, gender, cat_hint)
        if category is None:
            print(f"[warn] No category found for {bc} — skipping")
            continue

        result = await db.execute(select(Product).where(Product.barcode == bc))
        existing = result.scalar_one_or_none()

        if existing:
            existing.name = name
            existing.brand = brand
            existing.color = color
            existing.size = size
            existing.sale_price = price
            existing.purchase_price = round(price * 0.35, 2)
            existing.category_id = category.id
            existing.status = ProductStatus.stock
            existing.zone_id = zone.id if zone else None
            existing.condition = "Très bon état"
            existing.description = f"Produit test POS — {name}"
            products.append(existing)
            print(f"[upd] {bc} → {name}  {price:.2f} €")
        else:
            p = Product(
                barcode=bc,
                name=name,
                brand=brand,
                color=color,
                size=size,
                sale_price=price,
                purchase_price=round(price * 0.35, 2),
                category_id=category.id,
                status=ProductStatus.stock,
                zone_id=zone.id if zone else None,
                condition="Très bon état",
                description=f"Produit test POS — {name}",
            )
            db.add(p)
            products.append(p)
            print(f"[new] {bc} → {name}  {price:.2f} €")

    await db.flush()
    return products


def write_barcodes_and_markdown() -> None:
    """Generate all PNGs under docs/test_barcodes/ and the markdown doc."""
    BARCODES_DIR.mkdir(parents=True, exist_ok=True)

    lines: list[str] = [
        "# Vintiz POS — Codes-barres de test",
        "",
        "Série de 15 produits de test prêts pour le premier passage caisse avec",
        "le matériel reçu : **iPad + douchette Inateck 160B + imprimante ticket",
        "80 mm + tiroir RJ11 + TPE SumUp Solo**.",
        "",
        "## Préparation (une fois)",
        "",
        "1. **Backend SumUp** — dans `.env` :",
        "",
        "   ```env",
        "   SUMUP_ENVIRONMENT=sandbox",
        "   SUMUP_API_KEY=              # vide = sandbox simulé auto",
        "   SUMUP_MERCHANT_CODE=",
        "   SUMUP_SANDBOX_AUTO_DELAY_SEC=5   # 0 = approbation manuelle",
        "   ```",
        "",
        "   - **Sans clé** : sandbox simulé en mémoire, événements visibles dans",
        "     *Paramètres > Paiement*, approve/decline manuel disponible.",
        "   - **Avec clé** : appels réels vers l'API SumUp sandbox.",
        "",
        "2. **Seed** — créer/réassigner les 15 produits et régénérer ce doc :",
        "",
        "   ```bash",
        "   PYTHONPATH=apps/api python scripts/seed_test_products.py",
        "   # ou juste régénérer images + markdown sans DB :",
        "   python scripts/seed_test_products.py --docs-only",
        "   ```",
        "",
        "3. **Douchette Inateck 160B** — branchement USB, mode HID clavier par",
        "   défaut (aucune config). Elle tape le code lu puis envoie Entrée.",
        "   Vérifier dans le manuel que le suffixe *CR/Enter* est bien activé.",
        "",
        "4. **Imprimante + tiroir** — l'imprimante thermique 80 mm se connecte à",
        "   l'iPad en AirPrint (Wi-Fi). Le tiroir-caisse se branche sur le port",
        "   **RJ11** (ou DK) de l'imprimante. Dans le driver imprimante, activer",
        "   \"open cash drawer on print\".",
        "",
        "5. **Caisse** — ouvrir la caisse via */pos* → bouton **Ouvrir la caisse**",
        "   (saisir le fond), puis effectuer les ventes.",
        "",
        "## Procédure de test",
        "",
        "- **Scan** : poser la douchette sur un code-barres ci-dessous → le",
        "  produit s'ajoute au panier (champ recherche auto-focus).",
        "- **Encaisser** : bouton Encaisser → choisir moyen de paiement :",
        "  - *Espèces* → numpad tactile + monnaie à rendre.",
        "  - *Carte (CB)* → le TPE SumUp Solo demande la carte (en sandbox :",
        "    auto-validation après 5 s, ou approve/decline manuel dans Settings).",
        "  - *Chèque* → saisie manuelle.",
        "- **Ticket** : à validation, le ticket s'affiche. Cliquer **Imprimer**",
        "  → impression papier + ouverture automatique du tiroir-caisse.",
        "- **Z report** : en fin de journée, bouton **Fermer la caisse** →",
        "  saisie fond final → rapport Z généré.",
        "",
        "> Tous les codes sont **Code 128**, lisibles par n'importe quelle",
        "> douchette USB HID dont l'Inateck 160B.",
        "",
        "---",
        "",
        "## Les 15 produits de test",
        "",
    ]

    for i, (bc, name, brand, color, size, gender, cat_hint, price) in enumerate(TEST_PRODUCTS, start=1):
        png = generate_code128_png(bc)
        png_path = BARCODES_DIR / f"{bc}.png"
        png_path.write_bytes(png)

        rel = png_path.relative_to(DOC_PATH.parent).as_posix()
        size_str = f"taille {size}" if size else "—"

        lines += [
            f"### {i}. {name}",
            "",
            f"- **Code-barres** : `{bc}`",
            f"- **Marque** : {brand}",
            f"- **Couleur** : {color}",
            f"- **Taille** : {size_str}",
            f"- **Genre** : {gender}",
            f"- **Catégorie** : {cat_hint}",
            f"- **Prix TTC** : **{price:.2f} €**",
            "",
            f"![{bc}]({rel})",
            "",
            "---",
            "",
        ]

    lines += [
        "## Scénarios de test suggérés",
        "",
        "| # | Scénario | Articles | Paiement attendu |",
        "|---|----------|----------|------------------|",
        "| 1 | Vente simple espèces | TEST0002 | 9,00 € espèces + rendu monnaie |",
        "| 2 | Vente CB sandbox | TEST0004 + TEST0005 | 88,00 € carte via SumUp Solo |",
        "| 3 | Panier mixte + sac | TEST0003 + TEST0001 | 19,25 € au choix |",
        "| 4 | Remise -20 % | TEST0010 avec remise 20 % | 63,20 € CB |",
        "| 5 | Article manuel | Saisie libre \"retouche\" 5 € | 5,00 € espèces |",
        "| 6 | Fidélité | Client existant + TEST0007 | CB avec points |",
        "| 7 | Ouverture / fermeture caisse | — | Fond initial + Z report |",
        "| 8 | Approve/decline manuel CB | TEST0006 + CB | Valider dans Settings > Paiement |",
        "",
        "## Dépannage",
        "",
        "- **La douchette ne scanne rien** : vérifier que le champ recherche est",
        "  focalisé (il l'est par défaut à l'ouverture de `/pos`) ; l'Inateck 160B",
        "  envoie les caractères + *Enter* suffixé — vérifier la config du",
        "  suffixe dans son manuel si le scan ne déclenche pas l'ajout panier.",
        "- **Le produit n'est pas trouvé** : relancer le seed sans `--docs-only` ;",
        "  vérifier que l'API tourne sur `NEXT_PUBLIC_API_URL`.",
        "- **Le ticket ne s'imprime pas** : autoriser les pop-ups pour le domaine",
        "  (Safari → Réglages → Sites web → Fenêtres pop-up → Autoriser).",
        "- **Le tiroir ne s'ouvre pas** : configurer \"open drawer on print\" dans",
        "  le driver de l'imprimante ; sans cette option il faudra un kick ESC/POS.",
        "- **Le TPE ne réagit pas** : sans `SUMUP_API_KEY`, le mode est sandbox",
        "  simulé — le checkout auto-valide après `SUMUP_SANDBOX_AUTO_DELAY_SEC`",
        "  secondes. Réglable sur 0 pour forcer l'approbation manuelle.",
        "- **Le paiement CB reste PENDING** : aller dans *Paramètres > Paiement*",
        "  → event log → cliquer *Approuver* ou *Refuser* sur le checkout en cours.",
        "",
    ]

    DOC_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"[done] Wrote {DOC_PATH.relative_to(REPO_ROOT)} "
          f"({len(TEST_PRODUCTS)} products, "
          f"PNGs in {BARCODES_DIR.relative_to(REPO_ROOT)}/).")


async def main() -> None:
    print("=" * 55)
    print("  Vintiz — Seed test products for hardware POS run")
    print("=" * 55)

    from app.core.database import async_session, engine

    async with async_session() as db:
        try:
            await upsert_test_products(db)
            await db.commit()
        except Exception as e:
            await db.rollback()
            print(f"\n[error] DB seed failed: {e}")
            import traceback
            traceback.print_exc()
            # Still generate the doc — it does not depend on the DB.
            write_barcodes_and_markdown()
            raise

    write_barcodes_and_markdown()
    await engine.dispose()
    print("\nAll set. Open the POS on iPad and scan away.")


if __name__ == "__main__":
    # If called with --docs-only, regenerate only the barcode PNGs + markdown.
    if len(sys.argv) > 1 and sys.argv[1] in ("--docs-only", "--docs"):
        write_barcodes_and_markdown()
    else:
        asyncio.run(main())
