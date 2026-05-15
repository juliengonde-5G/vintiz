package fr.vintiz.feature.ia

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import fr.vintiz.core.common.VintizResult
import fr.vintiz.data.ia.ChecklistItemDto
import fr.vintiz.data.ia.IaRepository
import fr.vintiz.data.ia.TrendSignalDto
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

@HiltViewModel
class IaViewModel @Inject constructor(private val repo: IaRepository) : ViewModel() {

    private val _state = MutableStateFlow(IaUiState())
    val state: StateFlow<IaUiState> = _state.asStateFlow()

    fun loadAll() {
        viewModelScope.launch {
            (repo.weeklyChecklist() as? VintizResult.Success)?.let { ok ->
                _state.update { it.copy(checklist = ok.value.items) }
            }
            (repo.trends() as? VintizResult.Success)?.let { ok ->
                _state.update {
                    it.copy(social = ok.value.social_signals, retail = ok.value.retail_signals)
                }
            }
        }
    }

    fun selectTab(i: Int) = _state.update { it.copy(tab = i) }
}

data class IaUiState(
    val tab: Int = 0,
    val checklist: List<ChecklistItemDto> = emptyList(),
    val social: List<TrendSignalDto> = emptyList(),
    val retail: List<TrendSignalDto> = emptyList(),
)

@Composable
fun IaScreen(viewModel: IaViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsState()
    LaunchedEffect(Unit) { viewModel.loadAll() }

    Scaffold { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding)) {
            Text("Compagnon IA",
                style = MaterialTheme.typography.headlineLarge,
                modifier = Modifier.padding(16.dp))
            TabRow(selectedTabIndex = state.tab) {
                listOf("Checklist", "Tendances", "Retail").forEachIndexed { i, label ->
                    Tab(selected = state.tab == i, onClick = { viewModel.selectTab(i) }, text = { Text(label) })
                }
            }
            when (state.tab) {
                0 -> ChecklistTab(state.checklist)
                1 -> SignalsTab(state.social, title = "Signaux sociaux")
                else -> SignalsTab(state.retail, title = "Signaux retail")
            }
        }
    }
}

@Composable
private fun ChecklistTab(items: List<ChecklistItemDto>) {
    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        items(items, key = { it.id }) { item ->
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(12.dp)) {
                    Row {
                        Text(item.title,
                            modifier = Modifier.weight(1f),
                            style = MaterialTheme.typography.titleMedium)
                        AssistChip(onClick = {}, label = { Text(item.priority) })
                    }
                    item.rationale?.let {
                        Text(it, style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
    }
}

@Composable
private fun SignalsTab(signals: List<TrendSignalDto>, title: String) {
    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        item { Text(title, style = MaterialTheme.typography.titleLarge) }
        items(signals, key = { it.label }) { s ->
            Card(modifier = Modifier.fillMaxWidth()) {
                Row(modifier = Modifier.fillMaxWidth().padding(12.dp)) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(s.label, style = MaterialTheme.typography.titleSmall)
                        Text(s.source, style = MaterialTheme.typography.labelSmall)
                    }
                    Text("${(s.score * 100).toInt()} %")
                }
            }
        }
    }
}
