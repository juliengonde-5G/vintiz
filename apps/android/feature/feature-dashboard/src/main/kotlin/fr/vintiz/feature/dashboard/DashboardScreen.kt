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
import fr.vintiz.data.reports.ReportsRepository
import fr.vintiz.data.reports.TopProductDto
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
                value = Money(data.today_revenue_cents).format(),
                modifier = Modifier.weight(1f),
            )
            KpiCard(
                title = "Tickets",
                value = data.today_transactions.toString(),
                modifier = Modifier.weight(1f),
            )
            KpiCard(
                title = "Panier moyen",
                value = Money(data.today_average_cart_cents).format(),
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

        Text("Top produits", style = MaterialTheme.typography.titleLarge)
        LazyColumn(verticalArrangement = Arrangement.spacedBy(6.dp)) {
            items(data.top_products, key = { it.product_id }) { p -> TopProductRow(p) }
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
private fun TopProductRow(p: TopProductDto) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(p.name, style = MaterialTheme.typography.titleMedium)
                Text("× ${p.sold_quantity}", style = MaterialTheme.typography.bodySmall)
            }
            Text(Money(p.revenue_cents).format())
        }
    }
}
