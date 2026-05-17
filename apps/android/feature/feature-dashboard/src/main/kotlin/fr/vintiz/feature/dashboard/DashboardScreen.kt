package fr.vintiz.feature.dashboard

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
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
import fr.vintiz.data.reports.DashboardDto
import fr.vintiz.data.reports.DashboardTopProductDto
import fr.vintiz.data.reports.ReportsRepository
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

@HiltViewModel
class DashboardViewModel @Inject constructor(
    private val repo: ReportsRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(DashboardUiState())
    val state: StateFlow<DashboardUiState> = _state.asStateFlow()

    fun load() {
        _state.update { it.copy(loading = true) }
        viewModelScope.launch {
            when (val r = repo.dashboard()) {
                is VintizResult.Success -> _state.update {
                    it.copy(loading = false, data = r.value, error = null)
                }
                is VintizResult.Failure -> _state.update {
                    it.copy(loading = false, error = r.error.message)
                }
            }
        }
    }
}

data class DashboardUiState(
    val loading: Boolean = false,
    val data: DashboardDto? = null,
    val error: String? = null,
)

@Composable
fun DashboardScreen(viewModel: DashboardViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsState()
    LaunchedEffect(Unit) { viewModel.load() }
    Scaffold { padding -> DashboardContent(state, padding) }
}

@Composable
internal fun DashboardContent(state: DashboardUiState, padding: PaddingValues) {
    Column(
        modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("Tableau de bord", style = MaterialTheme.typography.headlineLarge)

        if (state.loading) {
            Box(modifier = Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
            return@Column
        }

        val data = state.data
        if (data == null) {
            state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            return@Column
        }

        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            KpiCard(
                title = "CA du jour",
                value = "%.2f €".format(data.today.revenue),
                modifier = Modifier.weight(1f),
            )
            KpiCard(
                title = "Tickets",
                value = data.today.transaction_count.toString(),
                modifier = Modifier.weight(1f),
            )
            KpiCard(
                title = "Panier moyen",
                value = "%.2f €".format(data.today.avg_basket),
                modifier = Modifier.weight(1f),
            )
        }

        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            KpiCard(
                title = "Stock (articles)",
                value = data.stock.count.toString(),
                modifier = Modifier.weight(1f),
            )
            KpiCard(
                title = "Valeur stock",
                value = "%.2f €".format(data.stock.value),
                modifier = Modifier.weight(1f),
            )
        }

        data.weather?.let { w ->
            Card(modifier = Modifier.fillMaxWidth()) {
                Row(
                    modifier = Modifier.fillMaxWidth().padding(12.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text("Météo Vernon", modifier = Modifier.weight(1f))
                    Text("${"%.1f".format(w.temperature_c)} °C — ${w.description}")
                }
            }
        }

        Text("Top produits semaine", style = MaterialTheme.typography.titleLarge)
        LazyColumn(
            modifier = Modifier.height(180.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            items(data.top_products_week, key = { it.name }) { p ->
                DashboardTopProductRow(p)
            }
        }

        if (data.recent_transactions.isNotEmpty()) {
            Text("Tickets récents", style = MaterialTheme.typography.titleLarge)
            LazyColumn(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                items(data.recent_transactions, key = { it.id }) { t ->
                    Card(modifier = Modifier.fillMaxWidth()) {
                        Row(
                            modifier = Modifier.fillMaxWidth().padding(12.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Column(modifier = Modifier.weight(1f)) {
                                val date = t.created_at?.take(16)?.replace("T", " ") ?: "—"
                                Text(t.transaction_number ?: "#${t.id.take(8)}",
                                    style = MaterialTheme.typography.titleSmall)
                                Text("$date • ${t.type}",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                            Text("%.2f €".format(t.total_ttc))
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun DashboardTopProductRow(p: DashboardTopProductDto) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(p.name, style = MaterialTheme.typography.titleMedium)
                Text("× ${p.quantity}", style = MaterialTheme.typography.bodySmall)
            }
            Text("%.2f €".format(p.revenue))
        }
    }
}

@Composable
private fun KpiCard(title: String, value: String, modifier: Modifier = Modifier) {
    Card(modifier = modifier) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(title, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.height(8.dp))
            Text(value, style = MaterialTheme.typography.headlineMedium)
        }
    }
}

@Composable
private fun TopProductRowLegacy(p: DashboardTopProductDto) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(p.name, style = MaterialTheme.typography.titleMedium)
                Text("× ${p.quantity}", style = MaterialTheme.typography.bodySmall)
            }
            Text("%.2f €".format(p.revenue))
        }
    }
}
