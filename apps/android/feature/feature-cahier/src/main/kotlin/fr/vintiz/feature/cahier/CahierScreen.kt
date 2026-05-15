package fr.vintiz.feature.cahier

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
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
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
import fr.vintiz.core.common.Money
import fr.vintiz.core.common.VintizResult
import fr.vintiz.data.cahier.CahierDayDto
import fr.vintiz.data.cahier.CahierRepository
import fr.vintiz.domain.cahier.CahierDay
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
                    it.copy(loading = false, day = r.value.toDomain(), error = null,
                        messageDraft = r.value.message_of_the_day.orEmpty(),
                        operationDraft = r.value.current_operation.orEmpty())
                }
                is VintizResult.Failure -> _state.update {
                    it.copy(loading = false, error = r.error.message)
                }
            }
        }
    }

    fun onMessage(v: String) = _state.update { it.copy(messageDraft = v) }
    fun onOperation(v: String) = _state.update { it.copy(operationDraft = v) }

    fun saveTexts() {
        val s = _state.value
        viewModelScope.launch {
            when (val r = repo.setDailyText(s.date, s.messageDraft, s.operationDraft)) {
                is VintizResult.Success -> _state.update {
                    it.copy(day = r.value.toDomain(), savedAt = System.currentTimeMillis())
                }
                is VintizResult.Failure -> _state.update { it.copy(error = r.error.message) }
            }
        }
    }

    fun sign(role: String, signature: String) {
        val s = _state.value
        viewModelScope.launch {
            when (val r = repo.sign(s.date, role, signature)) {
                is VintizResult.Success -> _state.update { it.copy(day = r.value.toDomain()) }
                is VintizResult.Failure -> _state.update { it.copy(error = r.error.message) }
            }
        }
    }
}

internal fun CahierDayDto.toDomain(): CahierDay = CahierDay(
    date = date,
    target = Money(target_cents),
    actual = Money(actual_cents),
    transactionCount = transaction_count,
    cumulativeMonth = Money(cumulative_month_cents),
    remainingMonth = Money(remaining_month_cents),
    yearAgo = Money(ya1_cents),
    messageOfTheDay = message_of_the_day,
    currentOperation = current_operation,
    managerSignature = manager_signature,
    teamSignature = team_signature,
)

data class CahierUiState(
    val loading: Boolean = false,
    val date: String = "",
    val day: CahierDay? = null,
    val messageDraft: String = "",
    val operationDraft: String = "",
    val savedAt: Long? = null,
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
            Text("Cahier du jour", style = MaterialTheme.typography.headlineLarge)
            state.day?.let { day ->
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text("Objectif jour : ${day.target.format()}",
                            style = MaterialTheme.typography.titleMedium)
                        LinearProgressIndicator(
                            progress = { day.dayProgress },
                            modifier = Modifier.fillMaxWidth().height(8.dp),
                        )
                        Row {
                            Text("Réalisé : ${day.actual.format()}", modifier = Modifier.weight(1f))
                            Text("${(day.rawDayProgress * 100).toInt()}%")
                        }
                        Text("Tickets : ${day.transactionCount}",
                            style = MaterialTheme.typography.bodyMedium)
                        Spacer(Modifier.height(4.dp))
                        Text("Cumul mois : ${day.cumulativeMonth.format()}")
                        Text("Reste à faire : ${day.remainingMonth.format()}")
                        if (day.yearAgo.cents > 0) {
                            val delta = day.yearOnYearDeltaPercent
                            val sign = if (delta >= 0) "+" else ""
                            Text("vs N-1 : $sign$delta%",
                                color = if (delta >= 0) MaterialTheme.colorScheme.primary
                                else MaterialTheme.colorScheme.error)
                        }
                    }
                }
            }

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

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = viewModel::saveTexts) { Text("Enregistrer") }
                Button(onClick = { viewModel.sign("manager", "Manager") }) { Text("Signer manager") }
                Button(onClick = { viewModel.sign("equipe", "Équipe") }) { Text("Signer équipe") }
            }

            state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        }
    }
}
