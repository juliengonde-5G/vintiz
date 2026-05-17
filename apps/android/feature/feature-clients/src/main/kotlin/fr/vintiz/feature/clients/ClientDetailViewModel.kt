package fr.vintiz.feature.clients

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import fr.vintiz.core.common.VintizResult
import fr.vintiz.data.clients.ClientFullDto
import fr.vintiz.data.clients.ClientsRepository
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

@HiltViewModel
class ClientDetailViewModel @Inject constructor(
    private val repo: ClientsRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(ClientDetailUiState())
    val state: StateFlow<ClientDetailUiState> = _state.asStateFlow()

    fun load(clientId: String) {
        _state.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            when (val r = repo.fullClient(clientId)) {
                is VintizResult.Success -> _state.update {
                    it.copy(loading = false, full = r.value, clientId = clientId)
                }
                is VintizResult.Failure -> _state.update {
                    it.copy(loading = false, error = r.error.message)
                }
            }
        }
    }

    fun selectTab(i: Int) = _state.update { it.copy(tab = i) }

    /**
     * RGPD Article 20 — récupère l'export JSON et le fournit à l'UI.
     * L'UI s'occupe ensuite du partage (FileProvider Intent).
     */
    fun exportData() {
        val id = _state.value.clientId ?: return
        _state.update { it.copy(rgpdBusy = true, rgpdMessage = null, exportBytes = null) }
        viewModelScope.launch {
            when (val r = repo.exportData(id)) {
                is VintizResult.Success -> _state.update {
                    it.copy(
                        rgpdBusy = false,
                        exportBytes = r.value,
                        rgpdMessage = "Export prêt (${r.value.size} octets)",
                    )
                }
                is VintizResult.Failure -> _state.update {
                    it.copy(rgpdBusy = false, rgpdMessage = "Export KO : ${r.error.message}")
                }
            }
        }
    }

    fun clearExport() = _state.update { it.copy(exportBytes = null) }

    /**
     * RGPD Article 17 — déclenche la demande de suppression soft 30j.
     */
    fun requestDeletion() {
        val id = _state.value.clientId ?: return
        _state.update { it.copy(rgpdBusy = true, rgpdMessage = null) }
        viewModelScope.launch {
            when (val r = repo.requestDeletion(id)) {
                is VintizResult.Success -> _state.update {
                    it.copy(
                        rgpdBusy = false,
                        rgpdMessage = "Suppression programmée (purge ${r.value.purge_at ?: "30j"})",
                    )
                }
                is VintizResult.Failure -> _state.update {
                    it.copy(rgpdBusy = false, rgpdMessage = "Demande KO : ${r.error.message}")
                }
            }
        }
    }
}

data class ClientDetailUiState(
    val loading: Boolean = false,
    val full: ClientFullDto? = null,
    val tab: Int = 0,
    val error: String? = null,
    val clientId: String? = null,
    val rgpdBusy: Boolean = false,
    val rgpdMessage: String? = null,
    val exportBytes: ByteArray? = null,
) {
    override fun equals(other: Any?): Boolean = this === other || (
        other is ClientDetailUiState &&
            loading == other.loading &&
            full == other.full &&
            tab == other.tab &&
            error == other.error &&
            clientId == other.clientId &&
            rgpdBusy == other.rgpdBusy &&
            rgpdMessage == other.rgpdMessage &&
            (exportBytes?.contentEquals(other.exportBytes) ?: (other.exportBytes == null))
    )

    override fun hashCode(): Int {
        var r = loading.hashCode()
        r = 31 * r + (full?.hashCode() ?: 0)
        r = 31 * r + tab
        r = 31 * r + (error?.hashCode() ?: 0)
        r = 31 * r + (clientId?.hashCode() ?: 0)
        r = 31 * r + rgpdBusy.hashCode()
        r = 31 * r + (rgpdMessage?.hashCode() ?: 0)
        r = 31 * r + (exportBytes?.contentHashCode() ?: 0)
        return r
    }
}
