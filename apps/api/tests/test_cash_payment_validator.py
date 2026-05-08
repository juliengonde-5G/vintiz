"""Tests pour le validateur de plafond espèces (CMF art. L.112-6, 2015-741).

Plafonds :
- résident fiscal FR → max 1 000 € espèces
- non-résident (touriste) → max 15 000 €
"""

from dataclasses import dataclass
from decimal import Decimal

import pytest

from app.services.cash_payment_validator import (
    CASH_CAP_RESIDENT_EUR,
    CASH_CAP_TOURIST_EUR,
    cap_for,
    sum_cash_payments,
    validate,
)


@dataclass
class FakePayment:
    """Mimics PaymentInput / ORM Payment with method + amount."""

    method: str
    amount: Decimal


# -- cap_for --------------------------------------------------------


def test_cap_for_resident():
    assert cap_for(False) == CASH_CAP_RESIDENT_EUR == Decimal("1000")


def test_cap_for_tourist():
    assert cap_for(True) == CASH_CAP_TOURIST_EUR == Decimal("15000")


# -- sum_cash_payments ---------------------------------------------


def test_sum_cash_only_method_cash():
    payments = [
        FakePayment("cash", Decimal("100")),
        FakePayment("card", Decimal("500")),
        FakePayment("cash", Decimal("250")),
        FakePayment("cheque", Decimal("999")),
    ]
    assert sum_cash_payments(payments) == Decimal("350")


def test_sum_cash_empty():
    assert sum_cash_payments([]) == Decimal("0")


def test_sum_cash_handles_str_method_uppercase():
    payments = [FakePayment("CASH", Decimal("42"))]
    assert sum_cash_payments(payments) == Decimal("42")


def test_sum_cash_handles_enum_like_method():
    """Si l'objet a `method.value`, on l'utilise."""

    class EnumLike:
        def __init__(self, value):
            self.value = value

    payments = [FakePayment(EnumLike("cash"), Decimal("33"))]  # type: ignore[arg-type]
    assert sum_cash_payments(payments) == Decimal("33")


# -- validate ------------------------------------------------------


def test_validate_under_cap_resident_passes():
    res = validate([FakePayment("cash", Decimal("999"))], is_tourist=False)
    assert res.over_cap is False
    assert res.reason is None
    assert res.cap_eur == Decimal("1000")


def test_validate_at_cap_resident_passes():
    """Le seuil est strictement supérieur à 1000 — 1000 pile passe."""
    res = validate([FakePayment("cash", Decimal("1000"))], is_tourist=False)
    assert res.over_cap is False


def test_validate_over_cap_resident_fails():
    res = validate(
        [FakePayment("cash", Decimal("1000.01"))], is_tourist=False
    )
    assert res.over_cap is True
    assert "1 000" in res.reason or "1000" in res.reason
    assert "L.112-6" in res.reason


def test_validate_over_cap_resident_split_payment_still_blocked():
    """Split cash + CB ne contourne pas — c'est le total cash qui compte."""
    payments = [
        FakePayment("cash", Decimal("800")),
        FakePayment("cash", Decimal("400")),
        FakePayment("card", Decimal("5000")),  # CB ignored
    ]
    res = validate(payments, is_tourist=False)
    assert res.over_cap is True
    assert res.cash_total_eur == Decimal("1200")


def test_validate_under_cap_tourist_15000():
    res = validate(
        [FakePayment("cash", Decimal("14999"))], is_tourist=True
    )
    assert res.over_cap is False
    assert res.cap_eur == Decimal("15000")


def test_validate_over_cap_tourist():
    res = validate(
        [FakePayment("cash", Decimal("15000.01"))], is_tourist=True
    )
    assert res.over_cap is True
    assert res.is_tourist is True
    assert "non-résident" in res.reason
    assert "15000" in res.reason or "15 000" in res.reason


def test_validate_card_only_never_over_cap():
    """Une transaction 100 % CB de 50 000 € passe — pas concerné par L.112-6."""
    res = validate(
        [FakePayment("card", Decimal("50000"))], is_tourist=False
    )
    assert res.over_cap is False
    assert res.cash_total_eur == Decimal("0")


def test_validate_cheque_only_never_over_cap():
    """Le chèque a son propre plafond légal mais pas via ce validateur."""
    res = validate(
        [FakePayment("cheque", Decimal("3000"))], is_tourist=False
    )
    assert res.over_cap is False


def test_validate_no_payments_passes():
    res = validate([], is_tourist=False)
    assert res.over_cap is False
    assert res.cash_total_eur == Decimal("0")


def test_validate_avoir_payment_ignored():
    """Le règlement par avoir / store credit n'est pas du cash."""
    res = validate(
        [
            FakePayment("avoir", Decimal("2000")),
            FakePayment("cash", Decimal("100")),
        ],
        is_tourist=False,
    )
    assert res.over_cap is False
    assert res.cash_total_eur == Decimal("100")


@pytest.mark.parametrize(
    "amount,is_tourist,expected_over",
    [
        (Decimal("0"), False, False),
        (Decimal("999.99"), False, False),
        (Decimal("1000"), False, False),
        (Decimal("1000.01"), False, True),
        (Decimal("5000"), False, True),
        (Decimal("999"), True, False),
        (Decimal("15000"), True, False),
        (Decimal("15000.01"), True, True),
        (Decimal("50000"), True, True),
    ],
)
def test_validate_boundaries(amount, is_tourist, expected_over):
    res = validate(
        [FakePayment("cash", amount)], is_tourist=is_tourist
    )
    assert res.over_cap is expected_over
