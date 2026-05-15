package fr.vintiz.feature.auth

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import fr.vintiz.core.common.VintizError
import fr.vintiz.core.common.VintizResult
import fr.vintiz.data.auth.AuthRepository
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

@HiltViewModel
class LoginViewModel @Inject constructor(
    private val auth: AuthRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(LoginUiState())
    val state: StateFlow<LoginUiState> = _state.asStateFlow()

    fun onUsernameChange(v: String) = _state.update { it.copy(username = v, error = null) }
    fun onPasswordChange(v: String) = _state.update { it.copy(password = v, error = null) }

    fun submit(onSuccess: () -> Unit) {
        val s = _state.value
        if (s.username.isBlank() || s.password.isBlank()) {
            _state.update { it.copy(error = "Identifiants requis") }
            return
        }
        _state.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            when (val r = auth.login(s.username, s.password)) {
                is VintizResult.Success -> {
                    _state.update { it.copy(loading = false) }
                    onSuccess()
                }
                is VintizResult.Failure -> _state.update {
                    it.copy(loading = false, error = r.error.userMessage())
                }
            }
        }
    }
}

data class LoginUiState(
    val username: String = "",
    val password: String = "",
    val loading: Boolean = false,
    val error: String? = null,
)

internal fun VintizError.userMessage(): String = when (this) {
    is VintizError.Unauthorized -> "Identifiants incorrects"
    is VintizError.RateLimit -> "Trop de tentatives, réessayer dans ${retryAfterSeconds}s"
    is VintizError.Network -> "Connexion indisponible"
    is VintizError.Http -> "Erreur serveur ($code)"
    else -> message
}
