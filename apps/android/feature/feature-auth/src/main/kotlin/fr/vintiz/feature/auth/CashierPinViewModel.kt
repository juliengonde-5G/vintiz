package fr.vintiz.feature.auth

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import fr.vintiz.core.common.VintizResult
import fr.vintiz.data.auth.AuthRepository
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

@HiltViewModel
class CashierPinViewModel @Inject constructor(
    private val auth: AuthRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(CashierPinUiState())
    val state: StateFlow<CashierPinUiState> = _state.asStateFlow()

    fun onDigit(d: Char) {
        if (_state.value.pin.length >= MAX_LEN) return
        _state.update { it.copy(pin = it.pin + d, error = null) }
    }

    fun onBackspace() {
        _state.update { it.copy(pin = it.pin.dropLast(1), error = null) }
    }

    fun submit(onSuccess: () -> Unit) {
        val pin = _state.value.pin
        if (pin.length != MAX_LEN) {
            _state.update { it.copy(error = "PIN à 4 chiffres") }
            return
        }
        _state.update { it.copy(loading = true) }
        viewModelScope.launch {
            when (val r = auth.cashierLogin(pin)) {
                is VintizResult.Success -> {
                    _state.update { CashierPinUiState() }
                    onSuccess()
                }
                is VintizResult.Failure -> _state.update {
                    it.copy(loading = false, pin = "", error = r.error.userMessage())
                }
            }
        }
    }

    private companion object {
        const val MAX_LEN = 4
    }
}

data class CashierPinUiState(
    val pin: String = "",
    val loading: Boolean = false,
    val error: String? = null,
)
