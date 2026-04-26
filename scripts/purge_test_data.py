"""Purge selectively all rows marked is_test=True (L3.7).

Calls the admin endpoint ``POST /api/admin/test-data/purge`` first in
dry-run mode (default), prints the counts, and asks for confirmation
before actually deleting.

The pre-opening real base (rows with is_test=False, the default) is
**untouched** by this script.

Usage
-----

    # Local dev :
    python scripts/purge_test_data.py

    # No prompt (CI / automated runs) :
    YES=1 python scripts/purge_test_data.py
"""
from __future__ import annotations

import asyncio
import os
import sys

import httpx


API_URL = os.getenv("VINTIZ_API_URL", "http://localhost:8000")
API_TOKEN = os.getenv("VINTIZ_API_TOKEN", "")
YES = os.getenv("YES", "") == "1"


async def login_admin(client: httpx.AsyncClient) -> str:
    r = await client.post(
        f"{API_URL}/api/auth/login",
        data={"username": "admin", "password": "vintiz2026"},
    )
    r.raise_for_status()
    return r.json()["access_token"]


async def main() -> int:
    async with httpx.AsyncClient(timeout=60) as client:
        token = API_TOKEN or await login_admin(client)
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Dry run
        r = await client.post(
            f"{API_URL}/api/admin/test-data/purge",
            json={"dry_run": True},
            headers=headers,
        )
        if r.status_code >= 400:
            print(f"✗ Purge dry-run failed : HTTP {r.status_code} {r.text[:200]}", file=sys.stderr)
            return 1
        wd = r.json().get("would_delete", {})
        n_prod, n_cli = wd.get("products", 0), wd.get("clients", 0)
        print(f"Dry-run : {n_prod} produits + {n_cli} clientes seraient supprimés (is_test=true).")

        if n_prod == 0 and n_cli == 0:
            print("Rien à purger.")
            return 0

        if not YES:
            ans = input("Confirmer la purge ? [y/N] ").strip().lower()
            if ans not in {"y", "yes", "o", "oui"}:
                print("Abandon.")
                return 0

        # 2. Real purge
        r = await client.post(
            f"{API_URL}/api/admin/test-data/purge",
            json={"dry_run": False},
            headers=headers,
        )
        if r.status_code >= 400:
            print(f"✗ Purge failed : HTTP {r.status_code} {r.text[:200]}", file=sys.stderr)
            return 1
        deleted = r.json().get("deleted", {})
        print(f"✓ Supprimés : {deleted.get('products', 0)} produits, {deleted.get('clients', 0)} clientes.")
        print("La base pré-ouverture (is_test=false) est intacte.")
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
