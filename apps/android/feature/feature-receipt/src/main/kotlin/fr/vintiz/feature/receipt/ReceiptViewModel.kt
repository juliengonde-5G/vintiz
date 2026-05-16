package fr.vintiz.feature.receipt

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import fr.vintiz.core.common.VintizResult
import fr.vintiz.data.pos.PosApi
import fr.vintiz.hardware.api.PrinterService
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import timber.log.Timber

/**
 * Pilote la modal post-vente : récupère les bytes ESC/POS pré-signés
 * depuis le backend et les envoie à l'imprimante MUNBYN (TCP ou USB
 * selon `PrinterService` injecté par Hilt). Pour la version V1, le
 * resend email/SMS n'est qu'un POST vers `/transactions/{id}/resend`
 * — ajouté plus tard quand le DTO sera défini.
 */
@HiltViewModel
class ReceiptViewModel @Inject constructor(
    private val pos: PosApi,
    private val printer: PrinterService,
) : ViewModel() {

    private val _state = MutableStateFlow(ReceiptUiState())
    val state: StateFlow<ReceiptUiState> = _state.asStateFlow()

    fun load(transactionId: String) {
        _state.update { it.copy(transactionId = transactionId) }
    }

    fun printTicket(kickDrawer: Boolean) {
        val txId = _state.value.transactionId ?: return
        _state.update { it.copy(printing = true, error = null) }
        viewModelScope.launch {
            val bytes = try {
                pos.receiptEscPosBytes(txId, kickDrawer).bytes()
            } catch (t: Throwable) {
                Timber.w(t, "receipt download KO")
                _state.update { it.copy(printing = false, error = "Téléchargement ticket impossible") }
                return@launch
            }
            when (val r = printer.printReceipt(bytes)) {
                is VintizResult.Success -> _state.update {
                    it.copy(printing = false, printed = true)
                }
                is VintizResult.Failure -> _state.update {
                    it.copy(printing = false, error = "Impression échouée : ${r.error.message}")
                }
            }
        }
    }

    fun kickDrawer() {
        viewModelScope.launch { printer.openDrawer() }
    }
}

data class ReceiptUiState(
    val transactionId: String? = null,
    val printing: Boolean = false,
    val printed: Boolean = false,
    val error: String? = null,
)
