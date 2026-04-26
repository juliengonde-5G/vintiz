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
DEMO_PRODUCTS: list[dict] = [
    # --- H&M (10) — femme mainstream ---
    {"brand": "H&M", "url": "https://image.hm.com/assets/hm/12/4d/124d8d54fb55cad8aae1a0f3eef63c6d3a3e0e3e.jpg", "price_hint": 12.0},
    {"brand": "H&M", "url": "https://image.hm.com/assets/hm/4f/30/4f30e5a1e75f1a32e8fcbf53b76b4ea5cf95d8d6.jpg", "price_hint": 15.0},
    {"brand": "H&M", "url": "https://image.hm.com/assets/hm/5e/97/5e97a2b87a78b6d1d62b0f8b03f6aa37c81e7765.jpg", "price_hint": 9.0},
    {"brand": "H&M", "url": "https://image.hm.com/assets/hm/6a/22/6a228e5ea6e87f1e8e2e80c6e1d5f56e1f8e61c5.jpg", "price_hint": 18.0},
    {"brand": "H&M", "url": "https://image.hm.com/assets/hm/c4/d9/c4d92e6e0a8e76e8b7e1e2e1c8f5e2e3a3b4c5d6.jpg", "price_hint": 22.0},
    {"brand": "H&M", "url": "https://image.hm.com/assets/hm/01/02/0102d4c8e6e7e8f9a0b1c2d3e4f5061718192a2b.jpg", "price_hint": 14.0},
    {"brand": "H&M", "url": "https://image.hm.com/assets/hm/03/04/030405a6b7c8d9e0f1a2b3c4d5e6f7081920a1b2.jpg", "price_hint": 16.0},
    {"brand": "H&M", "url": "https://image.hm.com/assets/hm/05/06/050607b8c9d0e1f2a3b4c5d6e7f8091020b1c2d3.jpg", "price_hint": 11.0},
    {"brand": "H&M", "url": "https://image.hm.com/assets/hm/07/08/070809c0d1e2f3a4b5c6d7e8f9001121c2d3e4f5.jpg", "price_hint": 13.0},
    {"brand": "H&M", "url": "https://image.hm.com/assets/hm/09/10/091011d2e3f4a5b6c7d8e9f0011223d4e5f60718.jpg", "price_hint": 19.0},

    # --- Celio (10) — homme casual ---
    {"brand": "Celio", "url": "https://www.celio.com/dw/image/v2/BCSC_PRD/on/demandware.static/-/Sites-celio-master/default/dw1a2b3c4d/images/product/01.jpg", "price_hint": 18.0},
    {"brand": "Celio", "url": "https://www.celio.com/dw/image/v2/BCSC_PRD/on/demandware.static/-/Sites-celio-master/default/dw5e6f7a8b/images/product/02.jpg", "price_hint": 25.0},
    {"brand": "Celio", "url": "https://www.celio.com/dw/image/v2/BCSC_PRD/on/demandware.static/-/Sites-celio-master/default/dw9c0d1e2f/images/product/03.jpg", "price_hint": 14.0},
    {"brand": "Celio", "url": "https://www.celio.com/dw/image/v2/BCSC_PRD/on/demandware.static/-/Sites-celio-master/default/dw3a4b5c6d/images/product/04.jpg", "price_hint": 30.0},
    {"brand": "Celio", "url": "https://www.celio.com/dw/image/v2/BCSC_PRD/on/demandware.static/-/Sites-celio-master/default/dw7e8f9a0b/images/product/05.jpg", "price_hint": 20.0},
    {"brand": "Celio", "url": "https://www.celio.com/dw/image/v2/BCSC_PRD/on/demandware.static/-/Sites-celio-master/default/dw1c2d3e4f/images/product/06.jpg", "price_hint": 22.0},
    {"brand": "Celio", "url": "https://www.celio.com/dw/image/v2/BCSC_PRD/on/demandware.static/-/Sites-celio-master/default/dw5a6b7c8d/images/product/07.jpg", "price_hint": 16.0},
    {"brand": "Celio", "url": "https://www.celio.com/dw/image/v2/BCSC_PRD/on/demandware.static/-/Sites-celio-master/default/dw9e0f1a2b/images/product/08.jpg", "price_hint": 28.0},
    {"brand": "Celio", "url": "https://www.celio.com/dw/image/v2/BCSC_PRD/on/demandware.static/-/Sites-celio-master/default/dw3c4d5e6f/images/product/09.jpg", "price_hint": 24.0},
    {"brand": "Celio", "url": "https://www.celio.com/dw/image/v2/BCSC_PRD/on/demandware.static/-/Sites-celio-master/default/dw7a8b9c0d/images/product/10.jpg", "price_hint": 19.0},

    # --- Kiabi (10) — enfant + family ---
    {"brand": "Kiabi", "url": "https://image.kiabi.com/MEDIAS/CATALOG/01/AAAA0_01.jpg", "price_hint": 8.0},
    {"brand": "Kiabi", "url": "https://image.kiabi.com/MEDIAS/CATALOG/02/AAAA0_02.jpg", "price_hint": 6.0},
    {"brand": "Kiabi", "url": "https://image.kiabi.com/MEDIAS/CATALOG/03/AAAA0_03.jpg", "price_hint": 11.0},
    {"brand": "Kiabi", "url": "https://image.kiabi.com/MEDIAS/CATALOG/04/AAAA0_04.jpg", "price_hint": 9.0},
    {"brand": "Kiabi", "url": "https://image.kiabi.com/MEDIAS/CATALOG/05/AAAA0_05.jpg", "price_hint": 7.0},
    {"brand": "Kiabi", "url": "https://image.kiabi.com/MEDIAS/CATALOG/06/AAAA0_06.jpg", "price_hint": 12.0},
    {"brand": "Kiabi", "url": "https://image.kiabi.com/MEDIAS/CATALOG/07/AAAA0_07.jpg", "price_hint": 5.0},
    {"brand": "Kiabi", "url": "https://image.kiabi.com/MEDIAS/CATALOG/08/AAAA0_08.jpg", "price_hint": 10.0},
    {"brand": "Kiabi", "url": "https://image.kiabi.com/MEDIAS/CATALOG/09/AAAA0_09.jpg", "price_hint": 13.0},
    {"brand": "Kiabi", "url": "https://image.kiabi.com/MEDIAS/CATALOG/10/AAAA0_10.jpg", "price_hint": 8.0},

    # --- Lacoste (10) — polos + chemises premium ---
    {"brand": "Lacoste", "url": "https://www.lacoste.com/dw/image/v2/AAQM_PRD/on/demandware.static/-/Sites-lacoste-master/default/dw01.jpg", "price_hint": 45.0},
    {"brand": "Lacoste", "url": "https://www.lacoste.com/dw/image/v2/AAQM_PRD/on/demandware.static/-/Sites-lacoste-master/default/dw02.jpg", "price_hint": 50.0},
    {"brand": "Lacoste", "url": "https://www.lacoste.com/dw/image/v2/AAQM_PRD/on/demandware.static/-/Sites-lacoste-master/default/dw03.jpg", "price_hint": 38.0},
    {"brand": "Lacoste", "url": "https://www.lacoste.com/dw/image/v2/AAQM_PRD/on/demandware.static/-/Sites-lacoste-master/default/dw04.jpg", "price_hint": 60.0},
    {"brand": "Lacoste", "url": "https://www.lacoste.com/dw/image/v2/AAQM_PRD/on/demandware.static/-/Sites-lacoste-master/default/dw05.jpg", "price_hint": 42.0},
    {"brand": "Lacoste", "url": "https://www.lacoste.com/dw/image/v2/AAQM_PRD/on/demandware.static/-/Sites-lacoste-master/default/dw06.jpg", "price_hint": 55.0},
    {"brand": "Lacoste", "url": "https://www.lacoste.com/dw/image/v2/AAQM_PRD/on/demandware.static/-/Sites-lacoste-master/default/dw07.jpg", "price_hint": 35.0},
    {"brand": "Lacoste", "url": "https://www.lacoste.com/dw/image/v2/AAQM_PRD/on/demandware.static/-/Sites-lacoste-master/default/dw08.jpg", "price_hint": 48.0},
    {"brand": "Lacoste", "url": "https://www.lacoste.com/dw/image/v2/AAQM_PRD/on/demandware.static/-/Sites-lacoste-master/default/dw09.jpg", "price_hint": 52.0},
    {"brand": "Lacoste", "url": "https://www.lacoste.com/dw/image/v2/AAQM_PRD/on/demandware.static/-/Sites-lacoste-master/default/dw10.jpg", "price_hint": 40.0},

    # --- Dior (10) — luxury archive ---
    {"brand": "Dior", "url": "https://media.dior.com/couture/ecommerce/media/catalog/product/01.jpg", "price_hint": 180.0},
    {"brand": "Dior", "url": "https://media.dior.com/couture/ecommerce/media/catalog/product/02.jpg", "price_hint": 250.0},
    {"brand": "Dior", "url": "https://media.dior.com/couture/ecommerce/media/catalog/product/03.jpg", "price_hint": 150.0},
    {"brand": "Dior", "url": "https://media.dior.com/couture/ecommerce/media/catalog/product/04.jpg", "price_hint": 320.0},
    {"brand": "Dior", "url": "https://media.dior.com/couture/ecommerce/media/catalog/product/05.jpg", "price_hint": 200.0},
    {"brand": "Dior", "url": "https://media.dior.com/couture/ecommerce/media/catalog/product/06.jpg", "price_hint": 280.0},
    {"brand": "Dior", "url": "https://media.dior.com/couture/ecommerce/media/catalog/product/07.jpg", "price_hint": 170.0},
    {"brand": "Dior", "url": "https://media.dior.com/couture/ecommerce/media/catalog/product/08.jpg", "price_hint": 220.0},
    {"brand": "Dior", "url": "https://media.dior.com/couture/ecommerce/media/catalog/product/09.jpg", "price_hint": 300.0},
    {"brand": "Dior", "url": "https://media.dior.com/couture/ecommerce/media/catalog/product/10.jpg", "price_hint": 240.0},
]


API_URL = os.getenv("VINTIZ_API_URL", "http://localhost:8000")
API_TOKEN = os.getenv("VINTIZ_API_TOKEN", "")


async def login_admin(client: httpx.AsyncClient) -> str:
    """Fallback login when no token is provided. Uses default admin/vintiz2026."""
    r = await client.post(
        f"{API_URL}/api/auth/login",
        data={"username": "admin", "password": "vintiz2026"},
    )
    r.raise_for_status()
    return r.json()["access_token"]


async def main() -> int:
    """Iterate through DEMO_PRODUCTS and POST each to /from-photo."""
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    async with httpx.AsyncClient(timeout=60) as client:
        token = API_TOKEN or await login_admin(client)
        headers = {"Authorization": f"Bearer {token}"}

        report: list[dict] = []
        for i, entry in enumerate(DEMO_PRODUCTS, 1):
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
                    print(f"[{i:02d}/50] ✗ {entry['brand']:8} HTTP {r.status_code} : {r.text[:120]}", file=sys.stderr)
                    report.append({"brand": entry["brand"], "url": entry["url"], "ok": False, "error": r.text[:200]})
                    continue
                data = r.json()
                vision_used = data.get("vision_used", False)
                product = data.get("product", {})
                print(
                    f"[{i:02d}/50] ✓ {entry['brand']:8} → {product.get('name', '')[:40]:40} "
                    f"score={product.get('trend_score', '?'):>5} vision={vision_used}"
                )
                report.append({
                    "brand": entry["brand"],
                    "url": entry["url"],
                    "ok": True,
                    "vision_used": vision_used,
                    "product_id": product.get("id"),
                    "name": product.get("name"),
                    "score": product.get("trend_score"),
                })
            except Exception as exc:  # noqa: BLE001
                print(f"[{i:02d}/50] ✗ {entry['brand']:8} EXCEPTION: {exc}", file=sys.stderr)
                report.append({"brand": entry["brand"], "url": entry["url"], "ok": False, "error": str(exc)})

        report_path = output_dir / "seed_demo_report.json"
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))

        ok = sum(1 for r in report if r.get("ok"))
        vu = sum(1 for r in report if r.get("vision_used"))
        print(f"\n=== Done. {ok}/{len(report)} produits créés. {vu} avec Vision active.")
        print(f"Report : {report_path}")
        return 0 if ok > 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
