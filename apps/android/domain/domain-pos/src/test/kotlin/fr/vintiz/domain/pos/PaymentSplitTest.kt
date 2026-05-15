package fr.vintiz.domain.pos

import com.google.common.truth.Truth.assertThat
import fr.vintiz.core.common.Money
import org.junit.jupiter.api.Test

class PaymentSplitTest {

    @Test
    fun `remaining decremente avec chaque leg`() {
        val split = PaymentSplit(cartTotal = Money(2000))
            .add(PaymentLeg(PaymentMethod.Cash, Money(500)))
            .add(PaymentLeg(PaymentMethod.Card, Money(1500), checkoutId = "ck1"))
        assertThat(split.paid.cents).isEqualTo(2000)
        assertThat(split.remaining.cents).isEqualTo(0)
        assertThat(split.isFullyPaid).isTrue()
    }

    @Test
    fun `change cash positif si surplus`() {
        val split = PaymentSplit(cartTotal = Money(1500))
        val change = split.computeChange(tenderedCash = Money(2000))
        assertThat(change.cents).isEqualTo(500)
    }

    @Test
    fun `change zero si pile`() {
        val split = PaymentSplit(cartTotal = Money(1500))
        assertThat(split.computeChange(Money(1500)).cents).isEqualTo(0)
    }

    @Test
    fun `change zero si insuffisant`() {
        val split = PaymentSplit(cartTotal = Money(1500))
        assertThat(split.computeChange(Money(1000)).cents).isEqualTo(0)
    }
}
