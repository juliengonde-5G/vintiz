package fr.vintiz.feature.loyalty

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import fr.vintiz.core.common.VintizResult
import fr.vintiz.data.loyalty.LoyaltyCardDto
import fr.vintiz.data.loyalty.LoyaltyConfigDto
import fr.vintiz.data.loyalty.LoyaltyRepository
import fr.vintiz.data.loyalty.LoyaltySubscribeRequest
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

@HiltViewModel
class LoyaltySubscribeViewModel @Inject constructor(
    private val repo: LoyaltyRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(LoyaltySubscribeUiState())
    val state: StateFlow<LoyaltySubscribeUiState> = _state.asStateFlow()

    fun loadConfig() {
        viewModelScope.launch {
            (repo.getConfig() as? VintizResult.Success)?.let { ok ->
                _state.update { it.copy(config = ok.value) }
            }
        }
    }

    fun setEmail(v: String) = _state.update { it.copy(email = v, error = null) }
    fun setFirstName(v: String) = _state.update { it.copy(firstName = v, error = null) }
    fun setLastName(v: String) = _state.update { it.copy(lastName = v, error = null) }
    fun setPhone(v: String) = _state.update { it.copy(phone = v) }
    fun toggleNewsletter() = _state.update { it.copy(consentNewsletter = !it.consentNewsletter) }
    fun togglePersonalShopper() =
        _state.update { it.copy(consentPersonalShopper = !it.consentPersonalShopper) }
    fun toggleTrendAlerts() = _state.update { it.copy(consentTrendAlerts = !it.consentTrendAlerts) }
    fun setPaymentMethod(method: String) = _state.update { it.copy(paymentMethod = method) }

    fun submit() {
        val s = _state.value
        val err = validate(s)
        if (err != null) {
            _state.update { it.copy(error = err) }
            return
        }
        _state.update { it.copy(loading = true) }
        viewModelScope.launch {
            val request = LoyaltySubscribeRequest(
                email = s.email.trim(),
                first_name = s.firstName.trim(),
                last_name = s.lastName.trim(),
                phone = s.phone.takeIf { it.isNotBlank() },
                consent_newsletter = s.consentNewsletter,
                consent_personal_shopper = s.consentPersonalShopper,
                consent_trend_alerts = s.consentTrendAlerts,
                payment_method = s.paymentMethod.takeIf { s.config?.mode == "paid" },
            )
            when (val r = repo.subscribe(request)) {
                is VintizResult.Success -> _state.update {
                    it.copy(loading = false, createdCard = r.value)
                }
                is VintizResult.Failure -> _state.update {
                    it.copy(loading = false, error = r.error.message)
                }
            }
        }
    }

    fun reset() {
        _state.value = LoyaltySubscribeUiState(config = _state.value.config)
    }

    private fun validate(s: LoyaltySubscribeUiState): String? =
        LoyaltySubscribeValidator.validate(
            firstName = s.firstName,
            lastName = s.lastName,
            email = s.email,
            paymentMethod = s.paymentMethod,
            config = s.config,
        )
}

data class LoyaltySubscribeUiState(
    val email: String = "",
    val firstName: String = "",
    val lastName: String = "",
    val phone: String = "",
    val consentNewsletter: Boolean = false,
    val consentPersonalShopper: Boolean = false,
    val consentTrendAlerts: Boolean = false,
    val paymentMethod: String = "",
    val config: LoyaltyConfigDto? = null,
    val loading: Boolean = false,
    val createdCard: LoyaltyCardDto? = null,
    val error: String? = null,
)
