package fr.vintiz.hardware.sumup.rest

import fr.vintiz.core.common.Money
import fr.vintiz.hardware.api.PaymentOutcome
import fr.vintiz.hardware.api.PaymentTerminalService
import fr.vintiz.hardware.api.TerminalStatus
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import retrofit2.HttpException
import timber.log.Timber
import java.io.IOException

/**
 * Implémentation REST de PaymentTerminalService — polling sur
 * `/api/v1/pos/payments/cb/{checkout_id}/status` toutes les
 * [pollIntervalMs] jusqu'à statut terminal (PAID/FAILED/CANCELLED) ou
 * timeout [timeoutMs].
 *
 * Reproduit usePosPayment() côté web (apps/web/src/hooks/usePosPayment.ts).
 * En V2 du plan, sera remplacée par `SumUpSdkTerminal` (BT direct via
 * sumup-android-sdk) — mais reste disponible en fallback runtime via
 * AppPreferences.paymentBackend.
 */
class SumUpRestTerminal(
    private val api: SumUpRestApi,
    private val pollIntervalMs: Long = 1_500L,
    private val timeoutMs: Long = 90_000L,
) : PaymentTerminalService {

    private val _status = MutableStateFlow(TerminalStatus.Unknown)
    override val status: StateFlow<TerminalStatus> = _status.asStateFlow()

    override suspend fun pay(amount: Money, foreignTxId: String, description: String): PaymentOutcome {
        _status.value = TerminalStatus.Busy
        val checkoutId = try {
            api.initiate(
                InitiateRequest(
                    amount_cents = amount.cents,
                    description = description,
                    foreign_transaction_id = foreignTxId,
                )
            ).checkout_id
        } catch (io: IOException) {
            _status.value = TerminalStatus.Offline
            return PaymentOutcome.Failed("Connexion SumUp impossible", io)
        } catch (http: HttpException) {
            _status.value = TerminalStatus.Error
            return PaymentOutcome.Failed("SumUp HTTP ${http.code()}")
        }

        val deadline = System.currentTimeMillis() + timeoutMs
        while (System.currentTimeMillis() < deadline) {
            delay(pollIntervalMs)
            val resp = try {
                api.status(checkoutId)
            } catch (io: IOException) {
                Timber.w(io, "polling SumUp KO — retry")
                continue
            }
            when (resp.status.uppercase()) {
                "PAID" -> {
                    _status.value = TerminalStatus.Paired
                    return PaymentOutcome.Paid(
                        checkoutId = checkoutId,
                        cardBrand = resp.card_brand,
                        cardLast4 = resp.card_last4,
                        authCode = resp.auth_code,
                    )
                }
                "FAILED" -> {
                    _status.value = TerminalStatus.Error
                    return PaymentOutcome.Declined(resp.error_detail ?: "Refusé")
                }
                "CANCELLED" -> {
                    _status.value = TerminalStatus.Paired
                    return PaymentOutcome.Cancelled(byUser = true)
                }
                else -> { /* PENDING — on continue */ }
            }
        }
        _status.value = TerminalStatus.Paired
        return PaymentOutcome.Failed("Délai dépassé (90 s)")
    }

    override suspend fun cancel(checkoutId: String): Boolean = try {
        api.cancel(checkoutId)
        true
    } catch (t: Throwable) {
        Timber.w(t, "cancel SumUp KO")
        false
    }
}
