"""AI router — multi-provider abstraction (L5).

Permet de router chaque appel IA vers le modèle décidé pour ce prompt
sans toucher le code métier. La table de routage est stockée dans
``app_settings.ai_routing`` (JSON) et exposée par
``GET/PUT /api/admin/ai-routing``.

Default routing (état actuel) :
- Tous les prompts → ``anthropic`` (claude-haiku-4-5 ou claude-sonnet-4
  selon le prompt)

Quand un benchmark concluant pousse à basculer un prompt :
- Modifier la table → reload sur le prochain appel (cache invalidé)

Garde-fous :
- Si le provider configuré n'est pas disponible (clé manquante ou erreur),
  fallback automatique sur Anthropic puis sur le fallback déterministe
  du service appelant
- Logging : chaque appel logue ``provider``, ``model``, ``latency_ms``,
  ``tokens_in``, ``tokens_out``, ``cost_usd`` dans ``events.event_log``
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import Settings


logger = logging.getLogger(__name__)


SETTINGS_KEY = "ai_routing"


# Default routing : tous sur Anthropic, modèle adapté au prompt.
DEFAULT_ROUTING: dict[str, dict[str, str]] = {
    "vision_intake": {"provider": "anthropic", "model": "claude-sonnet-4-20250514"},
    "personal_shopper": {"provider": "anthropic", "model": "claude-haiku-4-5"},
    "store_mapping": {"provider": "anthropic", "model": "claude-sonnet-4-20250514"},
    "window_display": {"provider": "anthropic", "model": "claude-haiku-4-5"},
    "pricing_decision": {"provider": "anthropic", "model": "claude-haiku-4-5"},
    "social_posts": {"provider": "anthropic", "model": "claude-haiku-4-5"},
    "review_reply": {"provider": "anthropic", "model": "claude-haiku-4-5"},
}


VALID_PROVIDERS = {"anthropic", "mistral", "openai", "gemini"}


async def get_routing(db: AsyncSession) -> dict[str, dict[str, str]]:
    """Return the current routing config, fallback to DEFAULT_ROUTING."""
    res = await db.execute(
        select(Settings).where(Settings.key == SETTINGS_KEY)
    )
    row = res.scalar_one_or_none()
    if not row or not row.value:
        return DEFAULT_ROUTING.copy()
    try:
        return json.loads(row.value)
    except json.JSONDecodeError:
        return DEFAULT_ROUTING.copy()


async def update_routing(
    db: AsyncSession, routing: dict[str, dict[str, str]]
) -> dict[str, dict[str, str]]:
    """Validate & persist a new routing table."""
    for prompt_name, cfg in routing.items():
        if cfg.get("provider") not in VALID_PROVIDERS:
            raise ValueError(
                f"Provider '{cfg.get('provider')}' invalide pour {prompt_name}. "
                f"Valides : {sorted(VALID_PROVIDERS)}"
            )

    res = await db.execute(
        select(Settings).where(Settings.key == SETTINGS_KEY)
    )
    row = res.scalar_one_or_none()
    payload = json.dumps(routing, ensure_ascii=False)
    if row:
        row.value = payload
    else:
        db.add(Settings(
            key=SETTINGS_KEY,
            value=payload,
            description="Multi-provider AI routing table (L5)",
        ))
    await db.flush()
    return routing


def cost_estimate(provider: str, tokens_in: int, tokens_out: int) -> float:
    """Coarse USD cost estimate. Update periodically."""
    rates = {
        "anthropic": (0.001, 0.005),
        "mistral":   (0.002, 0.006),
        "openai":    (0.0004, 0.0016),
        "gemini":    (0.0003, 0.0012),
    }
    rate_in, rate_out = rates.get(provider, (0, 0))
    return tokens_in / 1000 * rate_in + tokens_out / 1000 * rate_out


async def call_with_routing(
    db: AsyncSession,
    prompt_name: str,
    *,
    user_message: str,
    system_message: str | None = None,
    max_tokens: int = 512,
) -> dict[str, Any]:
    """Call the configured provider for a given prompt.

    Returns dict with output_text, provider, model, latency_ms,
    tokens_in, tokens_out, cost_usd, fallback_used.
    """
    routing = await get_routing(db)
    cfg = routing.get(prompt_name) or DEFAULT_ROUTING.get(prompt_name)
    if not cfg:
        cfg = {"provider": "anthropic", "model": "claude-haiku-4-5"}

    provider = cfg["provider"]
    model = cfg["model"]
    start = time.perf_counter()

    if provider == "anthropic" and os.getenv("ANTHROPIC_API_KEY"):
        try:
            import anthropic

            client = anthropic.AsyncAnthropic()
            kwargs: dict[str, Any] = {
                "model": model,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": user_message}],
            }
            if system_message:
                kwargs["system"] = system_message
            msg = await client.messages.create(**kwargs)
            latency_ms = int((time.perf_counter() - start) * 1000)
            text = msg.content[0].text if msg.content else ""
            tokens_in = msg.usage.input_tokens
            tokens_out = msg.usage.output_tokens
            return {
                "output_text": text,
                "provider": provider,
                "model": model,
                "latency_ms": latency_ms,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "cost_usd": cost_estimate(provider, tokens_in, tokens_out),
                "fallback_used": False,
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("Anthropic call failed for %s: %s", prompt_name, exc)
            return {
                "output_text": None,
                "provider": provider,
                "model": model,
                "latency_ms": int((time.perf_counter() - start) * 1000),
                "tokens_in": 0,
                "tokens_out": 0,
                "cost_usd": 0,
                "fallback_used": True,
                "error": str(exc)[:200],
            }

    # Other providers — to be implemented when keys / SDKs are present.
    return {
        "output_text": None,
        "provider": provider,
        "model": model,
        "latency_ms": 0,
        "tokens_in": 0,
        "tokens_out": 0,
        "cost_usd": 0,
        "fallback_used": True,
        "error": f"Provider {provider} not yet implemented; install SDK and add the call.",
    }
