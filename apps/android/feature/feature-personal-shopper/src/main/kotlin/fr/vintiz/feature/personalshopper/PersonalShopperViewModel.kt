package fr.vintiz.feature.personalshopper

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import fr.vintiz.core.common.VintizResult
import fr.vintiz.data.clients.ClientDto
import fr.vintiz.data.clients.ClientsRepository
import fr.vintiz.data.personalshopper.PersonalShopperPicksDto
import fr.vintiz.data.personalshopper.PersonalShopperRepository
import fr.vintiz.data.personalshopper.PickDto
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

@HiltViewModel
class PersonalShopperViewModel @Inject constructor(
    private val clients: ClientsRepository,
    private val personalShopper: PersonalShopperRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(PersonalShopperUiState())
    val state: StateFlow<PersonalShopperUiState> = _state.asStateFlow()

    fun onSearchChange(q: String) {
        _state.update { it.copy(searchQuery = q, error = null) }
        if (q.length < 2) {
            _state.update { it.copy(candidates = emptyList()) }
            return
        }
        viewModelScope.launch {
            when (val r = clients.identify(q)) {
                is VintizResult.Success -> _state.update { it.copy(candidates = r.value) }
                is VintizResult.Failure -> _state.update { it.copy(error = r.error.message) }
            }
        }
    }

    fun selectClient(client: ClientDto) {
        _state.update {
            it.copy(
                selectedClient = client,
                candidates = emptyList(),
                searchQuery = "",
                picks = null,
                loadingPicks = true,
                error = null,
            )
        }
        viewModelScope.launch {
            when (val r = personalShopper.forClient(client.id)) {
                is VintizResult.Success -> _state.update {
                    it.copy(loadingPicks = false, picks = r.value)
                }
                is VintizResult.Failure -> _state.update {
                    it.copy(loadingPicks = false, error = r.error.message)
                }
            }
        }
    }

    fun trackClick(pick: PickDto) {
        val clientId = _state.value.selectedClient?.id ?: return
        viewModelScope.launch { personalShopper.logClick(clientId, pick.product_id) }
    }

    fun clearClient() = _state.update {
        it.copy(selectedClient = null, picks = null, loadingPicks = false,
            freeSearchQuery = "", freeSearchResults = emptyList())
    }

    fun onFreeSearchChange(q: String) =
        _state.update { it.copy(freeSearchQuery = q) }

    /**
     * Recherche libre Claude Haiku (PR2 sémantique). Le caissier
     * tape "robe taille M en lin" et Claude extrait les filtres
     * pour matcher l'inventaire.
     */
    fun runFreeSearch() {
        val email = _state.value.selectedClient?.email ?: return
        val q = _state.value.freeSearchQuery.trim()
        if (q.length < 3) return
        _state.update { it.copy(freeSearching = true, freeSearchError = null) }
        viewModelScope.launch {
            when (val r = personalShopper.searchByText(email, q)) {
                is VintizResult.Success -> _state.update {
                    it.copy(freeSearching = false, freeSearchResults = r.value)
                }
                is VintizResult.Failure -> _state.update {
                    it.copy(freeSearching = false, freeSearchError = r.error.message)
                }
            }
        }
    }
}

data class PersonalShopperUiState(
    val searchQuery: String = "",
    val candidates: List<ClientDto> = emptyList(),
    val selectedClient: ClientDto? = null,
    val loadingPicks: Boolean = false,
    val picks: PersonalShopperPicksDto? = null,
    val error: String? = null,
    val freeSearchQuery: String = "",
    val freeSearching: Boolean = false,
    val freeSearchResults: List<PickDto> = emptyList(),
    val freeSearchError: String? = null,
)
