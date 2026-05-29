"""Personal Shopper v2 — recommendation pipeline (P2-003).

Pipeline:
1. Load (or compute) the customer's taste profile.
2. Find candidate products via cosine similarity (visual + text).
3. Diversify — keep at most one product per category, in score order.
4. Filter by the customer's most-frequent past size when known.
5. Ask Claude Haiku 4.5 to write a 4–6 line personalised message
   (deterministic template fallback if the API is unreachable).
6. Emit ``customer.recommendation_shown`` events so we can later
   measure click-through and A/B-test alternative encoders.

Returns a ``recommendation_set_id`` so a follow-up
``customer.recommendation_clicked`` event can be tied back to the
original recommendation.

The prompt template lives at
``apps/api/prompts/v1/personal_shopper.md``; bumping the model or the
phrasing only requires a new file alongside, plus an ``ALGO_VERSION``
update so old logged events stay attributable.
"""

from __future__ import annotations

import logging
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.client import Client, LoyaltyAccount
from app.models.embeddings import CustomerTasteProfile
from app.models.events import EventSource, EventType
from app.models.pos import Transaction, TransactionItem, TransactionType
from app.models.product import Product, ProductStatus
from app.services.embeddings import EmbeddingService
from app.services.events import EventService

logger = logging.getLogger("vintiz.personal_shopper")

ALGO_VERSION = "personal-shopper-v1-2026-04"
PROMPT_VERSION = "v1.0-2026-04"
DEFAULT_MODEL = "claude-haiku-4-5"
DEFAULT_TOP_N = 4
# How many candidates to fetch before diversification — wider funnel = better
# diversity without re-querying the DB.
CANDIDATE_FANOUT = 6


class PersonalShopperGatedError(PermissionError):
    """Raised when a customer is not allowed to use the Personal Shopper.

    ``reason`` is one of:

    - ``loyalty_required`` — no active loyalty membership.
    - ``profiling_consent_required`` — loyalty active but RGPD profiling
      consent missing or revoked.

    Routers translate this to HTTP 403 + a ``detail`` the public site
    surfaces as either an adhesion CTA or a consent toggle.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _format_currency(value) -> str:
    return f"{float(value):.2f}".replace(".", ",") + " €"


def _build_user_prompt(
    *,
    customer: Client,
    days_since_last_visit: int | None,
    last_purchases: list[dict],
    preferred_sizes: list[str],
    preferred_colors: list[str],
    candidates: list[dict],
    weather_summary: str | None,
) -> str:
    """Render the user message for the Anthropic call."""
    purchases_block = (
        "\n".join(
            f"- {p['name']} ({p.get('size') or 'taille n/a'}) — "
            f"{_format_currency(p['price'])} — {p['date']}"
            for p in last_purchases
        )
        or "- (Aucun achat passé connu)"
    )
    candidates_block = "\n".join(
        f"- ID {c['id']} | {c['name']} ({c.get('size') or 'taille n/a'}) — "
        f"{_format_currency(c['price'])} — score {c['score']:.2f}"
        for c in candidates
    )
    sizes = ", ".join(preferred_sizes) if preferred_sizes else "non identifiées"
    colors = ", ".join(preferred_colors) if preferred_colors else "non identifiées"
    last_visit = (
        f"il y a {days_since_last_visit} jours"
        if days_since_last_visit is not None
        else "première visite ou non connue"
    )
    return (
        f"Cliente : {customer.first_name}, dernière visite "
        f"{last_visit}.\n\n"
        f"3 derniers achats (du plus récent au plus ancien) :\n"
        f"{purchases_block}\n\n"
        f"Tailles habituelles : {sizes}\n"
        f"Couleurs préférées : {colors}\n\n"
        f"Sélection de pièces en stock pour elle "
        f"(ordre : score de pertinence décroissant) :\n"
        f"{candidates_block}\n\n"
        f"Météo Vernon prévue cette semaine : "
        f"{weather_summary or 'non communiquée'}\n\n"
        f"Génère le message Personal Shopper."
    )


# Loaded via the centralized prompts loader (T2 audit tech debt).
# Le fichier source vit dans apps/api/prompts/v1/personal_shopper.md.
_PERSONAL_SHOPPER_FALLBACK = (
    "Tu es la Personal Shopper de Vintiz Vernon. Présente 3-5 pièces "
    "à la cliente, ton chaleureux, vouvoiement, 4-6 phrases, références "
    "à ses achats passés, jamais de pièce hors stock."
)


def _system_prompt() -> str:
    from app.core.prompts import load_prompt

    return load_prompt(
        "personal_shopper",
        fallback=_PERSONAL_SHOPPER_FALLBACK,
    )


class PersonalShopperService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def recommend(
        self,
        customer_id: uuid.UUID,
        *,
        top_n: int = DEFAULT_TOP_N,
        weather_summary: str | None = None,
    ) -> dict:
        """Build a personalised recommendation set for ``customer_id``.

        Returns a dict shaped:
        ``{
            "recommendation_set_id": str,
            "message": str,
            "products": [{id, name, sale_price, size, score, ...}],
            "algo_version": str,
            "fallback_used": bool,
        }``

        Raises ``LookupError`` if the customer doesn't exist.
        Raises ``PersonalShopperGatedError`` if the customer is not a
        loyalty member or hasn't granted profiling consent (PR2 gating).
        """
        customer = await self._load_customer(customer_id)
        await self._enforce_gating(customer)

        profile = await self._load_or_build_profile(customer_id)

        recommendation_set_id = uuid.uuid4()
        if profile is None:
            # Cold start — no taste centroid yet. Return a minimal set and
            # rely on the cold-start onboarding (P2-004) for a richer flow.
            return await self._cold_start(customer, recommendation_set_id, top_n)

        # 1. Wide candidate pool from the embedding similarity search.
        emb_svc = EmbeddingService(self.db)
        wide_candidates = await emb_svc.find_similar_products(
            profile, top_k=top_n * CANDIDATE_FANOUT,
            statuses=[ProductStatus.stock, ProductStatus.display],
        )

        # 2. Apply size filter (best-effort: keep candidates whose size is in
        # the customer's preferred set OR whose size is unknown).
        preferred_sizes = await self._preferred_sizes(customer_id)
        if preferred_sizes:
            filtered = [
                (p, score) for p, score in wide_candidates
                if not p.size or p.size.lower() in preferred_sizes
            ]
            # Don't return empty if the size filter kills everything — fall
            # back to the wide pool with a warning logged for observability.
            wide_candidates = filtered or wide_candidates

        # 3. Diversify: at most one product per category, score order.
        diversified = self._diversify_by_category(wide_candidates, top_n=top_n)

        if not diversified:
            return await self._cold_start(customer, recommendation_set_id, top_n)

        # 4. Build the user prompt + call Claude Haiku (with fallback).
        last_purchases = await self._last_purchases(customer_id, limit=3)
        days_since = await self._days_since_last_visit(customer_id)
        candidates_payload = [
            {
                "id": str(p.id),
                "name": p.name,
                "size": p.size,
                "price": float(p.sale_price),
                "score": float(score),
            }
            for p, score in diversified
        ]
        message, fallback_used = await self._render_message(
            customer=customer,
            days_since_last_visit=days_since,
            last_purchases=last_purchases,
            preferred_sizes=sorted(preferred_sizes),
            preferred_colors=await self._preferred_colors(customer_id),
            candidates=candidates_payload,
            weather_summary=weather_summary,
        )

        # 5. Log one event per surfaced product so click-through can be
        # measured later.
        events = EventService(self.db)
        for product, score in diversified:
            await events.emit(
                EventType.customer_recommendation_shown,
                source=EventSource.api,
                customer_id=customer_id,
                product_id=product.id,
                session_id=recommendation_set_id,
                algo_version=ALGO_VERSION,
                meta={
                    "score": float(score),
                    "fallback_used": fallback_used,
                    "prompt_version": PROMPT_VERSION,
                },
            )

        return {
            "recommendation_set_id": str(recommendation_set_id),
            "message": message,
            "products": [
                {
                    "id": str(p.id),
                    # ``product_id`` + ``price_cents`` mirror the text-search
                    # payload so the espace-client front renders one consistent
                    # shape (no more ``NaN €`` from a missing ``price_cents``).
                    "product_id": str(p.id),
                    "name": p.name,
                    "size": p.size,
                    "color": p.color,
                    "brand": p.brand,
                    "sale_price": float(p.sale_price),
                    "price_cents": int(round(float(p.sale_price) * 100)),
                    "score": round(float(score), 4),
                    "photo_url": p.photo_url,
                }
                for p, score in diversified
            ],
            "algo_version": ALGO_VERSION,
            "prompt_version": PROMPT_VERSION,
            "fallback_used": fallback_used,
        }

    async def record_click(
        self,
        recommendation_set_id: uuid.UUID,
        product_id: uuid.UUID,
        customer_id: uuid.UUID | None = None,
        position_in_list: int | None = None,
    ) -> None:
        """Log a click on one of the recommended products."""
        await EventService(self.db).emit(
            EventType.customer_recommendation_clicked,
            source=EventSource.site,
            customer_id=customer_id,
            product_id=product_id,
            session_id=recommendation_set_id,
            algo_version=ALGO_VERSION,
            meta={"position_in_list": position_in_list},
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _load_customer(self, customer_id: uuid.UUID) -> Client:
        result = await self.db.execute(
            select(Client).where(Client.id == customer_id)
        )
        customer = result.scalar_one_or_none()
        if customer is None:
            raise LookupError(f"Client {customer_id} not found")
        return customer

    async def _enforce_gating(self, customer: Client) -> None:
        """PR2: Personal Shopper is members-only with explicit profiling consent.

        Two checks, both raising :class:`PersonalShopperGatedError`:

        1. ``loyalty_active`` — the customer must hold a non-expired
           loyalty account (24-month rolling window). Non-members get
           pushed to the adhesion CTA.
        2. ``profiling`` consent — even members must opt-in to the
           profilage RGPD purpose before their taste profile is used.
           Toggleable from /account/shopper.
        """
        from app.models.client import Consent, ConsentPurpose
        from app.services.loyalty import loyalty_active

        if not loyalty_active(customer):
            raise PersonalShopperGatedError("loyalty_required")

        latest = await self.db.execute(
            select(Consent)
            .where(
                Consent.client_id == customer.id,
                Consent.purpose == ConsentPurpose.profiling,
            )
            .order_by(Consent.created_at.desc())
            .limit(1)
        )
        consent = latest.scalar_one_or_none()
        if consent is None or not consent.granted:
            raise PersonalShopperGatedError("profiling_consent_required")

    async def _load_or_build_profile(
        self, customer_id: uuid.UUID
    ) -> CustomerTasteProfile | None:
        existing = await self.db.execute(
            select(CustomerTasteProfile).where(
                CustomerTasteProfile.customer_id == customer_id
            )
        )
        profile = existing.scalar_one_or_none()
        if profile is not None:
            return profile
        # No profile yet — try to build one inline. This is best-effort:
        # the daily cron normally takes care of it.
        return await EmbeddingService(self.db).recompute_taste_profile(customer_id)

    async def _preferred_sizes(self, customer_id: uuid.UUID) -> set[str]:
        """Return the lowercase set of sizes the customer has bought before."""
        result = await self.db.execute(
            select(Product.size)
            .join(TransactionItem, TransactionItem.product_id == Product.id)
            .join(Transaction, Transaction.id == TransactionItem.transaction_id)
            .where(
                Transaction.client_id == customer_id,
                Transaction.transaction_type == TransactionType.sale,
                Product.size.is_not(None),
            )
        )
        sizes = [s for (s,) in result.all() if s]
        if not sizes:
            return set()
        # Keep sizes that appear at least twice if the history is rich
        # enough; otherwise fall back to all distinct sizes.
        counts = Counter(s.lower() for s in sizes)
        if sum(counts.values()) >= 6:
            return {s for s, n in counts.items() if n >= 2}
        return set(counts.keys())

    async def _preferred_colors(self, customer_id: uuid.UUID) -> list[str]:
        result = await self.db.execute(
            select(Product.color)
            .join(TransactionItem, TransactionItem.product_id == Product.id)
            .join(Transaction, Transaction.id == TransactionItem.transaction_id)
            .where(
                Transaction.client_id == customer_id,
                Transaction.transaction_type == TransactionType.sale,
                Product.color.is_not(None),
            )
        )
        counts = Counter(c.lower() for (c,) in result.all() if c)
        return [c for c, _ in counts.most_common(3)]

    async def _last_purchases(
        self, customer_id: uuid.UUID, limit: int
    ) -> list[dict]:
        result = await self.db.execute(
            select(Product, Transaction.created_at)
            .join(TransactionItem, TransactionItem.product_id == Product.id)
            .join(Transaction, Transaction.id == TransactionItem.transaction_id)
            .where(
                Transaction.client_id == customer_id,
                Transaction.transaction_type == TransactionType.sale,
            )
            .order_by(desc(Transaction.created_at))
            .limit(limit)
        )
        rows = result.all()
        return [
            {
                "id": str(product.id),
                "name": product.name,
                "size": product.size,
                "price": float(product.sale_price),
                "date": (
                    created_at.strftime("%d/%m/%Y")
                    if created_at is not None
                    else "date inconnue"
                ),
            }
            for product, created_at in rows
        ]

    async def _days_since_last_visit(
        self, customer_id: uuid.UUID
    ) -> int | None:
        result = await self.db.execute(
            select(Transaction.created_at)
            .where(
                Transaction.client_id == customer_id,
                Transaction.transaction_type == TransactionType.sale,
            )
            .order_by(desc(Transaction.created_at))
            .limit(1)
        )
        last = result.scalar_one_or_none()
        if last is None:
            return None
        last_aware = last if last.tzinfo else last.replace(tzinfo=timezone.utc)
        return max(0, (datetime.now(timezone.utc) - last_aware).days)

    @staticmethod
    def _diversify_by_category(
        candidates: Iterable[tuple[Product, float]], *, top_n: int
    ) -> list[tuple[Product, float]]:
        """Walk the score-sorted candidates, keeping at most one per category."""
        seen: set[uuid.UUID] = set()
        diversified: list[tuple[Product, float]] = []
        for product, score in candidates:
            if product.category_id in seen:
                continue
            diversified.append((product, score))
            seen.add(product.category_id)
            if len(diversified) >= top_n:
                break
        return diversified

    async def _cold_start(
        self, customer: Client, recommendation_set_id: uuid.UUID, top_n: int
    ) -> dict:
        """Fall back to "newest in stock" when we have no taste signal."""
        result = await self.db.execute(
            select(Product)
            .where(
                Product.status.in_(
                    [ProductStatus.display, ProductStatus.stock]
                )
            )
            .order_by(desc(Product.created_at))
            .limit(top_n)
        )
        products = result.scalars().all()
        if not products:
            return {
                "recommendation_set_id": str(recommendation_set_id),
                "message": (
                    f"Bonjour {customer.first_name} ! Notre stock actuel est "
                    "réduit, repassez en boutique cette semaine — nous aurons "
                    "de nouvelles arrivées."
                ),
                "products": [],
                "algo_version": ALGO_VERSION,
                "prompt_version": PROMPT_VERSION,
                "fallback_used": True,
            }
        message = (
            f"Bonjour {customer.first_name} ! Voici nos dernières arrivées "
            "qui pourraient vous plaire ; venez les essayer en boutique."
        )
        return {
            "recommendation_set_id": str(recommendation_set_id),
            "message": message,
            "products": [
                {
                    "id": str(p.id),
                    "product_id": str(p.id),
                    "name": p.name,
                    "size": p.size,
                    "color": p.color,
                    "brand": p.brand,
                    "sale_price": float(p.sale_price),
                    "price_cents": int(round(float(p.sale_price) * 100)),
                    "score": None,
                    "photo_url": p.photo_url,
                }
                for p in products
            ],
            "algo_version": ALGO_VERSION,
            "prompt_version": PROMPT_VERSION,
            "fallback_used": True,
        }

    # -- Message rendering --------------------------------------------------

    async def _render_message(
        self,
        *,
        customer: Client,
        days_since_last_visit: int | None,
        last_purchases: list[dict],
        preferred_sizes: list[str],
        preferred_colors: list[str],
        candidates: list[dict],
        weather_summary: str | None,
    ) -> tuple[str, bool]:
        """Try Anthropic, fall back to a deterministic template on failure."""
        if not settings.ANTHROPIC_API_KEY:
            logger.info("Personal Shopper: no Anthropic key, using fallback")
            return (
                self._fallback_message(customer, last_purchases, candidates),
                True,
            )

        user_prompt = _build_user_prompt(
            customer=customer,
            days_since_last_visit=days_since_last_visit,
            last_purchases=last_purchases,
            preferred_sizes=preferred_sizes,
            preferred_colors=preferred_colors,
            candidates=candidates,
            weather_summary=weather_summary,
        )

        try:
            import anthropic

            client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
            message = await client.messages.create(
                model=DEFAULT_MODEL,
                max_tokens=512,
                system=_system_prompt(),
                messages=[{"role": "user", "content": user_prompt}],
            )
            text = message.content[0].text if message.content else ""
            text = text.strip()
            if not text:
                return (
                    self._fallback_message(customer, last_purchases, candidates),
                    True,
                )
            return text, False
        except Exception as exc:  # pragma: no cover — covered by fallback test
            logger.warning("Personal Shopper Claude call failed: %s", exc)
            return (
                self._fallback_message(customer, last_purchases, candidates),
                True,
            )

    @staticmethod
    def _fallback_message(
        customer: Client,
        last_purchases: list[dict],
        candidates: list[dict],
    ) -> str:
        """Deterministic template used when the Anthropic API is unreachable."""
        opener = f"Bonjour {customer.first_name},"
        if last_purchases:
            ref = last_purchases[0]
            opener += (
                f" depuis votre dernier passage (où vous aviez choisi "
                f"{ref['name']}), nous avons reçu de nouvelles pièces."
            )
        else:
            opener += " voici une sélection que nous avons préparée pour vous."
        lines = [opener, ""]
        for c in candidates[:5]:
            size = f" ({c.get('size')})" if c.get("size") else ""
            lines.append(
                f"- **{c['name']}**{size} — {_format_currency(c['price'])}"
            )
        lines.append("")
        lines.append("Venez les essayer cette semaine en boutique.")
        return "\n".join(lines)
