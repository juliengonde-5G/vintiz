package fr.vintiz.domain.pos

import fr.vintiz.core.common.Money

enum class PaymentMethod { Cash, Card, Cheque, Credit }

data class PaymentLeg(
    val method: PaymentMethod,
    val amount: Money,
    val checkoutId: String? = null,
    val chequeRef: String? = null,
)

/**
 * Comptabilise les paiements d'un panier multi-règlements.
 * `paid` cumulé, `remaining` calculé par rapport au total panier
 * **indicatif** (le serveur reste autorité au commit).
 */
data class PaymentSplit(val cartTotal: Money, val legs: List<PaymentLeg> = emptyList()) {
    val paid: Money get() = legs.fold(Money.ZERO) { acc, l -> acc + l.amount }
    val remaining: Money get() = Money(cartTotal.cents - paid.cents)
    val isFullyPaid: Boolean get() = remaining.cents <= 0L

    /**
     * Pour un paiement espèces, calcule le rendu monnaie attendu :
     * différence entre montant donné et solde restant. Retourne
     * Money.ZERO si on rend "0 ou moins" (paiement juste / insuffisant).
     */
    fun computeChange(tenderedCash: Money): Money {
        val delta = tenderedCash.cents - remaining.cents
        return if (delta > 0L) Money(delta) else Money.ZERO
    }

    fun add(leg: PaymentLeg): PaymentSplit = copy(legs = legs + leg)
}
