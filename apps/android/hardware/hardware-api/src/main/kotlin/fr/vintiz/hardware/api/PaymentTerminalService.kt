package fr.vintiz.hardware.api

import fr.vintiz.core.common.Money
import kotlinx.coroutines.flow.StateFlow

/**
 * Abstraction TPE Vintiz. Deux implémentations :
 * - `SumUpSdkTerminal` (sumup-android-sdk, BT direct, recommandé)
 * - `SumUpRestTerminal` (polling /api/v1/pos/payments/cb/* en fallback)
 *
 * Le choix entre les deux est piloté par
 * [fr.vintiz.core.datastore.AppPreferences.paymentBackend].
 */
interface PaymentTerminalService {

    val status: StateFlow<TerminalStatus>

    /**
     * @param foreignTxId UUID Vintiz pour idempotence et reconciliation
     *   côté SumUp. Pas le `transaction_id` SumUp — c'est l'UUID que la
     *   boutique génère pour cette tentative de paiement
     *   (cf. `apps/api/app/services/sumup_service.py:affiliate.foreign_transaction_id`).
     */
    suspend fun pay(amount: Money, foreignTxId: String, description: String): PaymentOutcome

    suspend fun cancel(checkoutId: String): Boolean
}

enum class TerminalStatus { Unknown, Paired, Offline, Busy, Error }

sealed class PaymentOutcome {
    data class Paid(
        val checkoutId: String,
        val cardBrand: String?,
        val cardLast4: String?,
        val authCode: String?,
    ) : PaymentOutcome()

    data class Declined(val reason: String) : PaymentOutcome()
    data class Cancelled(val byUser: Boolean) : PaymentOutcome()
    data class Failed(val message: String, val cause: Throwable? = null) : PaymentOutcome()
}
