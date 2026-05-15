package fr.vintiz.domain.reports

import com.google.common.truth.Truth.assertThat
import fr.vintiz.core.common.Money
import org.junit.jupiter.api.Test

class ZReportTest {

    private fun zr(opening: Long, closing: Long, expected: Long, cash: Long, card: Long, cheque: Long) =
        ZReport(
            id = "z1",
            drawerId = "d1",
            openedAt = "2026-05-15T08:00",
            closedAt = "2026-05-15T20:00",
            openingAmount = Money(opening),
            closingAmount = Money(closing),
            expected = Money(expected),
            totalCash = Money(cash),
            totalCard = Money(card),
            totalCheque = Money(cheque),
        )

    @Test
    fun `diff zero si reconcilie`() {
        val r = zr(10000, 15000, 15000, 5000, 0, 0)
        assertThat(r.diff.cents).isEqualTo(0)
        assertThat(r.isReconciled).isTrue()
        assertThat(r.isSurplus).isFalse()
        assertThat(r.isShortage).isFalse()
    }

    @Test
    fun `surplus si compte plus eleve que attendu`() {
        val r = zr(10000, 16000, 15000, 5000, 0, 0)
        assertThat(r.diff.cents).isEqualTo(1000)
        assertThat(r.isSurplus).isTrue()
    }

    @Test
    fun `shortage si compte moins eleve que attendu`() {
        val r = zr(10000, 14500, 15000, 5000, 0, 0)
        assertThat(r.diff.cents).isEqualTo(-500)
        assertThat(r.isShortage).isTrue()
    }

    @Test
    fun `totalRevenue somme les 3 methodes`() {
        val r = zr(10000, 15000, 15000, 5000, 12000, 800)
        assertThat(r.totalRevenue.cents).isEqualTo(17800)
    }
}
