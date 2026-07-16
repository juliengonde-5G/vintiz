"""Seed 50 demo products via the /from-photo orchestration (L3.3).

Calls ``POST /api/inventory/products/from-photo`` for 50 hot-linked image
URLs covering 5 brand "personas" (10 each) :
- H&M (mainstream)
- Celio (homme casual)
- Kiabi (enfant + family)
- Lacoste (premium polo + chemise)
- Dior (luxury archive)

All products are created with ``is_test=True`` so they survive only until
``scripts/purge_test_data.py`` is run before public opening.

Important — copyright disclaimer
--------------------------------
Image URLs are referenced (hot-linked), not copied. The DB stores only the
URL. These products MUST be purged before public launch to avoid any
liability. For production, switch to Unsplash / Pexels (open licence) or
your own product photography.

Usage
-----

    # Local dev (API on http://localhost:8000) :
    python scripts/seed_demo_products.py

    # Custom base URL + token :
    VINTIZ_API_URL=https://api.vintiz.fr \\
    VINTIZ_API_TOKEN=eyJhbG... \\
    python scripts/seed_demo_products.py

The script is **idempotent** : barcode collisions cause regeneration via
``product_intake._generate_barcode``, so re-runs add new fiches each time
(use purge first to start clean).

Output
------
- 50 fiches Product (is_test=True) avec attributs Vision auto-remplis
- ``scripts/output/seed_demo_report.json`` détail vision_used, score, zone
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import httpx


# 50 image URLs grouped by brand. To regenerate : pick fresh URLs from each
# brand's e-shop product pages (the URL must respond with Content-Type:
# image/*). Avoid signed URLs that expire.
# 50 photos Unsplash de mode (licence Unsplash, libre — pas de risque copyright)
# regroupées par persona catégorie. Vision extraira de vrais attributs (type,
# couleur, matière) — la marque sera souvent null car Unsplash n'a pas
# d'étiquette visible, ce qui est exactement le comportement attendu en
# boutique seconde main quand l'étiquette a été retirée.
#
# Le script HEAD-vérifie chaque URL avant d'appeler /from-photo (Vision coûte ~5 €
# pour les 50 calls). Si une URL renvoie != 200, l'entrée est skippée.
DEMO_PRODUCTS: list[dict] = [
    # --- Robes (7) ---
    {"category_persona": "robe", "url": "https://images.unsplash.com/photo-1595777457583-95e059d581b8?w=800&q=80", "price_hint": 35.0},
    {"category_persona": "robe", "url": "https://images.unsplash.com/photo-1572804013309-59a88b7e92f1?w=800&q=80", "price_hint": 45.0},
    {"category_persona": "robe", "url": "https://images.unsplash.com/photo-1496747611176-843222e1e57c?w=800&q=80", "price_hint": 28.0},
    {"category_persona": "robe", "url": "https://images.unsplash.com/photo-1566174053879-31528523f8ae?w=800&q=80", "price_hint": 55.0},
    {"category_persona": "robe", "url": "https://images.unsplash.com/photo-1539109136881-3be0616acf4b?w=800&q=80", "price_hint": 39.0},
    {"category_persona": "robe", "url": "https://images.unsplash.com/photo-1623609163859-ca93c959b98a?w=800&q=80", "price_hint": 32.0},
    {"category_persona": "robe", "url": "https://images.unsplash.com/photo-1583846783214-7229a91b20ed?w=800&q=80", "price_hint": 49.0},

    # --- Manteaux / vestes (7) ---
    {"category_persona": "manteau", "url": "https://images.unsplash.com/photo-1544022613-e87ca75a784a?w=800&q=80", "price_hint": 65.0},
    {"category_persona": "manteau", "url": "https://images.unsplash.com/photo-1591047139829-d91aecb6caea?w=800&q=80", "price_hint": 75.0},
    {"category_persona": "manteau", "url": "https://images.unsplash.com/photo-1539533018447-63fcce2678e3?w=800&q=80", "price_hint": 58.0},
    {"category_persona": "manteau", "url": "https://images.unsplash.com/photo-1548883354-94bcfe321cbb?w=800&q=80", "price_hint": 69.0},
    {"category_persona": "manteau", "url": "https://images.unsplash.com/photo-1551488831-00ddcb6c6bd3?w=800&q=80", "price_hint": 49.0},
    {"category_persona": "manteau", "url": "https://images.unsplash.com/photo-1520975916090-3105956dac38?w=800&q=80", "price_hint": 79.0},
    {"category_persona": "manteau", "url": "https://images.unsplash.com/photo-1577900232427-18219b9166a0?w=800&q=80", "price_hint": 42.0},

    # --- Pulls / chemises (7) ---
    {"category_persona": "pull", "url": "https://images.unsplash.com/photo-1576566588028-4147f3842f27?w=800&q=80", "price_hint": 25.0},
    {"category_persona": "pull", "url": "https://images.unsplash.com/photo-1584917865442-de89df76afd3?w=800&q=80", "price_hint": 32.0},
    {"category_persona": "pull", "url": "https://images.unsplash.com/photo-1620799140408-edc6dcb6d633?w=800&q=80", "price_hint": 28.0},
    {"category_persona": "pull", "url": "https://images.unsplash.com/photo-1434389677669-e08b4cac3105?w=800&q=80", "price_hint": 22.0},
    {"category_persona": "pull", "url": "https://images.unsplash.com/photo-1611312449412-6cefac5dc3e4?w=800&q=80", "price_hint": 35.0},
    {"category_persona": "pull", "url": "https://images.unsplash.com/photo-1602810318383-e386cc2a3ccf?w=800&q=80", "price_hint": 19.0},
    {"category_persona": "pull", "url": "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=800&q=80", "price_hint": 24.0},

    # --- Pantalons / jupes (7) ---
    {"category_persona": "pantalon", "url": "https://images.unsplash.com/photo-1542272604-787c3835535d?w=800&q=80", "price_hint": 35.0},
    {"category_persona": "pantalon", "url": "https://images.unsplash.com/photo-1541099649105-f69ad21f3246?w=800&q=80", "price_hint": 29.0},
    {"category_persona": "pantalon", "url": "https://images.unsplash.com/photo-1582418702059-97ebafb35d09?w=800&q=80", "price_hint": 38.0},
    {"category_persona": "pantalon", "url": "https://images.unsplash.com/photo-1604176354204-9268737828e4?w=800&q=80", "price_hint": 42.0},
    {"category_persona": "pantalon", "url": "https://images.unsplash.com/photo-1591195853828-11db59a44f6b?w=800&q=80", "price_hint": 26.0},
    {"category_persona": "pantalon", "url": "https://images.unsplash.com/photo-1594633312681-425c7b97ccd1?w=800&q=80", "price_hint": 32.0},
    {"category_persona": "pantalon", "url": "https://images.unsplash.com/photo-1551854838-212c9a5e29fb?w=800&q=80", "price_hint": 24.0},

    # --- Chaussures (8) ---
    {"category_persona": "chaussures", "url": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=800&q=80", "price_hint": 45.0},
    {"category_persona": "chaussures", "url": "https://images.unsplash.com/photo-1525966222134-fcfa99b8ae77?w=800&q=80", "price_hint": 39.0},
    {"category_persona": "chaussures", "url": "https://images.unsplash.com/photo-1606107557195-0e29a4b5b4aa?w=800&q=80", "price_hint": 55.0},
    {"category_persona": "chaussures", "url": "https://images.unsplash.com/photo-1595950653106-6c9ebd614d3a?w=800&q=80", "price_hint": 49.0},
    {"category_persona": "chaussures", "url": "https://images.unsplash.com/photo-1551107696-a4b0c5a0d9a2?w=800&q=80", "price_hint": 35.0},
    {"category_persona": "chaussures", "url": "https://images.unsplash.com/photo-1560769629-975ec94e6a86?w=800&q=80", "price_hint": 42.0},
    {"category_persona": "chaussures", "url": "https://images.unsplash.com/photo-1543163521-1bf539c55dd2?w=800&q=80", "price_hint": 65.0},
    {"category_persona": "chaussures", "url": "https://images.unsplash.com/photo-1549298916-b41d501d3772?w=800&q=80", "price_hint": 52.0},

    # --- Sacs (7) ---
    {"category_persona": "sac", "url": "https://images.unsplash.com/photo-1548036328-c9fa89d128fa?w=800&q=80", "price_hint": 48.0},
    {"category_persona": "sac", "url": "https://images.unsplash.com/photo-1591561954557-26941169b49e?w=800&q=80", "price_hint": 65.0},
    {"category_persona": "sac", "url": "https://images.unsplash.com/photo-1590874103328-eac38a683ce7?w=800&q=80", "price_hint": 39.0},
    {"category_persona": "sac", "url": "https://images.unsplash.com/photo-1566150905458-1bf1fc113f0d?w=800&q=80", "price_hint": 72.0},
    {"category_persona": "sac", "url": "https://images.unsplash.com/photo-1564422170194-896b89110ef8?w=800&q=80", "price_hint": 45.0},
    {"category_persona": "sac", "url": "https://images.unsplash.com/photo-1605733513597-a8f8341084e6?w=800&q=80", "price_hint": 58.0},
    {"category_persona": "sac", "url": "https://images.unsplash.com/photo-1559563458-527698bf5295?w=800&q=80", "price_hint": 55.0},

    # --- Accessoires (lunettes / foulards / ceintures / chapeaux) (7) ---
    {"category_persona": "accessoire", "url": "https://images.unsplash.com/photo-1511499767150-a48a237f0083?w=800&q=80", "price_hint": 18.0},
    {"category_persona": "accessoire", "url": "https://images.unsplash.com/photo-1572635196237-14b3f281503f?w=800&q=80", "price_hint": 22.0},
    {"category_persona": "accessoire", "url": "https://images.unsplash.com/photo-1556306535-0f09a537f0a3?w=800&q=80", "price_hint": 15.0},
    {"category_persona": "accessoire", "url": "https://images.unsplash.com/photo-1606760227091-3dd870d97f1d?w=800&q=80", "price_hint": 28.0},
    {"category_persona": "accessoire", "url": "https://images.unsplash.com/photo-1601924994987-69e26d50dc26?w=800&q=80", "price_hint": 19.0},
    {"category_persona": "accessoire", "url": "https://images.unsplash.com/photo-1590736969955-71cc94901144?w=800&q=80", "price_hint": 24.0},
    {"category_persona": "accessoire", "url": "https://images.unsplash.com/photo-1521369909029-2afed882baee?w=800&q=80", "price_hint": 16.0},
]


API_URL = os.getenv("VINTIZ_API_URL", "http://localhost:8000")
API_TOKEN = os.getenv("VINTIZ_API_TOKEN", "")
TEST_USERNAME = os.getenv("VINTIZ_TEST_USERNAME", "")
TEST_PASSWORD = os.getenv("VINTIZ_TEST_PASSWORD", "")


async def login_admin(client: httpx.AsyncClient) -> str:
    """Fallback login with explicitly supplied non-production credentials."""
    if not TEST_USERNAME or not TEST_PASSWORD:
        raise RuntimeError(
            "Set VINTIZ_API_TOKEN or VINTIZ_TEST_USERNAME/VINTIZ_TEST_PASSWORD"
        )
    r = await client.post(
        f"{API_URL}/api/auth/login",
        data={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    )
    r.raise_for_status()
    return r.json()["access_token"]


async def head_check(client: httpx.AsyncClient, url: str) -> bool:
    """Pre-flight HEAD check to avoid wasting Vision calls on broken URLs."""
    try:
        r = await client.head(url, follow_redirects=True, timeout=8,
                              headers={"User-Agent": "Mozilla/5.0 (Vintiz Seed)"})
        return r.status_code == 200
    except Exception:
        return False


async def main() -> int:
    """Iterate through DEMO_PRODUCTS and POST each to /from-photo.

    Pré-flight HEAD sur chaque URL pour éviter les appels Vision (~5€/50)
    sur des URLs cassées. Les entrées avec URL 404 sont reportées sans
    appel API.
    """
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    async with httpx.AsyncClient(timeout=60) as client:
        token = API_TOKEN or await login_admin(client)
        headers = {"Authorization": f"Bearer {token}"}

        # Pre-flight : valide toutes les URLs en parallèle pour échouer vite.
        print(f"Pre-flight HEAD check on {len(DEMO_PRODUCTS)} URLs...")
        head_results = await asyncio.gather(
            *(head_check(client, e["url"]) for e in DEMO_PRODUCTS)
        )
        ok_urls = sum(head_results)
        print(f"  → {ok_urls}/{len(DEMO_PRODUCTS)} URLs accessibles\n")
        if ok_urls == 0:
            print("✗ Aucune URL accessible — rien à seeder.", file=sys.stderr)
            return 1

        report: list[dict] = []
        for i, (entry, head_ok) in enumerate(zip(DEMO_PRODUCTS, head_results), 1):
            persona = entry["category_persona"]
            if not head_ok:
                print(f"[{i:02d}/50] · {persona:11} URL 404 — skip")
                report.append({"persona": persona, "url": entry["url"], "ok": False, "error": "URL not reachable (HEAD)"})
                continue
            try:
                r = await client.post(
                    f"{API_URL}/api/inventory/products/from-photo",
                    json={
                        "photo_url": entry["url"],
                        "sale_price_hint": entry["price_hint"],
                        "is_test": True,
                    },
                    headers=headers,
                )
                if r.status_code >= 400:
                    print(f"[{i:02d}/50] ✗ {persona:11} HTTP {r.status_code} : {r.text[:120]}", file=sys.stderr)
                    report.append({"persona": persona, "url": entry["url"], "ok": False, "error": r.text[:200]})
                    continue
                data = r.json()
                vision_used = data.get("vision_used", False)
                product = data.get("product", {})
                print(
                    f"[{i:02d}/50] ✓ {persona:11} → {product.get('name', '')[:40]:40} "
                    f"score={product.get('trend_score', '?'):>5} vision={vision_used}"
                )
                report.append({
                    "persona": persona,
                    "url": entry["url"],
                    "ok": True,
                    "vision_used": vision_used,
                    "product_id": product.get("id"),
                    "name": product.get("name"),
                    "score": product.get("trend_score"),
                })
            except Exception as exc:  # noqa: BLE001
                print(f"[{i:02d}/50] ✗ {persona:11} EXCEPTION: {exc}", file=sys.stderr)
                report.append({"persona": persona, "url": entry["url"], "ok": False, "error": str(exc)})

        report_path = output_dir / "seed_demo_report.json"
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))

        ok = sum(1 for r in report if r.get("ok"))
        vu = sum(1 for r in report if r.get("vision_used"))
        print(f"\n=== Done. {ok}/{len(report)} produits créés. {vu} avec Vision active.")
        print(f"Report : {report_path}")
        return 0 if ok > 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
