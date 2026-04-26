"""RFM segmentation (P4-007).

Computes per-customer Recency / Frequency / Monetary scores from sale
transactions, ranks each on a 1..5 scale (5 = best), and assigns a
marketing segment label (champion, loyal, …). The monthly cron persists
the result on ``Client.rfm_segment`` so other modules can target their
campaigns without recomputing.

Quintile-based ranking — distribution-friendly, doesn't require absolute
thresholds. With < 10 customers we still classify every row using the
fallback ``_label_from_scores`` table; the segments just won't be
balanced.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client
from app.models.pos import Transaction, TransactionType


# Whole-number scores 1..5; 5 = most recent / most frequent / highest spend.
_RANK_LEVELS = (1, 2, 3, 4, 5)


@dataclass
class RFMScore:
    customer_id: uuid.UUID
    recency_days: int
    frequency: int
    monetary: float
    r_score: int
    f_score: int
    m_score: int
    segment: str


# Standard 11-segment RFM grid simplified to 9 buckets for legibility.
# Inputs: (R, F, M) ∈ {1..5}³.
def _label_from_scores(r: int, f: int, m: int) -> str:
    if r == 5 and f >= 4 and m >= 4:
        return "champion"
    if r >= 4 and f >= 3 and m >= 3:
        return "loyal"
    if r == 5 and f <= 2:
        return "new"
    if r >= 4 and f <= 2:
        return "promising"
    if r <= 2 and f >= 4 and m >= 4:
        return "cant_lose"
    if r <= 2 and f >= 3 and m >= 3:
        return "at_risk"
    if r <= 2 and f >= 2:
        return "hibernating"
    if r == 1 and f == 1:
        return "lost"
    return "regular"


def _rank_quintiles(values: list[float], descending: bool = False) -> dict[int, int]:
    """Return ``{index_in_input → 1..5 score}`` based on quintile bucket.

    ``descending=True`` reverses the ordering so smaller values get the
    higher score (e.g. recency in days: smaller is more recent).
    """
    if not values:
        return {}
    sorted_indices = sorted(
        range(len(values)),
        key=lambda i: values[i],
        reverse=descending,
    )
    n = len(sorted_indices)
    result: dict[int, int] = {}
    for rank_pos, idx in enumerate(sorted_indices):
        # rank_pos ∈ [0, n-1]; map to 1..5 by reversed quintile order.
        # The lowest rank_pos belongs to the WORST values — score 1.
        # We want the BEST values to get score 5, so:
        bucket = min(5, int(rank_pos / max(n, 1) * 5) + 1)
        result[idx] = bucket
    return result


async def compute_rfm(
    db: AsyncSession, *, now: datetime | None = None
) -> list[RFMScore]:
    """Compute RFM scores for every client with at least one paid sale."""
    now = now or datetime.now(timezone.utc)

    rows_result = await db.execute(
        select(
            Transaction.client_id,
            func.max(Transaction.created_at).label("last_sale"),
            func.count(Transaction.id).label("freq"),
            func.coalesce(func.sum(Transaction.total_ttc), 0).label("monetary"),
        )
        .where(
            Transaction.transaction_type == TransactionType.sale,
            Transaction.client_id.is_not(None),
        )
        .group_by(Transaction.client_id)
    )
    rows = list(rows_result.all())
    if not rows:
        return []

    customer_ids = [r[0] for r in rows]
    last_sales = [r[1] for r in rows]
    freqs = [int(r[2]) for r in rows]
    monetaries = [float(r[3]) for r in rows]

    # Recency: lower is better → reverse the ranking so small values get 5.
    recency_days: list[float] = []
    for last in last_sales:
        if last is None:
            recency_days.append(9999.0)
            continue
        last_aware = last if last.tzinfo else last.replace(tzinfo=timezone.utc)
        recency_days.append(max(0.0, (now - last_aware).total_seconds() / 86400.0))

    r_scores = _rank_quintiles(recency_days, descending=True)
    f_scores = _rank_quintiles([float(f) for f in freqs], descending=False)
    m_scores = _rank_quintiles(monetaries, descending=False)

    out: list[RFMScore] = []
    for i, cid in enumerate(customer_ids):
        r = r_scores.get(i, 1)
        f = f_scores.get(i, 1)
        m = m_scores.get(i, 1)
        out.append(RFMScore(
            customer_id=cid,
            recency_days=int(recency_days[i]),
            frequency=freqs[i],
            monetary=monetaries[i],
            r_score=r,
            f_score=f,
            m_score=m,
            segment=_label_from_scores(r, f, m),
        ))
    return out


async def persist_segments(
    db: AsyncSession,
    scores: Iterable[RFMScore],
) -> int:
    """Write each customer's segment back to ``Client.rfm_segment``."""
    by_id = {s.customer_id: s for s in scores}
    if not by_id:
        return 0

    rows = await db.execute(
        select(Client).where(Client.id.in_(by_id.keys()))
    )
    touched = 0
    for client in rows.scalars().all():
        new_segment = by_id[client.id].segment
        if client.rfm_segment != new_segment:
            client.rfm_segment = new_segment
            touched += 1
    await db.flush()
    return touched


async def run_segmentation(db: AsyncSession) -> dict:
    """End-to-end pass for the cron / admin trigger."""
    scores = await compute_rfm(db)
    touched = await persist_segments(db, scores)
    counts: dict[str, int] = {}
    for s in scores:
        counts[s.segment] = counts.get(s.segment, 0) + 1
    return {
        "computed": len(scores),
        "updated": touched,
        "segments": counts,
    }


async def segment_summary(db: AsyncSession) -> dict[str, int]:
    """Return ``{segment: count}`` over all clients with a stamped tag."""
    result = await db.execute(
        select(Client.rfm_segment, func.count(Client.id))
        .where(Client.rfm_segment.is_not(None))
        .group_by(Client.rfm_segment)
    )
    return {row[0]: int(row[1]) for row in result.all()}
