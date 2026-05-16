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
                    it.copy(loading = false, full = r.value)
                }
                is VintizResult.Failure -> _state.update {
                    it.copy(loading = false, error = r.error.message)
                }
            }
        }
    }

    fun selectTab(i: Int) = _state.update { it.copy(tab = i) }
}

data class ClientDetailUiState(
    val loading: Boolean = false,
    val full: ClientFullDto? = null,
    val tab: Int = 0,
    val error: String? = null,
)
