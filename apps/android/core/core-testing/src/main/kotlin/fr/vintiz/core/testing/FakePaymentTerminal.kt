package fr.vintiz.core.testing

import fr.vintiz.core.common.Money
import fr.vintiz.hardware.api.PaymentOutcome
import fr.vintiz.hardware.api.PaymentTerminalService
import fr.vintiz.hardware.api.TerminalStatus
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

class FakePaymentTerminal(
    private val scriptedOutcomes: ArrayDeque<PaymentOutcome> = ArrayDeque(),
    initialStatus: TerminalStatus = TerminalStatus.Paired,
) : PaymentTerminalService {

    private val _status = MutableStateFlow(initialStatus)
    override val status: StateFlow<TerminalStatus> = _status

    val payCalls = mutableListOf<PayCall>()
    val cancelCalls = mutableListOf<String>()

    data class PayCall(val amount: Money, val foreignTxId: String, val description: String)

    fun script(vararg outcomes: PaymentOutcome) {
        scriptedOutcomes.clear()
        scriptedOutcomes.addAll(outcomes)
    }

    fun setStatus(s: TerminalStatus) { _status.value = s }

    override suspend fun pay(amount: Money, foreignTxId: String, description: String): PaymentOutcome {
        payCalls += PayCall(amount, foreignTxId, description)
        return scriptedOutcomes.removeFirstOrNull()
            ?: PaymentOutcome.Failed("FakePaymentTerminal not scripted")
    }

    override suspend fun cancel(checkoutId: String): Boolean {
        cancelCalls += checkoutId
        return true
    }
}
