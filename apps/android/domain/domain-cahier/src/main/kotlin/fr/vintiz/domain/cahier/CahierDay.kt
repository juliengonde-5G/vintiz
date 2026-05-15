package fr.vintiz.domain.cahier

import fr.vintiz.core.common.Money

data class CahierDay(
    val date: String,
    val target: Money,
    val actual: Money,
    val transactionCount: Int,
    val cumulativeMonth: Money,
    val remainingMonth: Money,
    val yearAgo: Money,
    val messageOfTheDay: String? = null,
    val currentOperation: String? = null,
    val managerSignature: String? = null,
    val teamSignature: String? = null,
) {
    /** Progression journalière 0..1, capée à 1 si dépassement. */
    val dayProgress: Float
        get() = if (target.cents <= 0) 0f
        else (actual.cents.toFloat() / target.cents.toFloat()).coerceAtMost(1f)

    /** Vraie progression (peut dépasser 1) pour afficher le bonus. */
    val rawDayProgress: Float
        get() = if (target.cents <= 0) 0f else actual.cents.toFloat() / target.cents.toFloat()

    /** Progression cumulée du mois sur l'objectif mensuel. */
    fun monthProgress(monthlyTarget: Money): Float =
        if (monthlyTarget.cents <= 0) 0f
        else (cumulativeMonth.cents.toFloat() / monthlyTarget.cents.toFloat()).coerceAtMost(1f)

    /** Y/Y comparé à n-1 — positif si on fait mieux, négatif sinon. */
    val yearOnYearDeltaPercent: Int
        get() = if (yearAgo.cents <= 0) 0
        else (((actual.cents - yearAgo.cents) * 100) / yearAgo.cents).toInt()

    val isSigned: Boolean
        get() = !managerSignature.isNullOrBlank() && !teamSignature.isNullOrBlank()
}
