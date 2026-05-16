package fr.vintiz.feature.onboarding

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import fr.vintiz.core.common.VintizResult
import fr.vintiz.core.datastore.AppPreferences
import fr.vintiz.core.datastore.Environment
import fr.vintiz.data.hardware.HardwareRepository
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

@HiltViewModel
class OnboardingViewModel @Inject constructor(
    private val prefs: AppPreferences,
    private val hardware: HardwareRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(OnboardingUiState())
    val state: StateFlow<OnboardingUiState> = _state.asStateFlow()

    fun setEnvironment(env: Environment) {
        viewModelScope.launch { prefs.setEnvironment(env) }
        _state.update { it.copy(env = env) }
    }

    fun syncHardware() {
        _state.update { it.copy(syncing = true) }
        viewModelScope.launch {
            val r = hardware.syncFromApi()
            _state.update {
                when (r) {
                    is VintizResult.Success -> it.copy(syncing = false, hardwareOk = true)
                    is VintizResult.Failure -> it.copy(syncing = false, error = r.error.message)
                }
            }
        }
    }

    fun next() = _state.update { it.copy(step = it.step + 1) }
    fun previous() = _state.update { it.copy(step = (it.step - 1).coerceAtLeast(0)) }
}

data class OnboardingUiState(
    val step: Int = 0,
    val env: Environment = Environment.Dev,
    val syncing: Boolean = false,
    val hardwareOk: Boolean = false,
    val error: String? = null,
) {
    val totalSteps: Int = 4
    val progress: Float = (step + 1).toFloat() / totalSteps
}

@Composable
fun OnboardingScreen(
    onFinished: () -> Unit,
    viewModel: OnboardingViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsState()
    LaunchedEffect(state.step) {
        if (state.step >= state.totalSteps) onFinished()
    }
    Scaffold { padding ->
        Column(
            modifier = Modifier.fillMaxSize().padding(padding).padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Text("Bienvenue", style = MaterialTheme.typography.displayMedium)
            LinearProgressIndicator(
                progress = { state.progress },
                modifier = Modifier.fillMaxWidth().height(6.dp),
            )

            when (state.step) {
                0 -> WelcomeStep()
                1 -> EnvironmentStep(state, viewModel::setEnvironment)
                2 -> HardwareStep(state, viewModel::syncHardware)
                else -> FinalStep()
            }

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (state.step > 0) OutlinedButton(onClick = viewModel::previous) { Text("Précédent") }
                Spacer(Modifier.fillMaxWidth(0.5f))
                Button(
                    onClick = viewModel::next,
                    enabled = !state.syncing,
                    modifier = Modifier.widthIn(min = 160.dp),
                ) {
                    Text(if (state.step == state.totalSteps - 1) "Terminer" else "Suivant")
                }
            }

            state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        }
    }
}

@Composable
private fun WelcomeStep() {
    Text(
        "Cette tablette va devenir votre caisse Vintiz. " +
            "On va configurer l'environnement et tester le matériel en 3 étapes.",
        style = MaterialTheme.typography.bodyLarge,
    )
}

@Composable
private fun EnvironmentStep(state: OnboardingUiState, onSelect: (Environment) -> Unit) {
    Text("Environnement serveur", style = MaterialTheme.typography.titleLarge)
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Environment.entries.forEach { env ->
            Button(
                onClick = { onSelect(env) },
                enabled = state.env != env,
            ) { Text(env.key.uppercase()) }
        }
    }
    Text(
        "API : ${state.env.baseUrl}",
        style = MaterialTheme.typography.labelLarge,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
}

@Composable
private fun HardwareStep(state: OnboardingUiState, onSync: () -> Unit) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Matériel boutique", style = MaterialTheme.typography.titleLarge)
            Text("On va récupérer la config matériel depuis le serveur " +
                "(IPs imprimante ticket, imprimante étiquette, tiroir).")
            Button(onClick = onSync, enabled = !state.syncing) {
                Text(when {
                    state.syncing -> "Synchronisation…"
                    state.hardwareOk -> "Synchronisé ✓"
                    else -> "Synchroniser"
                })
            }
        }
    }
}

@Composable
private fun FinalStep() {
    Text(
        "Tout est prêt. La prochaine étape : connexion manager + PIN caissière.",
        style = MaterialTheme.typography.bodyLarge,
    )
}
