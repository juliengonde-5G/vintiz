"""Scoring configuration — DB-backed weights with hot-reload (L4).

Stores the scoring config in ``app_settings`` table under the unique key
``scoring_config_v1``. The service exposes get / update / reset and a
deterministic ``DEFAULT_CONFIG`` that mirrors the hardcoded weights from
``services/scoring_service.py:137-144``.

Schema (JSON in ``app_settings.value``):

{
  "version": 2,
  "weights": {
    "age": 0.27, "price": 0.18, "condition": 0.18,
    "brand": 0.13, "category": 0.09, "photos": 0.05,
    "season_transition": 0.05, "fashion_watch": 0.05
  },
  "age_decay": {
    "curve": "linear",            // linear | exponential | step
    "max_score_days": 0,
    "min_score_days": 60,
    "saturation_days": 90
  },
  "season_boost": {
    "enabled": true,
    "boost_pct": 0.15,
    "category_calendar": {
      "Manteau": [10, 11, 12, 1, 2],
      "Robe": [4, 5, 6, 7, 8],
      "Maillot": [5, 6, 7]
    }
  },
  "consignment_threshold": {
    "enabled": true,
    "max_days": 120,
    "action_after": "RETURNED_TO_SORTING"
  },
  "updated_by": "camille@vintiz.fr",
  "updated_at": "2026-05-...",
  "version_history": []  // last 10 versions for audit trail
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


# Default v2 — 8 components (legacy v1 = 6 first weights summing to 1.0).
DEFAULT_CONFIG_V2: dict[str, Any] = {
    "version": 2,
    "weights": {
        "age": 0.27,
        "price": 0.18,
        "condition": 0.18,
        "brand": 0.13,
        "category": 0.09,
        "photos": 0.05,
        "season_transition": 0.05,
        "fashion_watch": 0.05,
    },
    "age_decay": {
        "curve": "linear",
        "max_score_days": 0,
        "min_score_days": 60,
        "saturation_days": 90,
    },
    "season_boost": {
        "enabled": True,
        "boost_pct": 0.15,
        "category_calendar": {
            "Manteau": [10, 11, 12, 1, 2],
            "Robe": [4, 5, 6, 7, 8],
            "Maillot": [5, 6, 7],
            "Pull": [10, 11, 12, 1, 2, 3],
            "Veste": [3, 4, 5, 9, 10, 11],
        },
    },
    "consignment_threshold": {
        "enabled": True,
        "max_days": 120,
        "action_after": "RETURNED_TO_SORTING",
    },
    "updated_by": None,
    "updated_at": None,
    "version_history": [],
}


# v1 (6 components) — for "Restaurer v1" button in the UI.
DEFAULT_CONFIG_V1: dict[str, Any] = {
    "version": 1,
    "weights": {
        "age": 0.30,
        "price": 0.20,
        "condition": 0.20,
        "brand": 0.15,
        "category": 0.10,
        "photos": 0.05,
        "season_transition": 0.0,
        "fashion_watch": 0.0,
    },
    "age_decay": {
        "curve": "linear",
        "max_score_days": 0,
        "min_score_days": 60,
        "saturation_days": 90,
    },
    "season_boost": {
        "enabled": False,
        "boost_pct": 0.0,
        "category_calendar": {},
    },
    "consignment_threshold": {
        "enabled": False,
        "max_days": 120,
        "action_after": "RETURNED_TO_SORTING",
    },
    "updated_by": None,
    "updated_at": None,
    "version_history": [],
}


def _validate_weights(weights: dict[str, float]) -> None:
    """Check that the 8 weights are present, in [0, 1], and sum to ~1.0."""
    expected_keys = {
        "age", "price", "condition", "brand",
        "category", "photos", "season_transition", "fashion_watch",
    }
    missing = expected_keys - set(weights.keys())
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Poids manquants : {sorted(missing)}",
        )
    for k, v in weights.items():
        if not isinstance(v, (int, float)) or v < 0 or v > 1:
            raise HTTPException(
                status_code=400,
                detail=f"Poids '{k}' invalide : doit être dans [0, 1] (reçu {v!r})",
            )
    total = sum(weights.values())
    if abs(total - 1.0) > 0.01:
        raise HTTPException(
            status_code=400,
            detail=f"Somme des poids = {total:.3f}, doit valoir 1.0 (±1%)",
        )


def _validate_age_decay(age_decay: dict) -> None:
    if age_decay.get("curve") not in {"linear", "exponential", "step"}:
        raise HTTPException(
            status_code=400,
            detail="age_decay.curve doit être linear | exponential | step",
        )
    for k in ("max_score_days", "min_score_days", "saturation_days"):
        if not isinstance(age_decay.get(k), int) or age_decay[k] < 0:
            raise HTTPException(
                status_code=400,
                detail=f"age_decay.{k} doit être un entier ≥ 0",
            )


def _validate_payload(payload: dict) -> None:
    if "weights" not in payload:
        raise HTTPException(status_code=400, detail="Champ 'weights' obligatoire")
    _validate_weights(payload["weights"])
    if "age_decay" in payload:
        _validate_age_decay(payload["age_decay"])


async def get_scoring_config(db: AsyncSession) -> dict[str, Any]:
    """Return the current scoring config. If unset, returns DEFAULT_CONFIG_V2.

    The fallback ensures ``compute_score`` always has a config to read from
    even before the first save.
    """
    result = await db.execute(
        select(Settings).where(Settings.key == SETTINGS_KEY)
    )
    row = result.scalar_one_or_none()
    if not row or not row.value:
        return DEFAULT_CONFIG_V2.copy()
    try:
        return json.loads(row.value)
    except json.JSONDecodeError:
        return DEFAULT_CONFIG_V2.copy()


async def update_scoring_config(
    db: AsyncSession,
    payload: dict[str, Any],
    user_email: str | None = None,
) -> dict[str, Any]:
    """Validate and persist a new scoring config.

    Rolls the previous version into ``version_history`` (capped at 10).
    """
    _validate_payload(payload)

    current = await get_scoring_config(db)

    new_config = {
        "version": payload.get("version", 2),
        "weights": payload["weights"],
        "age_decay": payload.get("age_decay", DEFAULT_CONFIG_V2["age_decay"]),
        "season_boost": payload.get(
            "season_boost", DEFAULT_CONFIG_V2["season_boost"]
        ),
        "consignment_threshold": payload.get(
            "consignment_threshold", DEFAULT_CONFIG_V2["consignment_threshold"]
        ),
        "updated_by": user_email,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "version_history": (current.get("version_history", []) + [
            {
                "weights": current.get("weights"),
                "updated_by": current.get("updated_by"),
                "updated_at": current.get("updated_at"),
            }
        ])[-10:],
    }

    result = await db.execute(
        select(Settings).where(Settings.key == SETTINGS_KEY)
    )
    row = result.scalar_one_or_none()
    if row:
        row.value = json.dumps(new_config, ensure_ascii=False)
    else:
        db.add(Settings(
            key=SETTINGS_KEY,
            value=json.dumps(new_config, ensure_ascii=False),
            description="Scoring config (8 components, decay, season, consignment)",
        ))
    await db.flush()
    return new_config


async def reset_scoring_config(
    db: AsyncSession,
    *,
    version: int = 2,
    user_email: str | None = None,
) -> dict[str, Any]:
    """Restore the default config (v1 or v2)."""
    default = DEFAULT_CONFIG_V2 if version == 2 else DEFAULT_CONFIG_V1
    return await update_scoring_config(db, default, user_email=user_email)
