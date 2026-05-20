"""Store-operations persona audit (Responsable de magasin).

Audits the refonte of the product-intake module: are new products coming in
with a photo, are they being scored by the AI, do they carry an entry date and
— once on the floor — a shelf date and a zone? Surfaces the gaps a store
manager would chase during a stock review.

The report is a pure function over the DB plus an optional Claude narrative.
Without ``ANTHROPIC_API_KEY`` (tests, offline) it degrades to a deterministic
narrative built from the same metrics, so the endpoint always returns
something actionable.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.product import Product, ProductPhoto, ProductStatus

logger = logging.getLogger("vintiz.ai.store_ops")

# Back stock vs shop floor. Mirrors FLOOR_STATUSES in the inventory router and
# _FLOOR_STATUS_VALUES in zebra_zpl so the three views agree on what "en
# magasin" means.
STOCK_STATUSES = [
    ProductStatus.stock,
    ProductStatus.received,
    ProductStatus.sorted,
    ProductStatus.tagged,
]
FLOOR_STATUSES = [
    ProductStatus.display,
    ProductStatus.displayed,
    ProductStatus.discounted,
    ProductStatus.deep_discounted,
]
ACTIVE_STATUSES = STOCK_STATUSES + FLOOR_STATUSES

# A product sitting in the back longer than this without ever being displayed
# is flagged as stagnant stock.
STAGNANT_STOCK_DAYS = 30


async def _count(db: AsyncSession, *where) -> int:
    stmt = select(func.count()).select_from(Product)
    for clause in where:
        stmt = stmt.where(clause)
    return int((await db.execute(stmt)).scalar_one() or 0)


def _pct(part: int, whole: int) -> float:
    return round(100.0 * part / whole, 1) if whole else 0.0


async def collect_metrics(db: AsyncSession) -> dict:
    """Compute the intake-health metrics the persona reasons about."""
    now = datetime.now(timezone.utc)
    stagnant_cutoff = now - timedelta(days=STAGNANT_STOCK_DAYS)

    active = Product.status.in_(ACTIVE_STATUSES)

    active_total = await _count(db, active)
    en_stock = await _count(db, Product.status.in_(STOCK_STATUSES))
    en_magasin = await _count(db, Product.status.in_(FLOOR_STATUSES))

    sans_photo = await _count(db, active, Product.photo_url.is_(None))
    sans_date_entree = await _count(db, active, Product.received_at.is_(None))
    sans_zone_en_rayon = await _count(
        db, Product.status.in_(FLOOR_STATUSES), Product.zone_id.is_(None)
    )
    sans_date_rayon = await _count(
        db, Product.status.in_(FLOOR_STATUSES), Product.shelf_date.is_(None)
    )
    champs_incomplets = await _count(
        db,
        active,
        (Product.brand.is_(None))
        | (Product.size.is_(None))
        | (Product.color.is_(None)),
    )
    stock_stagnant = await _count(
        db,
        Product.status.in_(STOCK_STATUSES),
        Product.displayed_at.is_(None),
        Product.received_at.is_not(None),
        Product.received_at < stagnant_cutoff,
    )

    # Products whose photo carries an AI analysis timestamp.
    analyzed_stmt = (
        select(func.count(func.distinct(ProductPhoto.product_id)))
        .select_from(ProductPhoto)
        .join(Product, Product.id == ProductPhoto.product_id)
        .where(active, ProductPhoto.ai_analyzed_at.is_not(None))
    )
    analyse_ia = int((await db.execute(analyzed_stmt)).scalar_one() or 0)

    return {
        "active_total": active_total,
        "en_stock": en_stock,
        "en_magasin": en_magasin,
        "sans_photo": sans_photo,
        "pct_sans_photo": _pct(sans_photo, active_total),
        "sans_date_entree": sans_date_entree,
        "sans_zone_en_rayon": sans_zone_en_rayon,
        "sans_date_rayon": sans_date_rayon,
        "champs_incomplets": champs_incomplets,
        "pct_champs_incomplets": _pct(champs_incomplets, active_total),
        "analyse_ia": analyse_ia,
        "pct_analyse_ia": _pct(analyse_ia, active_total),
        "stock_stagnant": stock_stagnant,
        "stagnant_days": STAGNANT_STOCK_DAYS,
    }


def _fallback_narrative(m: dict) -> dict:
    """Deterministic audit derived straight from the metrics.

    Used when Claude is unavailable so the report is never empty.
    """
    points_forts: list[str] = []
    points_faibles: list[str] = []
    actions: list[dict] = []

    if m["active_total"] == 0:
        return {
            "persona": "Sandrine Lemoine, Responsable de magasin (15 ans en retail mode)",
            "diagnostic": (
                "Aucun article actif dans l'inventaire pour le moment. Dès les "
                "premières entrées, ce rapport suivra la complétude des fiches, "
                "la couverture photo et l'affectation en zone."
            ),
            "points_forts": [],
            "points_faibles": [],
            "actions_prioritaires": [],
            "note_sur_module": (
                "Module d'entrée produit prêt à l'emploi — à valider sur les "
                "premiers arrivages réels."
            ),
        }

    if m["pct_sans_photo"] <= 10:
        points_forts.append(
            f"Couverture photo solide : {100 - m['pct_sans_photo']:.0f}% des "
            "articles actifs ont une photo."
        )
    else:
        points_faibles.append(
            f"{m['sans_photo']} articles ({m['pct_sans_photo']:.0f}%) sans photo "
            "— invendables en personal shopper et invisibles à la caisse."
        )
        actions.append({
            "priorite": "haute",
            "action": "Repasser les articles sans photo et capturer un visuel via le parcours d'entrée.",
            "impact": "Visibilité site + caisse, meilleure attribution IA.",
        })

    if m["pct_analyse_ia"] >= 60:
        points_forts.append(
            f"L'analyse IA tourne : {m['pct_analyse_ia']:.0f}% des articles ont une "
            "photo analysée."
        )
    else:
        points_faibles.append(
            f"Seulement {m['pct_analyse_ia']:.0f}% des articles ont une analyse IA — "
            "le pré-remplissage des fiches est sous-exploité."
        )

    if m["sans_zone_en_rayon"] > 0:
        points_faibles.append(
            f"{m['sans_zone_en_rayon']} articles en rayon sans zone affectée — "
            "introuvables quand une cliente demande où est la pièce."
        )
        actions.append({
            "priorite": "haute",
            "action": "Affecter une zone à chaque article mis en rayon (étape zone du parcours).",
            "impact": "Localisation produit fiable, réassort plus rapide.",
        })

    if m["sans_date_rayon"] > 0:
        points_faibles.append(
            f"{m['sans_date_rayon']} articles en rayon sans date de mise en rayon — "
            "le scoring d'ancienneté et la démarque J+30 sont faussés."
        )

    if m["stock_stagnant"] > 0:
        points_faibles.append(
            f"{m['stock_stagnant']} articles dorment en stock depuis plus de "
            f"{m['stagnant_days']} jours sans jamais passer en rayon."
        )
        actions.append({
            "priorite": "moyenne",
            "action": "Sortir le stock dormant : mise en rayon ou retour au tri.",
            "impact": "Rotation du stock, m² de réserve libérés.",
        })

    if m["pct_champs_incomplets"] > 25:
        actions.append({
            "priorite": "moyenne",
            "action": "Compléter marque / taille / couleur sur les fiches partielles.",
            "impact": "Recherche caisse et recommandations IA plus précises.",
        })

    diagnostic = (
        f"{m['active_total']} articles actifs : {m['en_stock']} en stock, "
        f"{m['en_magasin']} en magasin. "
        + (
            "Le parcours d'entrée alimente correctement les fiches. "
            if m["pct_sans_photo"] <= 10 and m["sans_zone_en_rayon"] == 0
            else "Quelques trous de saisie à combler sur la photo et l'affectation en zone. "
        )
    )

    return {
        "persona": "Sandrine Lemoine, Responsable de magasin (15 ans en retail mode)",
        "diagnostic": diagnostic.strip(),
        "points_forts": points_forts,
        "points_faibles": points_faibles,
        "actions_prioritaires": actions,
        "note_sur_module": (
            "Le module refondu (photo → analyse IA → vérification champs → prix → "
            "zone → étiquette) couvre le cycle d'entrée. Veiller à ce que chaque "
            "étape soit bien validée pour ne pas laisser de fiche incomplète."
        ),
    }


async def _claude_narrative(m: dict) -> dict | None:
    """Ask Claude to play the store-manager persona. Returns None on any failure."""
    key = settings.ANTHROPIC_API_KEY or ""
    if not key:
        return None
    try:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=key)
        prompt = f"""Tu es Sandrine Lemoine, Responsable de magasin chevronnée (15 ans en retail mode, ex-responsable boutique seconde main premium). Tu audites le module d'ENTRÉE PRODUIT refondu de la boutique Vintiz (Vernon).

Le parcours d'entrée d'un article est : prendre une photo → analyse IA automatique → vérification/complétude des champs (nom, marque, catégorie, couleur, taille) → prix suggéré par l'IA et validé → affectation d'une zone du magasin → édition de l'étiquette (avec référence de mise en stock/rayon).

Données d'inventaire actuelles :
- Articles actifs : {m['active_total']} ({m['en_stock']} en stock, {m['en_magasin']} en magasin)
- Sans photo : {m['sans_photo']} ({m['pct_sans_photo']}%)
- Avec analyse IA : {m['analyse_ia']} ({m['pct_analyse_ia']}%)
- En rayon sans zone affectée : {m['sans_zone_en_rayon']}
- En rayon sans date de mise en rayon : {m['sans_date_rayon']}
- Sans date d'entrée en stock : {m['sans_date_entree']}
- Fiches incomplètes (marque/taille/couleur manquante) : {m['champs_incomplets']} ({m['pct_champs_incomplets']}%)
- Stock dormant (>{m['stagnant_days']}j sans passage en rayon) : {m['stock_stagnant']}

Réponds UNIQUEMENT en JSON valide, sans markdown :
{{
  "persona": "Sandrine Lemoine, Responsable de magasin",
  "diagnostic": "1 paragraphe synthétique sur la santé des entrées produit",
  "points_forts": ["..."],
  "points_faibles": ["..."],
  "actions_prioritaires": [
    {{"priorite": "haute|moyenne|basse", "action": "...", "impact": "..."}}
  ],
  "note_sur_module": "Ton avis de responsable sur le parcours d'entrée refondu (ergonomie, risques de fiche incomplète, ce qui manque)"
}}

INTERDICTION : ne propose jamais de baisse de prix ni de soldes. La boutique fixe un prix juste dès la mise en rayon."""
        msg = await client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1600,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text if msg.content else "{}"
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            if raw.endswith("```"):
                raw = raw[:-3].strip()
        data = json.loads(raw)
        # Minimal shape check.
        if isinstance(data, dict) and "diagnostic" in data:
            return data
    except Exception as exc:  # noqa: BLE001 — never break the endpoint on AI failure
        logger.warning("store-ops Claude narrative failed: %s", exc)
    return None


async def build_store_ops_report(db: AsyncSession) -> dict:
    """Full report: metrics + persona narrative (Claude or deterministic fallback)."""
    now = datetime.now(timezone.utc)
    metrics = await collect_metrics(db)
    claude = await _claude_narrative(metrics)
    narrative = claude or _fallback_narrative(metrics)
    return {
        "generated_at": now.isoformat(),
        "week": now.isocalendar()[1],
        "year": now.year,
        "ai_generated": claude is not None,
        "metrics": metrics,
        "audit": narrative,
    }
