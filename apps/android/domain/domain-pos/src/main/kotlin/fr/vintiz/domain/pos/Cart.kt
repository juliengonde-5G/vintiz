package fr.vintiz.domain.pos

import fr.vintiz.core.common.Money

/**
 * Modèle métier d'un panier POS. Pure structure de données — toute
 * **logique de prix réelle** (TVA, remises fidélité, NF525, signature)
 * reste serveur (`apps/api/app/services/pos.py`). On calcule un total
 * local **uniquement pour l'affichage** ; le serveur recalculera au
 * commit et fait foi.
 */
data class Cart(val lines: List<CartLine> = emptyList()) {

    val isEmpty: Boolean get() = lines.isEmpty()

    val subtotal: Money
        get() = lines.fold(Money.ZERO) { acc, line -> acc + line.lineTotal }

    fun add(line: CartLine): Cart = copy(lines = lines + line)

    fun removeAt(index: Int): Cart =
        if (index in lines.indices) copy(lines = lines.toMutableList().apply { removeAt(index) })
        else this

    fun updateAt(index: Int, transform: (CartLine) -> CartLine): Cart =
        if (index in lines.indices) {
            copy(lines = lines.toMutableList().apply { this[index] = transform(this[index]) })
        } else {
            this
        }

    fun clear(): Cart = Cart()
}

data class CartLine(
    val productId: String?,
    val name: String,
    val unitPrice: Money,
    val quantity: Int = 1,
    val discountPercent: Int = 0,
) {
    init {
        require(quantity >= 1) { "Quantité doit être ≥ 1" }
        require(discountPercent in 0..100) { "Remise doit être entre 0 et 100" }
    }

    /**
     * Calcul indicatif (affichage caisse). Le serveur recalcule au
     * commit et reste la vérité — voir `pos.py:create_transaction`.
     */
    val lineTotal: Money
        get() {
            val gross = unitPrice * quantity
            if (discountPercent == 0) return gross
            val discountedCents = gross.cents - (gross.cents * discountPercent / 100)
            return Money(discountedCents)
        }
}
