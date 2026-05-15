package fr.vintiz.core.common

import com.google.common.truth.Truth.assertThat
import org.junit.jupiter.api.Test
import java.util.Locale

class MoneyTest {

    @Test
    fun `addition combine les cents`() {
        val total = Money.ofCents(1500) + Money.ofCents(250)
        assertThat(total.cents).isEqualTo(1750)
    }

    @Test
    fun `multiplication scale par quantite`() {
        val unit = Money.ofCents(199)
        assertThat((unit * 5).cents).isEqualTo(995)
    }

    @Test
    fun `format francais utilise virgule et euro`() {
        val price = Money.ofCents(1234_56)
        val formatted = price.format(Locale.FRANCE)
        // NumberFormat insère un NBSP entre nombre et symbole, on
        // normalise pour le test.
        assertThat(formatted.replace(' ', ' ').replace(' ', ' '))
            .isEqualTo("1 234,56 €")
    }

    @Test
    fun `parse depuis euros arrondit correctement les centimes`() {
        assertThat(Money.ofEuros(12.34).cents).isEqualTo(1234)
        assertThat(Money.ofEuros(0.005).cents).isEqualTo(1) // half-up
        assertThat(Money.ofEuros(0.001).cents).isEqualTo(0)
    }

    @Test
    fun `zero est detecte comme tel`() {
        assertThat(Money.ZERO.isZero).isTrue()
        assertThat(Money.ofCents(1).isZero).isFalse()
    }

    @Test
    fun `comparaison ordonne par cents`() {
        assertThat(Money.ofCents(100) < Money.ofCents(200)).isTrue()
        assertThat(Money.ofCents(500) > Money.ofCents(200)).isTrue()
    }
}
