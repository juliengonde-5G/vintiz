package fr.vintiz.domain.pos

import com.google.common.truth.Truth.assertThat
import fr.vintiz.core.common.Money
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.assertThrows

class CartTest {

    private fun line(price: Long, qty: Int = 1, discount: Int = 0) = CartLine(
        productId = "p$price",
        name = "Article $price",
        unitPrice = Money(price),
        quantity = qty,
        discountPercent = discount,
    )

    @Test
    fun `panier vide subtotal zero`() {
        assertThat(Cart().subtotal).isEqualTo(Money.ZERO)
        assertThat(Cart().isEmpty).isTrue()
    }

    @Test
    fun `subtotal somme les lineTotal`() {
        val cart = Cart()
            .add(line(1500))
            .add(line(799, qty = 3))
        assertThat(cart.subtotal.cents).isEqualTo(1500 + 799 * 3)
    }

    @Test
    fun `remise appliquee sur la ligne`() {
        val l = line(1000, qty = 2, discount = 20)
        // gross = 2000, -20% = 1600
        assertThat(l.lineTotal.cents).isEqualTo(1600)
    }

    @Test
    fun `quantite zero refuse`() {
        assertThrows<IllegalArgumentException> {
            CartLine(null, "x", Money(100), quantity = 0)
        }
    }

    @Test
    fun `remise hors borne refuse`() {
        assertThrows<IllegalArgumentException> {
            CartLine(null, "x", Money(100), discountPercent = 110)
        }
    }

    @Test
    fun `removeAt enleve la ligne`() {
        val cart = Cart().add(line(100)).add(line(200))
        val after = cart.removeAt(0)
        assertThat(after.lines).hasSize(1)
        assertThat(after.lines.first().unitPrice.cents).isEqualTo(200)
    }

    @Test
    fun `updateAt transforme une ligne`() {
        val cart = Cart().add(line(100))
        val after = cart.updateAt(0) { it.copy(quantity = 5) }
        assertThat(after.lines.first().quantity).isEqualTo(5)
    }
}
