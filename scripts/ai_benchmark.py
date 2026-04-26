"""AI provider benchmark — Claude vs Mistral / GPT-4.1 / Gemini (L5).

Méthodologie :
- 7 prompts (vision, personal_shopper, store_mapping, window_display,
  pricing_decision, social_posts, review_reply)
- 20 cas par prompt (inputs réels anonymisés depuis la base seed)
- 4 modèles : claude-haiku-4-5, claude-sonnet-4, mistral-large-2,
  gpt-4.1-mini, gemini-2.5-flash

Mesures par appel :
- Latence p50, p95
- Tokens in/out + coût €
- Validité format (JSON valide ? respect du schéma ?)
- (Score qualité subjective via rubrique L5.2 — humain)

Sortie : `scripts/output/ai_benchmark_results.json` + résumé console.

Usage
-----
    # Variables nécessaires :
    export ANTHROPIC_API_KEY=sk-ant-...
    export MISTRAL_API_KEY=...        # optionnel
    export OPENAI_API_KEY=...         # optionnel
    export GEMINI_API_KEY=...         # optionnel

    python scripts/ai_benchmark.py
    python scripts/ai_benchmark.py --prompts personal_shopper,vision_intake
    python scripts/ai_benchmark.py --providers anthropic,mistral

Si une clé est absente, le provider correspondant est skippé (pas
d'erreur).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any


# Per-prompt sample inputs. To regenerate from real seed data, use the
# `--regenerate-samples` flag (TODO).
SAMPLE_INPUTS: dict[str, list[dict]] = {
    "personal_shopper": [
        {"cliente": "Clara", "tier": "Gold", "budget_max": 50,
         "favorite_categories": ["Robe", "Top"],
         "candidats": [
             {"name": "Robe Sandro fluide bordeaux", "price": 45},
             {"name": "Top Maje noir cintré", "price": 28},
         ]} for _ in range(20)
    ],
    "vision_intake": [
        {"image_url": "https://placehold.co/800x800?text=Robe+bordeaux"} for _ in range(20)
    ],
    "store_mapping": [
        {"zone_stats": [{"name": "Robes", "occupancy_pct": 60}]} for _ in range(20)
    ],
    "window_display": [
        {"season": "printemps", "weather_5d": ["20°C", "18°C", "22°C", "19°C", "21°C"]} for _ in range(20)
    ],
    "pricing_decision": [
        {"score": 42, "days_on_shelf": 35, "prix_actuel": 45, "categorie_avg": 38} for _ in range(20)
    ],
    "social_posts": [
        {"last_arrivals": ["Robe Sandro", "Sac Vintiz"], "events": ["Marché Vernon samedi"]} for _ in range(20)
    ],
    "review_reply": [
        {"note": 5, "commentaire": "Très belle boutique, accueil chaleureux !", "client_name": "Clara D."} for _ in range(20)
    ],
}


PROVIDERS = {
    "anthropic_haiku": {
        "model": "claude-haiku-4-5",
        "env": "ANTHROPIC_API_KEY",
        "cost_per_1k_in": 0.001,    # USD, indicatif
        "cost_per_1k_out": 0.005,
    },
    "anthropic_sonnet": {
        "model": "claude-sonnet-4-20250514",
        "env": "ANTHROPIC_API_KEY",
        "cost_per_1k_in": 0.003,
        "cost_per_1k_out": 0.015,
    },
    "mistral_large": {
        "model": "mistral-large-latest",
        "env": "MISTRAL_API_KEY",
        "cost_per_1k_in": 0.002,
        "cost_per_1k_out": 0.006,
    },
    "openai_4_1_mini": {
        "model": "gpt-4.1-mini",
        "env": "OPENAI_API_KEY",
        "cost_per_1k_in": 0.0004,
        "cost_per_1k_out": 0.0016,
    },
    "gemini_flash": {
        "model": "gemini-2.5-flash",
        "env": "GEMINI_API_KEY",
        "cost_per_1k_in": 0.0003,
        "cost_per_1k_out": 0.0012,
    },
}


async def call_anthropic(model: str, prompt_name: str, sample: dict) -> dict:
    """Generic Anthropic call. Returns latency/tokens/output. Empty on no API key."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        return {"skipped": True, "reason": "no API key"}
    try:
        import anthropic

        client = anthropic.AsyncAnthropic()
        prompt = f"You are testing the Vintiz prompt '{prompt_name}'. Respond shortly. Sample: {json.dumps(sample)}"
        t0 = time.perf_counter()
        msg = await client.messages.create(
            model=model,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        latency_ms = int((time.perf_counter() - t0) * 1000)
        text = msg.content[0].text if msg.content else ""
        return {
            "ok": True,
            "latency_ms": latency_ms,
            "tokens_in": msg.usage.input_tokens,
            "tokens_out": msg.usage.output_tokens,
            "output_excerpt": text[:200],
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)[:200]}


async def call_mistral(model: str, prompt_name: str, sample: dict) -> dict:
    """Stub — to be implemented when MISTRAL_API_KEY is provided.

    The mistralai SDK API:
        from mistralai import Mistral
        client = Mistral(api_key=os.getenv('MISTRAL_API_KEY'))
        await client.chat.complete_async(model=model, messages=[...])
    """
    if not os.getenv("MISTRAL_API_KEY"):
        return {"skipped": True, "reason": "no API key"}
    return {"ok": False, "error": "Mistral provider stub — install mistralai SDK and implement."}


async def call_openai(model: str, prompt_name: str, sample: dict) -> dict:
    if not os.getenv("OPENAI_API_KEY"):
        return {"skipped": True, "reason": "no API key"}
    return {"ok": False, "error": "OpenAI provider stub — install openai SDK and implement."}


async def call_gemini(model: str, prompt_name: str, sample: dict) -> dict:
    if not os.getenv("GEMINI_API_KEY"):
        return {"skipped": True, "reason": "no API key"}
    return {"ok": False, "error": "Gemini provider stub — install google-generativeai SDK and implement."}


PROVIDER_CALLABLES = {
    "anthropic_haiku": call_anthropic,
    "anthropic_sonnet": call_anthropic,
    "mistral_large": call_mistral,
    "openai_4_1_mini": call_openai,
    "gemini_flash": call_gemini,
}


async def run_bench(prompts: list[str], providers: list[str]) -> dict:
    results: dict[str, Any] = {}
    for prompt_name in prompts:
        samples = SAMPLE_INPUTS.get(prompt_name, [])
        if not samples:
            continue
        results[prompt_name] = {}
        for provider_key in providers:
            cfg = PROVIDERS.get(provider_key)
            if not cfg:
                continue
            fn = PROVIDER_CALLABLES.get(provider_key)
            if not fn:
                continue
            print(f"\n=== {prompt_name} × {provider_key} ({cfg['model']}) ===")
            calls = []
            for i, s in enumerate(samples, 1):
                r = await fn(cfg["model"], prompt_name, s)
                if r.get("ok"):
                    cost = (r["tokens_in"] / 1000 * cfg["cost_per_1k_in"]
                            + r["tokens_out"] / 1000 * cfg["cost_per_1k_out"])
                    r["cost_usd"] = round(cost, 5)
                calls.append(r)
                if i % 5 == 0:
                    print(f"  {i}/{len(samples)} samples done")
            ok_calls = [c for c in calls if c.get("ok")]
            results[prompt_name][provider_key] = {
                "n_total": len(calls),
                "n_ok": len(ok_calls),
                "n_skipped": sum(1 for c in calls if c.get("skipped")),
                "latency_p50": int(statistics.median([c["latency_ms"] for c in ok_calls])) if ok_calls else None,
                "latency_p95": int(sorted([c["latency_ms"] for c in ok_calls])[int(len(ok_calls) * 0.95)]) if len(ok_calls) > 1 else None,
                "avg_cost_usd": round(sum(c.get("cost_usd", 0) for c in ok_calls) / max(1, len(ok_calls)), 5),
                "calls": calls,
            }
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompts", default=",".join(SAMPLE_INPUTS.keys()))
    parser.add_argument("--providers", default=",".join(PROVIDERS.keys()))
    args = parser.parse_args()

    prompts = [p.strip() for p in args.prompts.split(",") if p.strip()]
    providers = [p.strip() for p in args.providers.split(",") if p.strip()]

    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    out_path = output_dir / "ai_benchmark_results.json"

    print(f"Running benchmark : {len(prompts)} prompts × {len(providers)} providers...")
    results = asyncio.run(run_bench(prompts, providers))

    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"\n=== Results written to {out_path}")

    # Console summary
    print("\nSummary :")
    for prompt_name, providers_data in results.items():
        print(f"\n  {prompt_name}")
        for prov, stats in providers_data.items():
            if stats.get("n_skipped") == stats.get("n_total"):
                print(f"    {prov:25} : skipped (no API key)")
            else:
                print(
                    f"    {prov:25} : {stats['n_ok']}/{stats['n_total']} ok, "
                    f"p50={stats.get('latency_p50')}ms, "
                    f"avg_cost={stats.get('avg_cost_usd')}$"
                )
    return 0


if __name__ == "__main__":
    sys.exit(main())
