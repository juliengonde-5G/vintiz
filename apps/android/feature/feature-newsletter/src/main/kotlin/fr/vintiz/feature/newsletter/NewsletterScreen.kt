package fr.vintiz.feature.newsletter

import android.content.Intent
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
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import fr.vintiz.core.common.VintizResult
import fr.vintiz.data.newsletter.NewsletterRepository
import fr.vintiz.data.newsletter.SubscriberDto
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

@HiltViewModel
class NewsletterViewModel @Inject constructor(
    private val repo: NewsletterRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(NewsletterUiState())
    val state: StateFlow<NewsletterUiState> = _state.asStateFlow()

    fun load(query: String? = null) {
        _state.update { it.copy(loading = true, query = query.orEmpty(), error = null) }
        viewModelScope.launch {
            when (val r = repo.list(query)) {
                is VintizResult.Success -> _state.update {
                    it.copy(loading = false, subscribers = r.value)
                }
                is VintizResult.Failure -> _state.update {
                    it.copy(loading = false, error = r.error.message)
                }
            }
        }
    }

    fun onQueryChange(q: String) {
        _state.update { it.copy(query = q) }
    }

    fun search() = load(_state.value.query.takeIf { it.isNotBlank() })

    fun confirmDelete(s: SubscriberDto) {
        _state.update { it.copy(pendingDelete = s) }
    }

    fun cancelDelete() = _state.update { it.copy(pendingDelete = null) }

    fun runDelete() {
        val s = _state.value.pendingDelete ?: return
        _state.update { it.copy(pendingDelete = null) }
        viewModelScope.launch {
            when (val r = repo.delete(s.id)) {
                is VintizResult.Success -> load(_state.value.query.takeIf { it.isNotBlank() })
                is VintizResult.Failure -> _state.update { it.copy(error = r.error.message) }
            }
        }
    }

    fun exportCsv() {
        _state.update { it.copy(exporting = true, lastExport = null, error = null) }
        viewModelScope.launch {
            when (val r = repo.exportCsv()) {
                is VintizResult.Success -> _state.update {
                    it.copy(exporting = false, lastExport = r.value)
                }
                is VintizResult.Failure -> _state.update {
                    it.copy(exporting = false, error = r.error.message)
                }
            }
        }
    }
}

data class NewsletterUiState(
    val loading: Boolean = false,
    val query: String = "",
    val subscribers: List<SubscriberDto> = emptyList(),
    val pendingDelete: SubscriberDto? = null,
    val exporting: Boolean = false,
    val lastExport: NewsletterRepository.CsvExport? = null,
    val error: String? = null,
)

@Composable
fun NewsletterScreen(viewModel: NewsletterViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsState()
    val context = LocalContext.current
    LaunchedEffect(Unit) { viewModel.load() }

    Scaffold { padding ->
        Column(
            modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("Newsletter — abonnés RGPD", style = MaterialTheme.typography.headlineLarge)
            Text(
                "Liste des consents actifs. Suppression = RGPD article 17 (droit à l'oubli) — irréversible.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            Row(verticalAlignment = Alignment.CenterVertically) {
                OutlinedTextField(
                    value = state.query,
                    onValueChange = viewModel::onQueryChange,
                    label = { Text("Filtrer (email, prénom)") },
                    singleLine = true,
                    modifier = Modifier.weight(1f),
                )
                Spacer(Modifier.padding(horizontal = 4.dp))
                Button(onClick = viewModel::search) { Text("Filtrer") }
            }

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = viewModel::exportCsv, enabled = !state.exporting) {
                    Text(if (state.exporting) "Export…" else "Exporter CSV")
                }
                state.lastExport?.let { exp ->
                    OutlinedButton(onClick = {
                        val intent = Intent(Intent.ACTION_SEND).apply {
                            type = "text/csv"
                            putExtra(Intent.EXTRA_STREAM, exp.uri)
                            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                        }
                        ContextCompat.startActivity(
                            context,
                            Intent.createChooser(intent, "Partager export newsletter"),
                            null,
                        )
                    }) { Text("Partager ${exp.filename}") }
                }
            }

            if (state.loading) {
                Row(horizontalArrangement = Arrangement.Center, modifier = Modifier.fillMaxWidth()) {
                    CircularProgressIndicator()
                }
            }

            state.error?.let {
                Text(it, color = MaterialTheme.colorScheme.error)
            }

            LazyColumn(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                items(state.subscribers, key = { it.id }) { sub ->
                    SubscriberCard(sub, onDelete = { viewModel.confirmDelete(sub) })
                }
            }
        }
    }

    state.pendingDelete?.let { sub ->
        AlertDialog(
            onDismissRequest = viewModel::cancelDelete,
            title = { Text("Supprimer ${sub.email} ?") },
            text = {
                Text(
                    "Cette suppression est définitive (RGPD article 17). L'abonné " +
                        "ne pourra plus être contacté, et son consentement historique " +
                        "sera effacé.",
                )
            },
            confirmButton = { Button(onClick = viewModel::runDelete) { Text("Supprimer") } },
            dismissButton = { TextButton(onClick = viewModel::cancelDelete) { Text("Annuler") } },
        )
    }
}

@Composable
private fun SubscriberCard(sub: SubscriberDto, onDelete: () -> Unit) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    "${sub.first_name.orEmpty()} ${sub.email}".trim(),
                    style = MaterialTheme.typography.titleMedium,
                )
                Text(
                    "Inscrit ${sub.subscribed_at.take(10)} • " +
                        (sub.consent_text_version ?: "—"),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            if (sub.isActive) {
                AssistChip(onClick = {}, label = { Text("Actif") })
            } else {
                AssistChip(onClick = {}, label = { Text("Désinscrit") })
            }
            Spacer(Modifier.padding(horizontal = 4.dp))
            TextButton(onClick = onDelete) { Text("✕") }
        }
    }
}
