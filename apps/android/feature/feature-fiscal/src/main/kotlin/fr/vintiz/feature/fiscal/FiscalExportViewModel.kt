package fr.vintiz.feature.fiscal

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import fr.vintiz.core.common.VintizResult
import fr.vintiz.data.fiscal.FiscalFormat
import fr.vintiz.data.fiscal.FiscalRepository
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

@HiltViewModel
class FiscalExportViewModel @Inject constructor(
    private val repo: FiscalRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(FiscalExportUiState())
    val state: StateFlow<FiscalExportUiState> = _state.asStateFlow()

    fun setFrom(date: String?) {
        _state.update { it.copy(from = date, validation = validate(date, it.to)) }
    }

    fun setTo(date: String?) {
        _state.update { it.copy(to = date, validation = validate(it.from, date)) }
    }

    fun setFormat(format: FiscalFormat) {
        _state.update { it.copy(format = format) }
    }

    fun export() {
        val s = _state.value
        if (s.validation != null) return
        _state.update { it.copy(loading = true, lastExport = null, error = null) }
        viewModelScope.launch {
            when (val r = repo.export(s.from, s.to, s.format)) {
                is VintizResult.Success -> _state.update {
                    it.copy(loading = false, lastExport = r.value)
                }
                is VintizResult.Failure -> _state.update {
                    it.copy(loading = false, error = r.error.message)
                }
            }
        }
    }

    private fun validate(from: String?, to: String?): String? =
        FiscalDateValidator.validate(from, to)
}

data class FiscalExportUiState(
    val from: String? = null,
    val to: String? = null,
    val format: FiscalFormat = FiscalFormat.Xml,
    val validation: String? = null,
    val loading: Boolean = false,
    val lastExport: FiscalRepository.ExportFile? = null,
    val error: String? = null,
)
