package fr.vintiz.feature.cahier

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import fr.vintiz.core.common.VintizResult
import fr.vintiz.data.cahier.CahierDayDto
import fr.vintiz.data.cahier.CahierRepository
import fr.vintiz.data.cahier.WeekdayWeightsDto
import fr.vintiz.data.cahier.ZoningRowDto
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.time.LocalDate

@HiltViewModel
class CahierViewModel @Inject constructor(
    private val repo: CahierRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(CahierUiState())
    val state: StateFlow<CahierUiState> = _state.asStateFlow()

    fun load(date: String = LocalDate.now().toString()) {
        _state.update { it.copy(loading = true, date = date) }
        viewModelScope.launch {
            when (val r = repo.day(date)) {
                is VintizResult.Success -> _state.update {
                    val day = r.value
                    it.copy(
                        loading = false,
                        day = day,
                        error = null,
                        messageDraft = day.header.message_du_jour.orEmpty(),
                        operationDraft = day.header.operation_en_cours.orEmpty(),
                    )
                }
                is VintizResult.Failure -> _state.update {
                    it.copy(loading = false, error = r.error.message)
                }
            }
            (repo.weekdayWeights() as? VintizResult.Success)?.let { ok ->
                _state.update { it.copy(weekdayWeights = ok.value) }
            }
            val parsed = runCatching { LocalDate.parse(date) }.getOrNull()
            if (parsed != null) {
                (repo.monthlyTarget(parsed.year, parsed.monthValue) as? VintizResult.Success)
                    ?.let { ok ->
                        _state.update { it.copy(monthlyTargetSavedEur = ok.value.target_eur) }
                    }
            }
        }
    }

    fun setMonthlyTargetInput(v: String) {
        // input EUR, accepte virgule ou point
        _state.update { it.copy(monthlyTargetInput = v.filter { c -> c.isDigit() || c == '.' || c == ',' }) }
    }

    fun saveMonthlyTarget() {
        val raw = _state.value.monthlyTargetInput.replace(",", ".")
        val target = raw.toDoubleOrNull() ?: return
        val parsedDate = runCatching { LocalDate.parse(_state.value.date) }
            .getOrNull() ?: return
        viewModelScope.launch {
            when (val r = repo.setMonthlyTarget(parsedDate.year, parsedDate.monthValue, target)) {
                is VintizResult.Success -> {
                    _state.update {
                        it.copy(
                            monthlyTargetSavedEur = target,
                            monthlyTargetInput = "",
                            savedAt = System.currentTimeMillis(),
                        )
                    }
                    load(_state.value.date)
                }
                is VintizResult.Failure -> _state.update { it.copy(error = r.error.message) }
            }
        }
    }

    fun onMessage(v: String) = _state.update { it.copy(messageDraft = v) }
    fun onOperation(v: String) = _state.update { it.copy(operationDraft = v) }

    fun saveTexts() {
        val s = _state.value
        viewModelScope.launch {
            when (val r = repo.setDailyText(s.date, s.messageDraft, s.operationDraft)) {
                is VintizResult.Success -> {
                    _state.update { it.copy(savedAt = System.currentTimeMillis()) }
                    load(s.date)
                }
                is VintizResult.Failure -> _state.update { it.copy(error = r.error.message) }
            }
        }
    }
}

data class CahierUiState(
    val loading: Boolean = false,
    val date: String = "",
    val day: CahierDayDto? = null,
    val messageDraft: String = "",
    val operationDraft: String = "",
    val savedAt: Long? = null,
    val weekdayWeights: WeekdayWeightsDto? = null,
    val monthlyTargetInput: String = "",
    val monthlyTargetSavedEur: Double? = null,
    val error: String? = null,
)

@Composable
fun CahierScreen(viewModel: CahierViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsState()
    LaunchedEffect(Unit) { viewModel.load() }

    Scaffold { padding ->
        Column(
            modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(
                "Cahier du jour" + (state.day?.weekday?.takeIf { it.isNotBlank() }?.let { " — $it" } ?: ""),
                style = MaterialTheme.typography.headlineLarge,
            )

            state.day?.let { day -> ObjectifsCard(day) }
            state.day?.let { day -> PerformanceCard(day) }
            state.day?.let { day ->
                if (day.zoning.isNotEmpty()) ZoningCard(day.zoning)
            }
            state.day?.let { day -> CrmLoyaltyCard(day) }

            OutlinedTextField(
                value = state.messageDraft,
                onValueChange = viewModel::onMessage,
                label = { Text("Message du jour") },
                modifier = Modifier.fillMaxWidth(),
                minLines = 2,
            )
            OutlinedTextField(
                value = state.operationDraft,
                onValueChange = viewModel::onOperation,
                label = { Text("Opération en cours") },
                modifier = Modifier.fillMaxWidth(),
                minLines = 2,
            )

            Button(
                onClick = viewModel::saveTexts,
                enabled = state.day?.is_past != true,
            ) {
                Text(if (state.day?.is_past == true) "Lecture seule (passé)" else "Enregistrer")
            }

            state.weekdayWeights?.let { WeekdayWeightsCard(it) }
            MonthlyTargetCard(state, viewModel::setMonthlyTargetInput, viewModel::saveMonthlyTarget)

            state.error?.let { Text("⚠ $it", color = MaterialTheme.colorScheme.error) }
        }
    }
}

@Composable
private fun ObjectifsCard(day: CahierDayDto) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Objectif jour", style = MaterialTheme.typography.titleMedium)
            val obj = day.objectifs_valeur.ca_objectif_jour ?: 0.0
            val real = day.performance.ca
            val ratio = if (obj > 0.0) (real / obj).coerceIn(0.0, 1.0) else 0.0
            LinearProgressIndicator(
                progress = { ratio.toFloat() },
                modifier = Modifier.fillMaxWidth().height(8.dp),
            )
            Row {
                Text("Réalisé : %.2f €".format(real), modifier = Modifier.weight(1f))
                Text("Objectif : %.2f €".format(obj))
            }
            day.performance.prog_vs_obj_pct?.let {
                Text("Prog vs obj : %+.1f%%".format(it),
                    color = if (it >= 0) MaterialTheme.colorScheme.primary
                    else MaterialTheme.colorScheme.error)
            }
            Spacer(Modifier.height(4.dp))
            day.objectifs_valeur.ca_budget_mois?.let {
                Text("Budget mois : %.2f €".format(it))
            }
            Text("Cumul mois : %.2f €".format(day.objectifs_valeur.prog_ca_cumul_mois))
            day.objectifs_valeur.reste_a_faire_mois?.let {
                Text("Reste à faire : %.2f €".format(it))
            }
            if (day.objectifs_valeur.ca_n1_jour > 0) {
                day.performance.delta_vs_n1_pct?.let { delta ->
                    val src = day.objectifs_valeur.ca_n1_source?.let { " ($it)" } ?: ""
                    Text("vs N-1$src : %+.1f%%".format(delta),
                        color = if (delta >= 0) MaterialTheme.colorScheme.primary
                        else MaterialTheme.colorScheme.error)
                }
            }
        }
    }
}

@Composable
private fun PerformanceCard(day: CahierDayDto) {
    val p = day.performance
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text("Performance", style = MaterialTheme.typography.titleMedium)
            Row {
                MetricCell("Tickets", "${p.tk}", modifier = Modifier.weight(1f))
                MetricCell("IV", "%.2f".format(p.iv), modifier = Modifier.weight(1f))
                MetricCell("PM", "%.2f €".format(p.pm), modifier = Modifier.weight(1f))
            }
            Row {
                MetricCell("CRM", "%.0f%%".format(p.tx_crm_pct), modifier = Modifier.weight(1f))
                MetricCell("Fidélité", "%.0f%%".format(p.loyalty_pct), modifier = Modifier.weight(1f))
                MetricCell("Prod", "%.0f €/h".format(p.prod), modifier = Modifier.weight(1f))
            }
        }
    }
}

@Composable
private fun MetricCell(label: String, value: String, modifier: Modifier = Modifier) {
    Column(modifier = modifier, horizontalAlignment = Alignment.CenterHorizontally) {
        Text(value, style = MaterialTheme.typography.titleLarge)
        Text(label, style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun ZoningCard(zoning: List<ZoningRowDto>) {
    val fallback = MaterialTheme.colorScheme.primary
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text("Zones boutique", style = MaterialTheme.typography.titleMedium)
            zoning.forEach { z ->
                val color = remember(z.color_code) {
                    runCatching {
                        Color(android.graphics.Color.parseColor(z.color_code))
                    }.getOrDefault(fallback)
                }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .width(10.dp)
                            .height(20.dp)
                            .background(color),
                    )
                    Spacer(Modifier.width(8.dp))
                    Column(modifier = Modifier.weight(1f)) {
                        Text(z.zone_name, style = MaterialTheme.typography.titleSmall)
                        Text(
                            "Obj %.0f € · Réa %.0f € · ${z.units} u".format(z.obj_jour, z.ca),
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    z.delta_pct?.let {
                        Text("%+.0f%%".format(it),
                            color = if (it >= 0) MaterialTheme.colorScheme.primary
                            else MaterialTheme.colorScheme.error)
                    }
                }
            }
        }
    }
}

@Composable
private fun CrmLoyaltyCard(day: CahierDayDto) {
    val c = day.crm_loyalty
    if (c.fiches_creees + c.adhesions_fidelite + c.tickets_fidelo == 0) return
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text("CRM & Fidélité", style = MaterialTheme.typography.titleMedium)
            Row {
                MetricCell("Fiches", "${c.fiches_creees}", modifier = Modifier.weight(1f))
                MetricCell("Adhésions", "${c.adhesions_fidelite}", modifier = Modifier.weight(1f))
                MetricCell("Tickets fid.", "${c.tickets_fidelo}", modifier = Modifier.weight(1f))
            }
        }
    }
}

@Composable
private fun WeekdayWeightsCard(w: WeekdayWeightsDto) {
    if (w.weights.isEmpty()) return
    val labels = listOf("L", "M", "M", "J", "V", "S", "D")
    val max = w.weights.maxOrNull() ?: 1.0
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Text("Poids historique des jours", style = MaterialTheme.typography.titleMedium)
            Text(
                "Sur ${w.sample_weeks} semaines. Répartit l'objectif mensuel jour par jour.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Row(
                modifier = Modifier.fillMaxWidth().height(60.dp),
                verticalAlignment = Alignment.Bottom,
                horizontalArrangement = Arrangement.SpaceAround,
            ) {
                w.weights.forEachIndexed { i, value ->
                    val ratio = (value / max).toFloat().coerceIn(0f, 1f)
                    val primary = MaterialTheme.colorScheme.primary
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Box(
                            modifier = Modifier
                                .width(20.dp)
                                .height((40 * ratio).dp.coerceAtLeast(4.dp))
                                .background(primary),
                        )
                        Text(labels.getOrNull(i) ?: "?",
                            style = MaterialTheme.typography.labelSmall)
                    }
                }
            }
        }
    }
}

@Composable
private fun MonthlyTargetCard(
    state: CahierUiState,
    onChange: (String) -> Unit,
    onSave: () -> Unit,
) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Objectif mensuel", style = MaterialTheme.typography.titleMedium)
            state.monthlyTargetSavedEur?.let {
                Text("Actuel : %.2f €".format(it), color = MaterialTheme.colorScheme.primary)
            }
            OutlinedTextField(
                value = state.monthlyTargetInput,
                onValueChange = onChange,
                label = { Text("Nouvel objectif (€)") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            Button(
                onClick = onSave,
                enabled = state.monthlyTargetInput
                    .replace(",", ".").toDoubleOrNull()?.let { it > 0 } == true,
            ) {
                Text("Enregistrer l'objectif")
            }
        }
    }
}
