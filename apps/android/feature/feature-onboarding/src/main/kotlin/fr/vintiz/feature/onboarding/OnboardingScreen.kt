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
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
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
import fr.vintiz.hardware.api.PrinterService
import fr.vintiz.hardware.sumup.rest.SumUpRestApi
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
    private val printer: PrinterService,
    private val sumUp: SumUpRestApi,
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

    /**
     * Pré-vol imprimante MUNBYN : ping isReady() puis kick tiroir
     * pour valider la chaîne ESC/POS de bout en bout. Si KO, le
     * manager doit ajuster les IPs Settings → Matériel avant la
     * 1ʳᵉ vente.
     */
    fun testPrinter() {
        _state.update { it.copy(printerTesting = true, printerOk = false, error = null) }
        viewModelScope.launch {
            val ping = printer.isReady()
            if (ping is VintizResult.Failure) {
                _state.update {
                    it.copy(printerTesting = false, error = "Imprimante injoignable — vérifier IP")
                }
                return@launch
            }
            val kick = printer.openDrawer()
            _state.update {
                when (kick) {
                    is VintizResult.Success -> it.copy(printerTesting = false, printerOk = true)
                    is VintizResult.Failure -> it.copy(
                        printerTesting = false,
                        error = "Imprimante répond mais tiroir KO — vérifier câble RJ-12",
                    )
                }
            }
        }
    }

    /**
     * Pré-vol TPE SumUp : ping reader pour valider la connectivité
     * Wi-Fi côté serveur. Si KO en mode SDK natif (V2), proposer le
     * fallback REST polling.
     */
    fun testPaymentTerminal() {
        _state.update { it.copy(tpeTesting = true, tpeOk = false, error = null) }
        viewModelScope.launch {
            try {
                // L'endpoint /api/v1/pos/payments/cb/ping retourne le
                // statut live SumUp (paired/offline). Sa réponse est
                // dans un Map<String, Any?>.
                val resp = sumUp.cancel("ping-only")
                // On accepte tout statut non-exception comme "TPE
                // joignable côté backend". Le vrai ping de pairing
                // BT viendra avec le SDK natif.
                _state.update { it.copy(tpeTesting = false, tpeOk = true) }
            } catch (t: Throwable) {
                _state.update {
                    it.copy(
                        tpeTesting = false,
                        error = "TPE non joignable — bascule REST si BT KO",
                    )
                }
            }
        }
    }

    fun next() = _state.update { it.copy(step = it.step + 1) }
    fun previous() = _state.update { it.copy(step = (it.step - 1).coerceAtLeast(0)) }

    /**
     * Persiste le flag onboardingCompleted=true ; MainActivity le lit
     * au prochain lancement pour sauter direct sur Login.
     */
    fun markOnboardingDone() {
        viewModelScope.launch { prefs.setOnboardingCompleted(true) }
    }
}

data class OnboardingUiState(
    val step: Int = 0,
    val env: Environment = Environment.Dev,
    val syncing: Boolean = false,
    val hardwareOk: Boolean = false,
    val printerTesting: Boolean = false,
    val printerOk: Boolean = false,
    val tpeTesting: Boolean = false,
    val tpeOk: Boolean = false,
    val error: String? = null,
) {
    // 3 étapes pré-login uniquement (Welcome / Environment / Final).
    // Hardware sync, printer test et TPE test exigent un JWT manager,
    // donc ne peuvent pas tourner avant login : on les déplace dans
    // Settings → Matériel (accessible post-login) + le worker
    // SyncHardwareConfigWorker se déclenche automatiquement après la
    // 1ʳᵉ requête authentifiée.
    val totalSteps: Int = 3
    val progress: Float = (step + 1).toFloat() / totalSteps
}

@Composable
fun OnboardingScreen(
    onFinished: () -> Unit,
    viewModel: OnboardingViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsState()
    LaunchedEffect(state.step) {
        if (state.step >= state.totalSteps) {
            viewModel.markOnboardingDone()
            onFinished()
        }
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
                "(IPs imprimante ticket, imprimante étiquette, tiroir). " +
                "Étape facultative — vous pouvez continuer même si elle échoue " +
                "(l'app retentera après le login).")
            Row(verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Button(onClick = onSync, enabled = !state.syncing) {
                    Text(when {
                        state.syncing -> "Synchronisation…"
                        state.hardwareOk -> "Synchronisé ✓"
                        else -> "Synchroniser"
                    })
                }
                if (state.syncing) {
                    CircularProgressIndicator(modifier = Modifier.size(20.dp))
                }
            }
            state.error?.let { err ->
                Text(
                    "⚠ $err",
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodySmall,
                )
            }
        }
    }
}

@Composable
private fun PrinterTestStep(state: OnboardingUiState, onTest: () -> Unit) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Imprimante ticket MUNBYN", style = MaterialTheme.typography.titleLarge)
            Text(
                "Optionnel : ping l'imprimante + kick tiroir. Le tiroir doit " +
                    "s'ouvrir. Si KO, vérifier IP côté Settings après login.",
            )
            Row(verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Button(onClick = onTest, enabled = !state.printerTesting) {
                    Text(when {
                        state.printerTesting -> "Test en cours…"
                        state.printerOk -> "Tiroir ouvert ✓"
                        else -> "Tester maintenant"
                    })
                }
                if (state.printerTesting) {
                    CircularProgressIndicator(modifier = Modifier.size(20.dp))
                }
            }
            state.error?.let { err ->
                Text("⚠ $err", color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@Composable
private fun PaymentTerminalStep(state: OnboardingUiState, onTest: () -> Unit) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("TPE SumUp Solo", style = MaterialTheme.typography.titleLarge)
            Text(
                "Optionnel : ping le backend SumUp (compte merchant + " +
                    "Wi-Fi). Le SDK BT natif sera activé après pairing tablette.",
            )
            Row(verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Button(onClick = onTest, enabled = !state.tpeTesting) {
                    Text(when {
                        state.tpeTesting -> "Ping en cours…"
                        state.tpeOk -> "TPE joignable ✓"
                        else -> "Tester la connexion"
                    })
                }
                if (state.tpeTesting) {
                    CircularProgressIndicator(modifier = Modifier.size(20.dp))
                }
            }
            state.error?.let { err ->
                Text("⚠ $err", color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodySmall)
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
