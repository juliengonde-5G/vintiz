package fr.vintiz.feature.zones

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import fr.vintiz.core.common.VintizResult
import fr.vintiz.data.zones.ZonesRepository
import fr.vintiz.domain.zones.Zone
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

@HiltViewModel
class ZonesViewModel @Inject constructor(
    private val repo: ZonesRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(ZonesUiState())
    val state: StateFlow<ZonesUiState> = _state.asStateFlow()

    fun load() {
        _state.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            when (val r = repo.storePlan()) {
                is VintizResult.Success -> _state.update {
                    it.copy(loading = false, zones = r.value.map { dto -> dto.toDomain() })
                }
                is VintizResult.Failure -> _state.update {
                    it.copy(loading = false, error = r.error.message)
                }
            }
        }
    }

    fun selectZone(id: String?) {
        _state.update { it.copy(selectedId = id) }
    }
}

data class ZonesUiState(
    val loading: Boolean = false,
    val zones: List<Zone> = emptyList(),
    val selectedId: String? = null,
    val error: String? = null,
) {
    val selected: Zone? get() = zones.firstOrNull { it.id == selectedId }
}
