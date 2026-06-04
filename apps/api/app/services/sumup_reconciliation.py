"""SumUp ↔ Vintiz reconciliation service (feature C).

Compare les paiements CB Vintiz d'une journée avec les transactions SumUp
de la même journée pour permettre au comptable de repérer les écarts avant
l'envoi du FEC.

Stratégie de matching (en cascade) :

1. **Match par identifiant SumUp** — quand ``Payment.sumup_transaction_id``
   est posé (cas nominal : polling Solo Reader OK, checkout complété
   normalement). Pas d'ambiguïté possible.

2. **Match par montant** (fallback) — quand l'ID Vintiz manque (le caissier
   a confirmé manuellement, le polling a expiré, etc.) ou quand le push
   du Reader n'a pas posé l'ID côté Vintiz. On apparie 1↔1 les paiements
   Vintiz "orphelins" et les transactions SumUp "orphelines" qui ont le
   **même montant à 0,01 € près**. En cas de doublon de montant, on associe
   par ordre d'apparition (FIFO par horodatage) pour rester déterministe.

Le rapport expose des **diagnostics** (clé API présente ? appels API ?
pagination consommée ? erreur réseau ?) pour que le manager comprenne
*pourquoi* la liste SumUp est vide quand ça arrive — pas juste « 0 ».
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

_log = logging.getLogger("vintiz.reconciliation")

SUMUP_API_BASE = "https://api.sumup.com/v0.1"
# Limite max imposée par SumUp côté API. La pagination ré-interroge avec
# ``oldest_ref`` jusqu'à épuisement.
SUMUP_PAGE_LIMIT = 100
SUMUP_PAGES_HARD_CAP = 20  # Sécurité : 20 × 100 = 2 000 txns / jour max


def _iso(dt) -> str | None:
    """Datetime → ISO 8601 UTC ``Z``. Renvoie None si vide."""
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class SumUpTx:
    transaction_id: str
    transaction_code: str
    amount: float
    currency: str
    status: str
    timestamp: str
    card_brand: str = ""
    card_last4: str = ""


@dataclass
class ReconciliationLine:
    vintiz_payment_id: str
    vintiz_transaction_number: int
    vintiz_amount: float
    sumup_transaction_id: str | None
    sumup_transaction_code: str | None
    sumup_amount: float | None
    # "matched"       = appariement par ID exact
    # "matched_amount"= appariement fallback par montant
    # "vintiz_only"   = pas de SumUp en face
    # "sumup_only"    = pas de Vintiz en face
    # "amount_mismatch" = ID matché mais montants divergents
    status: str
    delta: float = 0.0
    # Chronodatage — ISO 8601 UTC (front formate localement en HH:MM:SS).
    # Vintiz = Transaction.created_at, SumUp = item["timestamp"]. Permet au
    # comptable de retrouver le ticket physique correspondant à la ligne et
    # de repérer un écart temporel (paiement validé à 11h17 vs SumUp à 11h25
    # → polling tardif, mais bien la même vente).
    vintiz_timestamp: str | None = None
    sumup_timestamp: str | None = None


@dataclass
class ReconciliationReport:
    reconciliation_date: str
    total_vintiz_card: float
    total_sumup: float
    delta: float
    matched_count: int
    unmatched_vintiz: int
    unmatched_sumup: int
    lines: list[ReconciliationLine] = field(default_factory=list)
    # Diagnostics — non sensibles. Aident à comprendre un "0 SumUp" trompeur
    # (sans clé → 0, erreur réseau → 0, vrai 0 → 0).
    api_key_present: bool = False
    api_error: str | None = None
    api_pages_fetched: int = 0
    api_raw_tx_count: int = 0
    matched_by_amount: int = 0


class SumUpReconciliationService:
    def __init__(self, db) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------
    def _get_sumup_api_key(self) -> str | None:
        try:
            from app.services.app_config import get_section
            s = get_section("sumup")
            key = (s.get("api_key") or "").strip()
            if key:
                return key
        except Exception:
            pass
        import os
        return os.getenv("SUMUP_API_KEY") or None

    # ------------------------------------------------------------------
    # SumUp API
    # ------------------------------------------------------------------
    def _fetch_sumup_page(
        self, api_key: str, target_date: date, *, oldest_ref: str | None
    ) -> tuple[list[dict], str | None]:
        """Une page de l'API SumUp. Renvoie (items, error_str_or_None).

        Note historique : on n'envoie PAS de filtre ``statuses`` côté serveur.
        SumUp parse ce paramètre comme un array et renvoie systématiquement
        ``400 Invalid Array value`` quand on lui passe une valeur scalaire
        (et la syntaxe array varie selon le SDK). On filtre donc en sortie
        sur ``status == "SUCCESSFUL"`` côté Python (cf. ``_fetch_sumup_transactions``).
        """
        import json
        from urllib.error import HTTPError, URLError
        from urllib.parse import urlencode
        from urllib.request import Request, urlopen

        params: dict[str, Any] = {
            "oldest_time": f"{target_date.isoformat()}T00:00:00Z",
            "newest_time": f"{target_date.isoformat()}T23:59:59Z",
            "limit": SUMUP_PAGE_LIMIT,
            "order": "ascending",
        }
        if oldest_ref:
            params["oldest_ref"] = oldest_ref
        url = f"{SUMUP_API_BASE}/me/transactions/history?{urlencode(params)}"
        req = Request(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
            },
        )
        try:
            with urlopen(req, timeout=15) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8", errors="replace")[:200]
            except Exception:
                detail = ""
            return [], f"HTTP {exc.code} {exc.reason} {detail}".strip()
        except URLError as exc:
            return [], f"Réseau : {exc.reason}"
        except Exception as exc:  # noqa: BLE001
            return [], f"Erreur : {exc}"

        items = payload.get("items", payload if isinstance(payload, list) else [])
        return items, None

    def _fetch_sumup_transactions(
        self, api_key: str, target_date: date
    ) -> tuple[list[SumUpTx], str | None, int]:
        """Tire toutes les pages du jour. Tuple (txns, error, pages_fetched).

        Pagination par ``oldest_ref`` : à chaque page, on note le dernier
        ``id`` reçu et on ré-interroge avec ``oldest_ref=<id>`` jusqu'à ce
        que la page renvoie moins de 100 résultats (ou qu'on tape le hard
        cap de sécurité).
        """
        all_items: list[dict] = []
        oldest_ref: str | None = None
        pages = 0
        last_error: str | None = None
        while pages < SUMUP_PAGES_HARD_CAP:
            items, err = self._fetch_sumup_page(
                api_key, target_date, oldest_ref=oldest_ref
            )
            pages += 1
            if err is not None:
                last_error = err
                break
            if not items:
                break
            all_items.extend(items)
            if len(items) < SUMUP_PAGE_LIMIT:
                break
            # Cursor pour la page suivante : dernier id reçu (order ascending).
            last_id = items[-1].get("id") or items[-1].get("transaction_code") or ""
            if not last_id or last_id == oldest_ref:
                # On boucle sur le même cursor → abort pour ne pas tourner.
                break
            oldest_ref = last_id

        out: list[SumUpTx] = []
        for item in all_items:
            # Filtre côté client : on ne garde que les transactions réussies.
            # SumUp refuse le filtre ``statuses=SUCCESSFUL`` en query string
            # (400 "Invalid Array value"), d'où ce filtre Python.
            raw_status = str(item.get("status") or "").upper()
            if raw_status and raw_status not in {"SUCCESSFUL", "PAID"}:
                continue
            out.append(
                SumUpTx(
                    transaction_id=str(item.get("id") or ""),
                    transaction_code=str(item.get("transaction_code") or ""),
                    amount=float(item.get("amount") or 0),
                    currency=str(item.get("currency") or "EUR"),
                    status=raw_status or "SUCCESSFUL",
                    timestamp=str(item.get("timestamp") or ""),
                    card_brand=str((item.get("card") or {}).get("brand") or ""),
                    card_last4=str((item.get("card") or {}).get("last_4_digits") or ""),
                )
            )
        return out, last_error, pages

    # ------------------------------------------------------------------
    # Matching
    # ------------------------------------------------------------------
    @staticmethod
    def _cents(x: float) -> int:
        return int(round(x * 100))

    def _pair_by_amount(
        self,
        unmatched_vintiz: list[tuple[Any, Any]],
        unmatched_sumup: list[SumUpTx],
    ) -> list[tuple[Any, Any, SumUpTx]]:
        """Apparie 1↔1 par montant identique. Retourne triplets (payment, txn, sumup_tx).

        Stratégie déterministe : on groupe les deux côtés par montant en
        centimes, puis pour chaque montant on apparie FIFO (ordre des listes
        d'entrée — pour Vintiz, c'est l'ordre des paiements en base ;
        pour SumUp, c'est l'ordre ascendant des timestamps).
        """
        from collections import defaultdict, deque

        sumup_by_cents: dict[int, deque[SumUpTx]] = defaultdict(deque)
        for tx in unmatched_sumup:
            sumup_by_cents[self._cents(tx.amount)].append(tx)

        pairs: list[tuple[Any, Any, SumUpTx]] = []
        for payment, txn in unmatched_vintiz:
            cents = self._cents(float(payment.amount))
            bucket = sumup_by_cents.get(cents)
            if bucket:
                tx = bucket.popleft()
                if not bucket:
                    sumup_by_cents.pop(cents, None)
                pairs.append((payment, txn, tx))
        return pairs

    # ------------------------------------------------------------------
    # Public entrypoint
    # ------------------------------------------------------------------
    async def reconcile(self, target_date: date) -> ReconciliationReport:
        from sqlalchemy import select
        from app.models.pos import Payment, PaymentMethod, Transaction, TransactionType

        api_key = self._get_sumup_api_key()
        api_key_present = bool(api_key)

        start = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59, tzinfo=timezone.utc)
        stmt = (
            select(Payment, Transaction)
            .join(Transaction, Payment.transaction_id == Transaction.id)
            .where(Payment.method == PaymentMethod.card)
            .where(Transaction.transaction_type == TransactionType.sale)
            .where(Transaction.created_at >= start)
            .where(Transaction.created_at <= end)
            .order_by(Transaction.created_at.asc())
        )
        result = await self.db.execute(stmt)
        rows: list[tuple[Any, Any]] = list(result.all())
        total_vintiz = round(sum(float(p.amount) for p, _ in rows), 2)

        sumup_txs: list[SumUpTx] = []
        api_error: str | None = None
        pages_fetched = 0
        if api_key:
            sumup_txs, api_error, pages_fetched = self._fetch_sumup_transactions(
                api_key, target_date
            )
        elif rows:
            # Pas de clé mais des paiements à réconcilier → on l'écrit
            # explicitement plutôt que de laisser le manager deviner.
            api_error = "Clé SumUp absente (SUMUP_API_KEY ou /settings > Paiement)."

        total_sumup = round(sum(tx.amount for tx in sumup_txs), 2)
        sumup_by_id: dict[str, SumUpTx] = {
            tx.transaction_id: tx for tx in sumup_txs if tx.transaction_id
        }

        # ── Passe 1 : match par ID exact ───────────────────────────────
        lines: list[ReconciliationLine] = []
        matched_by_id = 0
        unmatched_payments: list[tuple[Any, Any]] = []
        matched_sumup_ids: set[str] = set()

        for payment, txn in rows:
            sid = (getattr(payment, "sumup_transaction_id", None) or "").strip()
            sumup_tx = sumup_by_id.get(sid) if sid else None
            if sumup_tx is not None:
                delta = round(float(payment.amount) - sumup_tx.amount, 2)
                if abs(delta) < 0.01:
                    matched_by_id += 1
                    status = "matched"
                else:
                    status = "amount_mismatch"
                matched_sumup_ids.add(sumup_tx.transaction_id)
                lines.append(
                    ReconciliationLine(
                        vintiz_payment_id=str(payment.id),
                        vintiz_transaction_number=txn.transaction_number,
                        vintiz_amount=float(payment.amount),
                        sumup_transaction_id=sumup_tx.transaction_id,
                        sumup_transaction_code=sumup_tx.transaction_code,
                        sumup_amount=sumup_tx.amount,
                        status=status,
                        delta=delta,
                        vintiz_timestamp=_iso(txn.created_at),
                        sumup_timestamp=sumup_tx.timestamp or None,
                    )
                )
            else:
                unmatched_payments.append((payment, txn))

        # ── Passe 2 : match par montant (fallback) ─────────────────────
        unmatched_sumup_txs = [
            tx for tx in sumup_txs if tx.transaction_id not in matched_sumup_ids
        ]
        amount_pairs = self._pair_by_amount(unmatched_payments, unmatched_sumup_txs)
        paid_payment_ids = {p.id for p, _, _ in amount_pairs}
        paid_sumup_ids = {tx.transaction_id for _, _, tx in amount_pairs}

        for payment, txn, tx in amount_pairs:
            lines.append(
                ReconciliationLine(
                    vintiz_payment_id=str(payment.id),
                    vintiz_transaction_number=txn.transaction_number,
                    vintiz_amount=float(payment.amount),
                    sumup_transaction_id=tx.transaction_id,
                    sumup_transaction_code=tx.transaction_code,
                    sumup_amount=tx.amount,
                    status="matched_amount",
                    delta=0.0,
                    vintiz_timestamp=_iso(txn.created_at),
                    sumup_timestamp=tx.timestamp or None,
                )
            )
            matched_sumup_ids.add(tx.transaction_id)

        # ── Reste : orphelins ──────────────────────────────────────────
        for payment, txn in unmatched_payments:
            if payment.id in paid_payment_ids:
                continue
            lines.append(
                ReconciliationLine(
                    vintiz_payment_id=str(payment.id),
                    vintiz_transaction_number=txn.transaction_number,
                    vintiz_amount=float(payment.amount),
                    sumup_transaction_id=None,
                    sumup_transaction_code=None,
                    sumup_amount=None,
                    status="vintiz_only",
                    delta=float(payment.amount),
                    vintiz_timestamp=_iso(txn.created_at),
                )
            )
        unmatched_sumup_count = 0
        for tx in unmatched_sumup_txs:
            if tx.transaction_id in paid_sumup_ids:
                continue
            unmatched_sumup_count += 1
            lines.append(
                ReconciliationLine(
                    vintiz_payment_id="",
                    vintiz_transaction_number=0,
                    vintiz_amount=0.0,
                    sumup_transaction_id=tx.transaction_id,
                    sumup_transaction_code=tx.transaction_code,
                    sumup_amount=tx.amount,
                    status="sumup_only",
                    delta=-tx.amount,
                    sumup_timestamp=tx.timestamp or None,
                )
            )

        unmatched_vintiz_count = sum(1 for ln in lines if ln.status == "vintiz_only")
        matched_total = matched_by_id + len(amount_pairs)

        return ReconciliationReport(
            reconciliation_date=target_date.isoformat(),
            total_vintiz_card=total_vintiz,
            total_sumup=total_sumup,
            delta=round(total_vintiz - total_sumup, 2),
            matched_count=matched_total,
            unmatched_vintiz=unmatched_vintiz_count,
            unmatched_sumup=unmatched_sumup_count,
            lines=lines,
            api_key_present=api_key_present,
            api_error=api_error,
            api_pages_fetched=pages_fetched,
            api_raw_tx_count=len(sumup_txs),
            matched_by_amount=len(amount_pairs),
        )
