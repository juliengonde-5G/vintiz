#!/usr/bin/env python3
"""Reconstitue la liste des articles scannés à partir des logs d'accès.

Les scans douchette au POS frappent ``GET /api/inventory/products/by-barcode/
{code}`` — journalisé par le RequestIdMiddleware. Ce script lit ces lignes de
log sur l'ENTRÉE STANDARD, en extrait les codes-barres (dans l'ordre, doublons
consécutifs dédupliqués), puis résout chacun contre le catalogue pour afficher
nom + prix + statut. Idéal pour retrouver le contenu d'un encaissement orphelin.

Read-only. Ne modifie rien.

Usage — on pipe les logs de l'hôte dans le conteneur :

    docker logs vintiz-api --since 2026-07-17T09:28:00Z --until 2026-07-17T09:31:10Z 2>&1 \\
      | docker exec -i vintiz-api python scripts/scan_trail.py

    # Ou sur un fichier de log déjà récupéré :
    cat access.log | PYTHONPATH=apps/api python scripts/scan_trail.py

    # Inclure aussi les recherches texte (champ POS), pas seulement la douchette :
    docker logs vintiz-api --since ... 2>&1 | docker exec -i vintiz-api \\
      python scripts/scan_trail.py --with-search
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path
from urllib.parse import unquote

# Rendre ``import app.core...`` fonctionnel en dev ET en Docker (/app).
_HERE = Path(__file__).resolve()
for _candidate in (
    _HERE.parents[1] / "apps" / "api",   # layout dev (repo)
    _HERE.parents[1],                    # layout Docker prod (/app)
):
    if (_candidate / "app" / "core" / "database.py").exists():
        sys.path.insert(0, str(_candidate))
        break
else:
    raise SystemExit(
        "scan_trail: package `app` introuvable — vérifié "
        f"{_HERE.parents[1] / 'apps' / 'api'} et {_HERE.parents[1]}"
    )

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import selectinload  # noqa: E402

from app.core.database import async_session  # noqa: E402
from app.models.permanent_item import PermanentItem  # noqa: E402
from app.models.product import Product  # noqa: E402

# GET /api/inventory/products/by-barcode/<code>  (code jusqu'au prochain / ? espace)
_BARCODE_RE = re.compile(r"/api/inventory/products/by-barcode/([^/?\s\"']+)")
# GET /api/inventory/products/search?q=<code>
_SEARCH_RE = re.compile(r"/api/inventory/products/search\?[^\s\"']*\bq=([^&\s\"']+)")


def _extract(lines: list[str], with_search: bool) -> list[str]:
    """Extrait les codes scannés dans l'ordre, doublons CONSÉCUTIFS retirés."""
    ordered: list[str] = []
    for line in lines:
        for m in _BARCODE_RE.finditer(line):
            ordered.append(unquote(m.group(1)).strip())
        if with_search:
            for m in _SEARCH_RE.finditer(line):
                ordered.append(unquote(m.group(1)).strip())
    # Dédup des répétitions immédiates (la douchette envoie parfois 2x).
    deduped: list[str] = []
    for code in ordered:
        if code and (not deduped or deduped[-1] != code):
            deduped.append(code)
    return deduped


async def _resolve(db, code: str):
    """Résolution tolérante, alignée sur l'endpoint by-barcode."""
    variants = [code, code.replace("=", "-"), code.upper()]
    for needle in variants:
        prod = (
            await db.execute(
                select(Product)
                .options(selectinload(Product.category))
                .where(Product.barcode.ilike(needle))
                .limit(1)
            )
        ).scalar_one_or_none()
        if prod is not None:
            return ("product", prod)
    for needle in variants:
        perm = (
            await db.execute(
                select(PermanentItem).where(PermanentItem.barcode.ilike(needle)).limit(1)
            )
        ).scalar_one_or_none()
        if perm is not None:
            return ("permanent", perm)
    return (None, None)


async def run(with_search: bool) -> None:
    raw = sys.stdin.read()
    if not raw.strip():
        print(
            "Rien reçu sur l'entrée standard. Pipez les logs, ex. :\n"
            "  docker logs vintiz-api --since 2026-07-17T09:28:00Z "
            "--until 2026-07-17T09:31:10Z 2>&1 | docker exec -i vintiz-api "
            "python scripts/scan_trail.py"
        )
        return

    codes = _extract(raw.splitlines(), with_search)
    if not codes:
        print(
            "Aucun scan by-barcode"
            + (" ni recherche" if with_search else "")
            + " trouvé dans les lignes fournies."
            "\n→ Vérifiez la fenêtre horaire (UTC !) et que les logs de la "
            "veille ne sont pas déjà rotés."
        )
        return

    print(f"{len(codes)} scan(s) distinct(s) dans l'ordre :\n")
    print(f"{'#':>2}  {'CODE SCANNÉ':<20} {'PRIX':>7}  {'STATUT':<14} ARTICLE")
    print("─" * 96)

    total = 0.0
    async with async_session() as db:
        for i, code in enumerate(codes, 1):
            kind, obj = await _resolve(db, code)
            if kind == "product":
                cat = obj.category.name if obj.category else "?"
                total += float(obj.sale_price)
                print(
                    f"{i:>2}  {code:<20} {float(obj.sale_price):>7.2f}  "
                    f"{obj.status.value:<14} « {obj.name} » · {cat}"
                    + (f" · {obj.brand}" if obj.brand else "")
                    + (f" · T.{obj.size}" if obj.size else "")
                )
            elif kind == "permanent":
                total += float(obj.sale_price)
                print(
                    f"{i:>2}  {code:<20} {float(obj.sale_price):>7.2f}  "
                    f"{'permanent':<14} « {obj.name} » (article permanent)"
                )
            else:
                print(f"{i:>2}  {code:<20} {'—':>7}  {'INTROUVABLE':<14} (aucun produit)")
    print("─" * 96)
    print(f"    Somme des prix pleins des articles trouvés : {total:.2f} €")
    print(
        "\nNB : c'est la somme des PRIX PLEINS. Si une remise / un Solde "
        "s'appliquait, le total payé sera inférieur — croisez avec le montant "
        "de l'encaissement orphelin (find_price_candidates.py)."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reconstitue les articles scannés depuis les logs d'accès (stdin, read-only)"
    )
    parser.add_argument(
        "--with-search", action="store_true",
        help="Inclure aussi les recherches texte /products/search?q=, pas que la douchette",
    )
    args = parser.parse_args()
    asyncio.run(run(with_search=args.with_search))


if __name__ == "__main__":
    main()
