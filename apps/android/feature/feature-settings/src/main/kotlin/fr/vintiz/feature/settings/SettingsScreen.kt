package fr.vintiz.feature.settings

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
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
import fr.vintiz.core.datastore.PaymentBackend
import fr.vintiz.core.datastore.PrinterBackend
import fr.vintiz.data.hardware.HardwareConfig
import fr.vintiz.data.hardware.HardwareRepository
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val hardware: HardwareRepository,
    private val prefs: AppPreferences,
) : ViewModel() {

    private val _state = MutableStateFlow(SettingsUiState())
    val state: StateFlow<SettingsUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            _state.update {
                it.copy(
                    config = hardware.current(),
                    printerBackend = prefs.printerBackend.first(),
                    paymentBackend = prefs.paymentBackend.first(),
                    cameraScannerEnabled = prefs.cameraScannerEnabled.first(),
                )
            }
        }
    }

    fun refreshFromApi() {
        viewModelScope.launch {
            _state.update { it.copy(loading = true) }
            when (val r = hardware.syncFromApi()) {
                is VintizResult.Success -> _state.update {
                    it.copy(loading = false, config = r.value)
                }
                is VintizResult.Failure -> _state.update {
                    it.copy(loading = false, error = r.error.message)
                }
            }
        }
    }

    fun setPrinterBackend(b: PrinterBackend) {
        viewModelScope.launch {
            prefs.setPrinterBackend(b)
            _state.update { it.copy(printerBackend = b) }
        }
    }

    fun setPaymentBackend(b: PaymentBackend) {
        viewModelScope.launch {
            prefs.setPaymentBackend(b)
            _state.update { it.copy(paymentBackend = b) }
        }
    }

    fun setCameraScanner(enabled: Boolean) {
        viewModelScope.launch {
            prefs.setCameraScannerEnabled(enabled)
            _state.update { it.copy(cameraScannerEnabled = enabled) }
        }
    }
}

data class SettingsUiState(
    val loading: Boolean = false,
    val config: HardwareConfig? = null,
    val printerBackend: PrinterBackend = PrinterBackend.NetworkTcp,
    val paymentBackend: PaymentBackend = PaymentBackend.SumUpSdk,
    val cameraScannerEnabled: Boolean = false,
    val error: String? = null,
)

@Composable
fun SettingsScreen(viewModel: SettingsViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsState()
    Scaffold { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("Réglages", style = MaterialTheme.typography.headlineLarge)

            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text("Imprimantes", style = MaterialTheme.typography.titleLarge)
                    Text(
                        "Ticket : ${state.config?.receiptPrinterHost ?: "—"}:${state.config?.receiptPrinterPort ?: "—"}",
                        style = MaterialTheme.typography.bodyMedium,
                    )
                    Text(
                        "Étiquette : ${state.config?.labelPrinterHost ?: "—"}:${state.config?.labelPrinterPort ?: "—"}",
                        style = MaterialTheme.typography.bodyMedium,
                    )
                    Text(
                        "Tiroir : pin ${state.config?.drawerKickPin ?: 0}, ${state.config?.drawerOnMs ?: 50}/${state.config?.drawerOffMs ?: 250} ms",
                        style = MaterialTheme.typography.bodyMedium,
                    )
                    Spacer(Modifier.height(4.dp))
                    Button(onClick = viewModel::refreshFromApi, enabled = !state.loading) {
                        Text(if (state.loading) "…" else "Recharger depuis serveur")
                    }
                }
            }

            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Backends", style = MaterialTheme.typography.titleLarge)
                    BackendToggle(
                        label = "Imprimante via",
                        leftLabel = "Réseau",
                        rightLabel = "USB-OTG",
                        leftSelected = state.printerBackend == PrinterBackend.NetworkTcp,
                        onLeft = { viewModel.setPrinterBackend(PrinterBackend.NetworkTcp) },
                        onRight = { viewModel.setPrinterBackend(PrinterBackend.UsbDirect) },
                    )
                    BackendToggle(
                        label = "TPE SumUp via",
                        leftLabel = "SDK BT",
                        rightLabel = "REST polling",
                        leftSelected = state.paymentBackend == PaymentBackend.SumUpSdk,
                        onLeft = { viewModel.setPaymentBackend(PaymentBackend.SumUpSdk) },
                        onRight = { viewModel.setPaymentBackend(PaymentBackend.SumUpRest) },
                    )
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("Scan caméra fallback", modifier = Modifier.weight(1f))
                        Switch(
                            checked = state.cameraScannerEnabled,
                            onCheckedChange = viewModel::setCameraScanner,
                        )
                    }
                }
            }

            state.error?.let {
                Text(it, color = MaterialTheme.colorScheme.error)
            }
        }
    }
}

@Composable
private fun BackendToggle(
    label: String,
    leftLabel: String,
    rightLabel: String,
    leftSelected: Boolean,
    onLeft: () -> Unit,
    onRight: () -> Unit,
) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text(label, modifier = Modifier.weight(1f))
        Button(onClick = onLeft, enabled = !leftSelected) { Text(leftLabel) }
        Spacer(Modifier.height(4.dp))
        Button(onClick = onRight, enabled = leftSelected) { Text(rightLabel) }
    }
}
