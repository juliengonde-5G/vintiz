package fr.vintiz.domain.reports

import fr.vintiz.core.common.Money

data class ZReport(
    val id: String,
    val drawerId: String,
    val openedAt: String,
    val closedAt: String,
    val openingAmount: Money,
    val closingAmount: Money,
    val expected: Money,
    val totalCash: Money,
    val totalCard: Money,
    val totalCheque: Money,
) {
    val diff: Money get() = Money(closingAmount.cents - expected.cents)
    val isSurplus: Boolean get() = diff.cents > 0L
    val isShortage: Boolean get() = diff.cents < 0L
    val isReconciled: Boolean get() = diff.cents == 0L

    val totalRevenue: Money get() = totalCash + totalCard + totalCheque
}
