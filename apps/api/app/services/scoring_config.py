"""Scoring configuration v3 — 5 criteria, hot-reload from ``app_settings``.

Stored in ``app_settings`` table under the unique key ``scoring_config_v1``
(key kept for backward compat with existing rows; payload is overwritten
in-place when the application boots with a v3 schema).

Schema (JSON in ``app_settings.value``):

{
  "version": 3,
  "weights": {
    "attractivity": 0.25,
    "season":       0.20,
    "age":          0.25,
    "trend":        0.15,
    "price":        0.15
  },
  "age_weeks_table": [20, 17, 13, 10, 6, 2],   // S1..S6+
  "max_weeks_on_shelf": 6,
  "season_calendar": {
    "Manteau": [10, 11, 12, 1, 2],
    "Robe":    [4, 5, 6, 7, 8],
    "Pull":    [10, 11, 12, 1, 2, 3],
    "Maillot": [5, 6, 7],
    "Veste":   [3, 4, 5, 9, 10, 11]
  },
  "price_thresholds": [0.7, 0.9, 1.1, 1.3],
  "price_points":     [20, 16, 12, 8, 4],
  "updated_by": "...",
  "updated_at": "...",
  "version_history": []  // last 10 versions for audit
}
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import Settings


SETTINGS_KEY = "scoring_config_v1"


DEFAULT_CONFIG: dict[str, Any] = {
    "version": 3,
    "weights": {
        "attractivity": 0.25,
        "season": 0.20,
        "age": 0.25,
        "trend": 0.15,
        "price": 0.15,
    },
    "age_weeks_table": [20, 17, 13, 10, 6, 2],
    "max_weeks_on_shelf": 6,
    "season_calendar": {
        "Manteau": [10, 11, 12, 1, 2],
        "Robe": [4, 5, 6, 7, 8],
        "Pull": [10, 11, 12, 1, 2, 3],
        "Maillot": [5, 6, 7],
        "Veste": [3, 4, 5, 9, 10, 11],
    },
    "price_thresholds": [0.7, 0.9, 1.1, 1.3],
    "price_points": [20, 16, 12, 8, 4],
    "updated_by": None,
    "updated_at": None,
    "version_history": [],
}


WEIGHT_KEYS = ("attractivity", "season", "age", "trend", "price")


def _validate_weights(weights: dict[str, float]) -> None:
    missing = set(WEIGHT_KEYS) - set(weights.keys())
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Poids manquants : {sorted(missing)}",
        )
    for k in WEIGHT_KEYS:
        v = weights[k]
        if not isinstance(v, (int, float)) or v < 0 or v > 1:
            raise HTTPException(
                status_code=400,
                detail=f"Poids '{k}' invalide (doit être dans [0, 1], reçu {v!r})",
            )
    total = sum(float(weights[k]) for k in WEIGHT_KEYS)
    if abs(total - 1.0) > 0.01:
        raise HTTPException(
            status_code=400,
            detail=f"Somme des poids = {total:.3f}, doit valoir 1.0 (±1%)",
        )


def _validate_age_weeks_table(table: list) -> None:
    if not isinstance(table, list) or len(table) < 1:
        raise HTTPException(
            status_code=400,
            detail="age_weeks_table doit être une liste non vide",
        )
    for v in table:
        if not isinstance(v, (int, float)) or v < 0 or v > 20:
            raise HTTPException(
                status_code=400,
                detail=f"Point semaine '{v}' hors [0, 20]",
            )


def _validate_payload(payload: dict) -> None:
    if "weights" not in payload:
        raise HTTPException(status_code=400, detail="Champ 'weights' obligatoire")
    _validate_weights(payload["weights"])
    if "age_weeks_table" in payload:
        _validate_age_weeks_table(payload["age_weeks_table"])


async def get_scoring_config(db: AsyncSession) -> dict[str, Any]:
    """Return the current scoring config; falls back to ``DEFAULT_CONFIG``.

    If the persisted JSON is from an earlier schema (v1/v2) we ignore it and
    return the default — the codebase no longer supports those weights.
    """
    result = await db.execute(select(Settings).where(Settings.key == SETTINGS_KEY))
    row = result.scalar_one_or_none()
    if not row or not row.value:
        return DEFAULT_CONFIG.copy()
    try:
        cfg = json.loads(row.value)
    except json.JSONDecodeError:
        return DEFAULT_CONFIG.copy()
    if int(cfg.get("version", 0)) < 3:
        return DEFAULT_CONFIG.copy()
    return cfg


async def update_scoring_config(
    db: AsyncSession,
    payload: dict[str, Any],
    user_email: str | None = None,
) -> dict[str, Any]:
    """Validate and persist a new config (v3 only)."""
    _validate_payload(payload)
    current = await get_scoring_config(db)

    new_config = {
        "version": 3,
        "weights": {k: float(payload["weights"][k]) for k in WEIGHT_KEYS},
        "age_weeks_table": payload.get("age_weeks_table", DEFAULT_CONFIG["age_weeks_table"]),
        "max_weeks_on_shelf": int(payload.get("max_weeks_on_shelf", 6)),
        "season_calendar": payload.get("season_calendar", DEFAULT_CONFIG["season_calendar"]),
        "price_thresholds": payload.get("price_thresholds", DEFAULT_CONFIG["price_thresholds"]),
        "price_points": payload.get("price_points", DEFAULT_CONFIG["price_points"]),
        "updated_by": user_email,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "version_history": (
            (current.get("version_history") or [])
            + [
                {
                    "weights": current.get("weights"),
                    "updated_by": current.get("updated_by"),
                    "updated_at": current.get("updated_at"),
                }
            ]
        )[-10:],
    }

    result = await db.execute(select(Settings).where(Settings.key == SETTINGS_KEY))
    row = result.scalar_one_or_none()
    if row:
        row.value = json.dumps(new_config, ensure_ascii=False)
    else:
        db.add(
            Settings(
                key=SETTINGS_KEY,
                value=json.dumps(new_config, ensure_ascii=False),
                description="Scoring config v3 (5 criteria)",
            )
        )
    await db.flush()
    return new_config


async def reset_scoring_config(
    db: AsyncSession,
    *,
    user_email: str | None = None,
) -> dict[str, Any]:
    """Restore the default v3 config."""
    return await update_scoring_config(db, DEFAULT_CONFIG.copy(), user_email=user_email)
