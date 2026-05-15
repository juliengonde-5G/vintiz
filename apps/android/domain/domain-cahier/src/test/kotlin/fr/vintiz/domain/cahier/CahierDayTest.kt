package fr.vintiz.domain.cahier

import com.google.common.truth.Truth.assertThat
import fr.vintiz.core.common.Money
import org.junit.jupiter.api.Test

class CahierDayTest {

    private fun day(target: Long, actual: Long, ya1: Long = 0) = CahierDay(
        date = "2026-05-15",
        target = Money(target),
        actual = Money(actual),
        transactionCount = 10,
        cumulativeMonth = Money.ZERO,
        remainingMonth = Money.ZERO,
        yearAgo = Money(ya1),
    )

    @Test
    fun `dayProgress cape a 1 si objectif depasse`() {
        val d = day(target = 100_000, actual = 150_000)
        assertThat(d.dayProgress).isEqualTo(1f)
    }

    @Test
    fun `rawDayProgress peut depasser 1`() {
        val d = day(target = 100_000, actual = 150_000)
        assertThat(d.rawDayProgress).isEqualTo(1.5f)
    }

    @Test
    fun `dayProgress 0 si objectif zero`() {
        val d = day(target = 0, actual = 5_000)
        assertThat(d.dayProgress).isEqualTo(0f)
    }

    @Test
    fun `monthProgress calcule sur cumulative`() {
        val d = day(target = 100_000, actual = 50_000).copy(
            cumulativeMonth = Money(800_000),
        )
        assertThat(d.monthProgress(Money(1_000_000))).isEqualTo(0.8f)
    }

    @Test
    fun `yearOnYear delta positif si on fait mieux`() {
        val d = day(target = 100_000, actual = 120_000, ya1 = 100_000)
        assertThat(d.yearOnYearDeltaPercent).isEqualTo(20)
    }

    @Test
    fun `yearOnYear delta negatif si on fait moins`() {
        val d = day(target = 100_000, actual = 80_000, ya1 = 100_000)
        assertThat(d.yearOnYearDeltaPercent).isEqualTo(-20)
    }

    @Test
    fun `yearOnYear delta zero si ya1 nul`() {
        val d = day(target = 100_000, actual = 50_000, ya1 = 0)
        assertThat(d.yearOnYearDeltaPercent).isEqualTo(0)
    }

    @Test
    fun `isSigned true uniquement si les deux signatures presentes`() {
        val unsigned = day(0, 0)
        assertThat(unsigned.isSigned).isFalse()
        val onlyManager = unsigned.copy(managerSignature = "AM")
        assertThat(onlyManager.isSigned).isFalse()
        val both = onlyManager.copy(teamSignature = "Equipe")
        assertThat(both.isSigned).isTrue()
    }
}
