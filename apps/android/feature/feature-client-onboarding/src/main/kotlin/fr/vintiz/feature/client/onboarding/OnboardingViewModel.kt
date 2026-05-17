package fr.vintiz.feature.client.onboarding

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import fr.vintiz.core.common.VintizError
import fr.vintiz.core.common.VintizResult
import fr.vintiz.data.authclient.ClientAuthRepository
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/**
 * État UI partagé entre les écrans d'onboarding :
 * 1. [EmailRequestScreen] — saisie email + déclenche `requestOtp`
 * 2. [OtpVerifyScreen]    — saisie OTP 6 chiffres + déclenche `verifyOtp`
 *
 * Garder un seul ViewModel pour la séquence permet de propager `email`
 * sans le repasser en argument de navigation.
 */
@HiltViewModel
class OnboardingViewModel @Inject constructor(
    private val repo: ClientAuthRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(OnboardingUiState())
    val state: StateFlow<OnboardingUiState> = _state.asStateFlow()

    fun onEmailChanged(value: String) {
        _state.update { it.copy(email = value, error = null) }
    }

    fun onCodeChanged(value: String) {
        _state.update { it.copy(code = value.filter(Char::isDigit).take(6), error = null) }
    }

    fun requestOtp(onSuccess: () -> Unit) {
        val email = _state.value.email.trim()
        if (!email.contains('@') || email.length < 5) {
            _state.update { it.copy(error = "Adresse e-mail invalide") }
            return
        }
        _state.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            when (val r = repo.requestOtp(email)) {
                is VintizResult.Success -> {
                    _state.update { it.copy(loading = false, otpSent = true) }
                    onSuccess()
                }
                is VintizResult.Failure -> _state.update {
                    it.copy(loading = false, error = errorMessage(r.error))
                }
            }
        }
    }

    fun verifyOtp(onSuccess: () -> Unit) {
        val email = _state.value.email.trim()
        val code = _state.value.code.trim()
        if (code.length != 6) {
            _state.update { it.copy(error = "Code à 6 chiffres requis") }
            return
        }
        _state.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            when (val r = repo.verifyOtp(email, code)) {
                is VintizResult.Success -> {
                    _state.update { it.copy(loading = false, authenticated = true) }
                    onSuccess()
                }
                is VintizResult.Failure -> _state.update {
                    it.copy(loading = false, error = errorMessage(r.error))
                }
            }
        }
    }

    private fun errorMessage(err: VintizError): String = when (err) {
        is VintizError.Network -> "Connexion indisponible — réessayer ?"
        is VintizError.Unauthorized -> "Code invalide ou expiré"
        is VintizError.RateLimit -> "Trop de tentatives, réessayer dans ${err.retryAfterSeconds}s"
        is VintizError.Http -> err.message
        else -> err.message
    }
}

data class OnboardingUiState(
    val email: String = "",
    val code: String = "",
    val loading: Boolean = false,
    val otpSent: Boolean = false,
    val authenticated: Boolean = false,
    val error: String? = null,
)
