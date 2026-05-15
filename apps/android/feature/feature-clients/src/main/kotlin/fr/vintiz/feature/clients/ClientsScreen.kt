package fr.vintiz.feature.clients

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
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
import fr.vintiz.data.clients.ClientDto
import fr.vintiz.data.clients.ClientsRepository
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

@HiltViewModel
class ClientsViewModel @Inject constructor(
    private val repo: ClientsRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(ClientsUiState())
    val state: StateFlow<ClientsUiState> = _state.asStateFlow()

    fun onSearch(q: String) {
        _state.update { it.copy(query = q) }
        if (q.length < 2) return
        viewModelScope.launch {
            when (val r = repo.identify(q)) {
                is VintizResult.Success -> _state.update { it.copy(items = r.value) }
                is VintizResult.Failure -> _state.update { it.copy(error = r.error.message) }
            }
        }
    }
}

data class ClientsUiState(
    val query: String = "",
    val items: List<ClientDto> = emptyList(),
    val error: String? = null,
)

@Composable
fun ClientsScreen(viewModel: ClientsViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsState()
    Scaffold { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp)) {
            Text("Clientes", style = MaterialTheme.typography.headlineLarge)
            Spacer(Modifier.height(12.dp))
            OutlinedTextField(
                value = state.query,
                onValueChange = viewModel::onSearch,
                label = { Text("Email, carte V###### ou téléphone") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(12.dp))
            LazyColumn(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                items(state.items, key = { it.id }) { c ->
                    Card(modifier = Modifier.fillMaxWidth()) {
                        Row(
                            modifier = Modifier.fillMaxWidth().padding(12.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Column(modifier = Modifier.weight(1f)) {
                                Text(
                                    "${c.first_name} ${c.last_name.uppercase()}",
                                    style = MaterialTheme.typography.titleMedium,
                                )
                                Text(
                                    "${c.email ?: c.phone ?: "—"} • ${c.membership_number ?: ""}",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                            Text("${c.loyalty_points} pts")
                        }
                    }
                }
            }
            state.error?.let {
                Spacer(Modifier.height(8.dp))
                Text(it, color = MaterialTheme.colorScheme.error)
            }
        }
    }
}
