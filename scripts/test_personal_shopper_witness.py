"""Test Personal Shopper recommendations on the 20 witness clients (L3.5).

For each witness email, calls ``GET /api/crm/personal-shopper-v2?email=``
and captures the response. Outputs a CSV report with :
- email, persona, n_recommendations, narrative_excerpt
- fallback_used (Claude indispo ?)
- coherence_score (heuristic : do recommended products' colors match the
  persona's preferred palette ?)

Usage
-----

    python scripts/test_personal_shopper_witness.py
"""
from __future__ import annotations

import asyncio
import csv
import json
import os
import sys
from pathlib import Path

import httpx


API_URL = os.getenv("VINTIZ_API_URL", "http://localhost:8000")
API_TOKEN = os.getenv("VINTIZ_API_TOKEN", "")


# Persona → expected color palette (heuristic for coherence_score)
PERSONA_PALETTE = {
    "minimaliste": {"noir", "blanc", "beige", "gris", "écru", "ecru"},
    "vintage": {"bordeaux", "moutarde", "kaki", "marron", "ocre", "rouille"},
    "chic": {"marine", "noir", "rose", "rose poudré", "bleu marine", "bordeaux"},
    "sport": {"gris", "bleu", "noir", "blanc", "marine"},
}


def email_to_persona(email: str) -> str:
    """Reverse-engineer persona from email — relies on convention."""
    # 5 minimalistes : Camille / Sophie / Léa / Anne / Marie
    # 5 vintage : Élise / Charlotte / Juliette / Margaux / Inès
    # 5 chic : Clara / Alice / Sarah / Emma / Pauline
    # 5 sport : Léna / Lucie / Manon / Chloé / Zoé
    first = email.split("@", 1)[0].split(".")[0].lower()
    if first in {"camille", "sophie", "lea", "anne", "marie"}:
        return "minimaliste"
    if first in {"elise", "charlotte", "juliette", "margaux", "ines"}:
        return "vintage"
    if first in {"clara", "alice", "sarah", "emma", "pauline"}:
        return "chic"
    if first in {"lena", "lucie", "manon", "chloe", "zoe"}:
        return "sport"
    return "unknown"


def coherence_score(persona: str, recommendations: list[dict]) -> float:
    """Heuristic [0, 1] — proportion of recos whose color matches the palette."""
    palette = PERSONA_PALETTE.get(persona, set())
    if not palette or not recommendations:
        return 0.0
    matches = sum(
        1 for r in recommendations
        if (r.get("color") or "").lower() in palette
    )
    return round(matches / len(recommendations), 2)


WITNESS_EMAILS = [
    "camille.martin@temoin.vintiz.fr",
    "sophie.bernard@temoin.vintiz.fr",
    "lea.dubois@temoin.vintiz.fr",
    "anne.leroy@temoin.vintiz.fr",
    "marie.moreau@temoin.vintiz.fr",
    "elise.petit@temoin.vintiz.fr",
    "charlotte.rousseau@temoin.vintiz.fr",
    "juliette.laurent@temoin.vintiz.fr",
    "margaux.garcia@temoin.vintiz.fr",
    "ines.roux@temoin.vintiz.fr",
    "clara.dupont@temoin.vintiz.fr",
    "alice.lefebvre@temoin.vintiz.fr",
    "sarah.mercier@temoin.vintiz.fr",
    "emma.blanc@temoin.vintiz.fr",
    "pauline.faure@temoin.vintiz.fr",
    "lena.rey@temoin.vintiz.fr",
    "lucie.robin@temoin.vintiz.fr",
    "manon.dupuis@temoin.vintiz.fr",
    "chloe.gauthier@temoin.vintiz.fr",
    "zoe.henry@temoin.vintiz.fr",
]


async def main() -> int:
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    rows: list[dict] = []
    async with httpx.AsyncClient(timeout=60) as http:
        for i, email in enumerate(WITNESS_EMAILS, 1):
            persona = email_to_persona(email)
            try:
                r = await http.get(
                    f"{API_URL}/api/crm/personal-shopper-v2",
                    params={"email": email},
                )
                if r.status_code >= 400:
                    print(f"[{i:02d}/20] ✗ {persona:13} {email} HTTP {r.status_code}")
                    rows.append({
                        "email": email, "persona": persona,
                        "n_recommendations": 0, "narrative": "",
                        "fallback_used": True, "coherence_score": 0.0,
                        "error": r.text[:120],
                    })
                    continue
                data = r.json()
                recs = data.get("recommendations") or data.get("products") or []
                narrative = (data.get("narrative") or data.get("message") or "")[:200]
                fallback = data.get("fallback_used", False)
                coh = coherence_score(persona, recs)
                rows.append({
                    "email": email,
                    "persona": persona,
                    "n_recommendations": len(recs),
                    "narrative": narrative,
                    "fallback_used": fallback,
                    "coherence_score": coh,
                    "recommendation_set_id": data.get("recommendation_set_id", ""),
                    "error": "",
                })
                print(
                    f"[{i:02d}/20] ✓ {persona:13} {email}  "
                    f"recs={len(recs)} fallback={fallback} cohérence={coh}"
                )
            except Exception as exc:  # noqa: BLE001
                print(f"[{i:02d}/20] ✗ {persona:13} {email} EXCEPTION: {exc}", file=sys.stderr)
                rows.append({
                    "email": email, "persona": persona,
                    "n_recommendations": 0, "narrative": "",
                    "fallback_used": True, "coherence_score": 0.0,
                    "error": str(exc),
                })

    csv_path = output_dir / "personal_shopper_witness_report.csv"
    json_path = output_dir / "personal_shopper_witness_report.json"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "email", "persona", "n_recommendations",
            "fallback_used", "coherence_score", "narrative",
            "recommendation_set_id", "error",
        ])
        w.writeheader()
        w.writerows(rows)
    json_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False))

    avg_coherence = sum(r["coherence_score"] for r in rows) / max(1, len(rows))
    print(f"\n=== Done. Cohérence moyenne : {avg_coherence:.2f}")
    print(f"CSV : {csv_path}")
    print(f"JSON : {json_path}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
