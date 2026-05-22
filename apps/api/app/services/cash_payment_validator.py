"""Validation des plafonds légaux de paiement en espèces.

Conformité française :
- Article L.112-6 du Code monétaire et financier + décret n° 2015-741
- Particuliers résidents fiscaux français → professionnel : **1 000 € max**
- Non-résidents fiscaux français (touristes) : **15 000 € max**
- Sanction (CGI art. 1840 J) : amende de **5 % des sommes payées indûment**,
  solidaire entre payeur et bénéficiaire, minimum 150 €.

Les paiements espèces qui dépassent le plafond sont **bloqués** par défaut.
Un manager peut forcer la transaction en fournissant un motif d'override
(ex. justificatif d'identité étranger vérifié), tracé dans les audit logs.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable


CASH_CAP_RESIDENT_EUR = Decimal("1000")
CASH_CAP_TOURIST_EUR = Decimal("15000")


@dataclass(frozen=True)
class CashValidationResult:
    """Résultat d'une validation de paiement espèces.

    `cash_total_eur` : total cumulé des paiements de méthode `cash` sur
    une transaction (les paiements split type cash + CB ne contournent
    pas le plafond — c'est le total cash qui compte).
    """

    cash_total_eur: Decimal
    cap_eur: Decimal
    is_tourist: bool
    over_cap: bool
    reason: str | None  # message lisible quand `over_cap=True`


def cap_for(is_tourist: bool) -> Decimal:
    return CASH_CAP_TOURIST_EUR if is_tourist else CASH_CAP_RESIDENT_EUR


_CASH_METHOD_ALIASES = {"cash", "especes", "espèces"}


def sum_cash_payments(payments: Iterable[object]) -> Decimal:
    """Somme les paiements espèces quel que soit le DTO source.

    Accepte des objets exposant ``method`` (str ou Enum) et ``amount``
    (numérique). Les autres méthodes (``card``, ``cheque``, ``transfer``,
    ``avoir``) sont ignorées.

    ⚠️ Le POS envoie le vocabulaire FR (``especes``) tandis que l'ORM/Enum
    utilise ``cash`` : on accepte les deux, sinon le plafond légal serait
    silencieusement contourné (le total cash calculé resterait à 0).
    """
    total = Decimal("0")
    for p in payments:
        method_raw = getattr(p, "method", None)
        if method_raw is None:
            continue
        method = (
            method_raw.value
            if hasattr(method_raw, "value")
            else str(method_raw)
        ).lower()
        if method not in _CASH_METHOD_ALIASES:
            continue
        amount = getattr(p, "amount", None)
        if amount is None:
            continue
        total += Decimal(str(amount))
    return total


def validate(
    payments: Iterable[object],
    *,
    is_tourist: bool = False,
) -> CashValidationResult:
    """Vérifie qu'un panier de paiements respecte le plafond espèces.

    Paramètres :
        payments : liste des paiements de la transaction (PaymentInput,
            ORM Payment, ou n'importe quel objet avec ``method`` + ``amount``).
        is_tourist : True si la cliente déclare un statut de non-résident
            fiscal français (justificatif obligatoire avant override).

    Retour :
        ``CashValidationResult`` avec ``over_cap`` et ``reason`` lisible.
    """
    total = sum_cash_payments(payments)
    cap = cap_for(is_tourist)
    over = total > cap
    reason: str | None = None
    if over:
        if is_tourist:
            reason = (
                f"Paiement espèces de {total:.2f} € dépassant le plafond "
                f"non-résident de {cap:.0f} € (CMF art. L.112-6). "
                "Vérifier le justificatif d'identité étranger."
            )
        else:
            reason = (
                f"Paiement espèces de {total:.2f} € dépassant le plafond "
                f"légal de {cap:.0f} € (CMF art. L.112-6). "
                "Sanction : amende 5 % solidaire (CGI art. 1840 J)."
            )
    return CashValidationResult(
        cash_total_eur=total,
        cap_eur=cap,
        is_tourist=is_tourist,
        over_cap=over,
        reason=reason,
    )
