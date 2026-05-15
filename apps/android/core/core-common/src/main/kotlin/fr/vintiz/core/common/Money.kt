package fr.vintiz.core.common

import java.text.NumberFormat
import java.util.Locale

/**
 * Montant monétaire en cents (Long pour éviter les flottants).
 *
 * Aligné sur le backend : `Transaction.total_cents`, `Payment.amount_cents`
 * (cf. [`apps/api/app/models/pos.py`]). Toute conversion depuis l'API
 * doit utiliser ce type — jamais de `Double` ni de `Float` pour
 * représenter de l'argent côté Vintiz.
 */
@JvmInline
value class Money(val cents: Long) {

    operator fun plus(other: Money): Money = Money(cents + other.cents)
    operator fun minus(other: Money): Money = Money(cents - other.cents)
    operator fun times(qty: Int): Money = Money(cents * qty)
    operator fun compareTo(other: Money): Int = cents.compareTo(other.cents)

    val isZero: Boolean get() = cents == 0L
    val isPositive: Boolean get() = cents > 0L

    /** Formate au format français `1 234,56 €` (NumberFormat Locale("fr", "FR")). */
    fun format(locale: Locale = Locale.FRANCE): String {
        val format = NumberFormat.getCurrencyInstance(locale)
        return format.format(cents / 100.0)
    }

    companion object {
        val ZERO: Money = Money(0L)

        /** Parse depuis le format API : un Long en cents. */
        fun ofCents(cents: Long): Money = Money(cents)

        /** Parse depuis un Double euros (à éviter sauf saisie utilisateur). */
        fun ofEuros(euros: Double): Money = Money(Math.round(euros * 100.0))
    }
}
