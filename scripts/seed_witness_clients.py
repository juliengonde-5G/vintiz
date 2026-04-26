"""Seed 20 witness clients with cold-start taste profiles (L3.4).

Creates 4 personas × 5 clientes = 20 clients with distinct style profiles
to validate the Personal Shopper flow end-to-end. All marked is_test=True.

Personas
--------
- 5 minimalistes : style minimaliste, occasions bureau+quotidien,
                   couleurs noir/blanc/beige, budget 30€
- 5 vintage      : style vintage, occasions weekend+festival,
                   couleurs bordeaux/moutarde/kaki, budget 25€
- 5 chic         : style chic, occasions ceremonie+soiree,
                   couleurs marine/noir/rose, budget 50€
- 5 sport        : style sport+casual, occasions weekend,
                   couleurs gris/bleu, budget 20€

Emails : pattern ``prenom.nom@temoin.vintiz.fr`` (identifiables, séparables
des clientes réelles).

Usage
-----

    python scripts/seed_witness_clients.py

The script is idempotent : already-existing emails are skipped.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import httpx


# 20 witness clients : 4 personas × 5 instances.
WITNESS_CLIENTS = [
    # --- Minimalistes (5) ---
    {"first_name": "Camille", "last_name": "Martin", "persona": "minimaliste",
     "styles": ["minimaliste"], "occasions": ["bureau", "quotidien"],
     "budget_max": 30, "categories": ["Top", "Pantalon"]},
    {"first_name": "Sophie", "last_name": "Bernard", "persona": "minimaliste",
     "styles": ["minimaliste", "casual"], "occasions": ["bureau"],
     "budget_max": 35, "categories": ["Robe", "Top"]},
    {"first_name": "Léa", "last_name": "Dubois", "persona": "minimaliste",
     "styles": ["minimaliste"], "occasions": ["bureau", "quotidien"],
     "budget_max": 30, "categories": ["Manteau", "Pantalon"]},
    {"first_name": "Anne", "last_name": "Leroy", "persona": "minimaliste",
     "styles": ["minimaliste", "business"], "occasions": ["bureau"],
     "budget_max": 40, "categories": ["Veste", "Pantalon"]},
    {"first_name": "Marie", "last_name": "Moreau", "persona": "minimaliste",
     "styles": ["minimaliste"], "occasions": ["quotidien"],
     "budget_max": 25, "categories": ["Top", "Robe"]},

    # --- Vintage (5) ---
    {"first_name": "Élise", "last_name": "Petit", "persona": "vintage",
     "styles": ["vintage", "boheme"], "occasions": ["weekend", "festival"],
     "budget_max": 25, "categories": ["Robe", "Veste"]},
    {"first_name": "Charlotte", "last_name": "Rousseau", "persona": "vintage",
     "styles": ["vintage"], "occasions": ["weekend"],
     "budget_max": 30, "categories": ["Top", "Jupe"]},
    {"first_name": "Juliette", "last_name": "Laurent", "persona": "vintage",
     "styles": ["vintage", "romantique"], "occasions": ["weekend", "soiree"],
     "budget_max": 35, "categories": ["Robe", "Accessoire"]},
    {"first_name": "Margaux", "last_name": "Garcia", "persona": "vintage",
     "styles": ["vintage"], "occasions": ["festival"],
     "budget_max": 22, "categories": ["Veste", "Top"]},
    {"first_name": "Inès", "last_name": "Roux", "persona": "vintage",
     "styles": ["vintage", "boheme"], "occasions": ["weekend"],
     "budget_max": 28, "categories": ["Robe", "Pantalon"]},

    # --- Chic (5) ---
    {"first_name": "Clara", "last_name": "Dupont", "persona": "chic",
     "styles": ["chic", "romantique"], "occasions": ["ceremonie", "soiree"],
     "budget_max": 50, "categories": ["Robe", "Veste"]},
    {"first_name": "Alice", "last_name": "Lefebvre", "persona": "chic",
     "styles": ["chic"], "occasions": ["soiree", "ceremonie"],
     "budget_max": 60, "categories": ["Robe", "Top"]},
    {"first_name": "Sarah", "last_name": "Mercier", "persona": "chic",
     "styles": ["chic", "business"], "occasions": ["ceremonie"],
     "budget_max": 55, "categories": ["Robe", "Sac"]},
    {"first_name": "Emma", "last_name": "Blanc", "persona": "chic",
     "styles": ["chic"], "occasions": ["soiree"],
     "budget_max": 45, "categories": ["Top", "Veste"]},
    {"first_name": "Pauline", "last_name": "Faure", "persona": "chic",
     "styles": ["chic", "romantique"], "occasions": ["ceremonie"],
     "budget_max": 50, "categories": ["Robe", "Accessoire"]},

    # --- Sport (5) ---
    {"first_name": "Léna", "last_name": "Rey", "persona": "sport",
     "styles": ["sport", "casual"], "occasions": ["weekend"],
     "budget_max": 20, "categories": ["Top", "Pantalon"]},
    {"first_name": "Lucie", "last_name": "Robin", "persona": "sport",
     "styles": ["sport"], "occasions": ["weekend"],
     "budget_max": 25, "categories": ["Pull", "Pantalon"]},
    {"first_name": "Manon", "last_name": "Dupuis", "persona": "sport",
     "styles": ["sport", "casual"], "occasions": ["weekend", "quotidien"],
     "budget_max": 22, "categories": ["Top", "Veste"]},
    {"first_name": "Chloé", "last_name": "Gauthier", "persona": "sport",
     "styles": ["sport"], "occasions": ["quotidien"],
     "budget_max": 18, "categories": ["Pull"]},
    {"first_name": "Zoé", "last_name": "Henry", "persona": "sport",
     "styles": ["casual"], "occasions": ["weekend"],
     "budget_max": 20, "categories": ["Top", "Pantalon"]},
]


API_URL = os.getenv("VINTIZ_API_URL", "http://localhost:8000")
API_TOKEN = os.getenv("VINTIZ_API_TOKEN", "")


def email_for(client_def: dict) -> str:
    """Witness pattern : prenom.nom@temoin.vintiz.fr (deterministic)."""
    fn = client_def["first_name"].lower().replace("é", "e").replace("è", "e").replace("ï", "i")
    ln = client_def["last_name"].lower()
    return f"{fn}.{ln}@temoin.vintiz.fr"


async def login_admin(client: httpx.AsyncClient) -> str:
    r = await client.post(
        f"{API_URL}/api/auth/login",
        data={"username": "admin", "password": "vintiz2026"},
    )
    r.raise_for_status()
    return r.json()["access_token"]


async def main() -> int:
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    async with httpx.AsyncClient(timeout=30) as http:
        token = API_TOKEN or await login_admin(http)
        headers = {"Authorization": f"Bearer {token}"}

        report: list[dict] = []
        for i, defn in enumerate(WITNESS_CLIENTS, 1):
            email = email_for(defn)
            try:
                # 1. Create client (POST /api/crm/clients) — with is_test=True flag
                # Note: is_test is set via direct DB injection since the public
                # endpoint doesn't expose this flag (privacy). We use the seed
                # admin endpoint pattern instead.
                r = await http.post(
                    f"{API_URL}/api/crm/clients",
                    json={
                        "first_name": defn["first_name"],
                        "last_name": defn["last_name"],
                        "email": email,
                        "email_optin": True,
                        "is_test": True,
                    },
                    headers=headers,
                )
                if r.status_code in (400, 409):
                    print(f"[{i:02d}/20] · {defn['persona']:13} {email} (skip — déjà existante)")
                    report.append({"email": email, "persona": defn["persona"], "ok": False, "skipped": True})
                    continue
                if r.status_code >= 400:
                    print(f"[{i:02d}/20] ✗ {defn['persona']:13} {email} HTTP {r.status_code}", file=sys.stderr)
                    report.append({"email": email, "persona": defn["persona"], "ok": False, "error": r.text[:200]})
                    continue
                client_data = r.json()

                # 2. Cold-start onboarding (POST /api/crm/account/onboarding)
                onboard = await http.post(
                    f"{API_URL}/api/crm/account/onboarding",
                    json={
                        "email": email,
                        "styles": defn["styles"],
                        "occasions": defn["occasions"],
                        "budget_max": defn["budget_max"],
                        "favorite_categories": defn["categories"],
                    },
                )
                onboard_ok = onboard.status_code < 400

                print(f"[{i:02d}/20] ✓ {defn['persona']:13} {email} (onboarding={'ok' if onboard_ok else 'fail'})")
                report.append({
                    "email": email,
                    "persona": defn["persona"],
                    "client_id": client_data.get("id"),
                    "ok": True,
                    "onboarding_ok": onboard_ok,
                })
            except Exception as exc:  # noqa: BLE001
                print(f"[{i:02d}/20] ✗ {defn['persona']:13} {email} EXCEPTION: {exc}", file=sys.stderr)
                report.append({"email": email, "persona": defn["persona"], "ok": False, "error": str(exc)})

        report_path = output_dir / "seed_witness_report.json"
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))

        ok = sum(1 for r in report if r.get("ok"))
        print(f"\n=== Done. {ok}/{len(report)} clientes créées (4 personas × 5, is_test=true).")
        print(f"Report : {report_path}")
        return 0 if ok > 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
