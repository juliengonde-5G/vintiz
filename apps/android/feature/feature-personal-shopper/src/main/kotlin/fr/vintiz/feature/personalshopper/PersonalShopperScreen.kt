package fr.vintiz.feature.personalshopper

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import coil.compose.AsyncImage
import fr.vintiz.core.common.Money
import fr.vintiz.data.personalshopper.PickDto

@Composable
fun PersonalShopperScreen(viewModel: PersonalShopperViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsState()

    Scaffold { padding ->
        Column(
            modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("Personal Shopper", style = MaterialTheme.typography.headlineLarge)
            Text(
                "Recommandations basées sur les goûts et le profil RFM " +
                    "de la cliente. Gated par le consentement profilage.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            val selected = state.selectedClient
            if (selected == null) {
                ClientPicker(state, viewModel::onSearchChange, viewModel::selectClient)
            } else {
                ClientHeader(selected.fullName(), onClear = viewModel::clearClient)
                FreeSearchBar(
                    query = state.freeSearchQuery,
                    busy = state.freeSearching,
                    onChange = viewModel::onFreeSearchChange,
                    onRun = viewModel::runFreeSearch,
                )
                state.freeSearchError?.let {
                    Text("⚠ $it", color = MaterialTheme.colorScheme.error,
                        style = MaterialTheme.typography.bodySmall)
                }
                when {
                    state.freeSearchResults.isNotEmpty() -> PicksGrid(
                        picks = state.freeSearchResults,
                        rationale = "Résultats Claude Haiku",
                        onClick = viewModel::trackClick,
                    )
                    state.loadingPicks -> Box(
                        modifier = Modifier.fillMaxWidth(),
                        contentAlignment = Alignment.Center,
                    ) { CircularProgressIndicator() }
                    state.error != null -> Text(
                        state.error!!,
                        color = MaterialTheme.colorScheme.error,
                    )
                    else -> PicksGrid(
                        picks = state.picks?.picks ?: emptyList(),
                        rationale = state.picks?.rationale,
                        onClick = viewModel::trackClick,
                    )
                }
            }
        }
    }
}

@Composable
private fun ClientPicker(
    state: PersonalShopperUiState,
    onSearch: (String) -> Unit,
    onSelect: (fr.vintiz.data.clients.ClientDto) -> Unit,
) {
    OutlinedTextField(
        value = state.searchQuery,
        onValueChange = onSearch,
        label = { Text("Rechercher cliente (email, V######, téléphone)") },
        singleLine = true,
        modifier = Modifier.fillMaxWidth(),
    )
    state.error?.takeIf { state.candidates.isEmpty() }?.let {
        Text(it, color = MaterialTheme.colorScheme.error)
    }
    LazyColumn(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        items(state.candidates, key = { it.id }) { c ->
            Card(onClick = { onSelect(c) }, modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(12.dp)) {
                    Text(c.fullName(), style = MaterialTheme.typography.titleMedium)
                    Text(
                        "${c.email ?: c.phone ?: "—"} • ${c.membership_number ?: ""}",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
    }
}

@Composable
private fun ClientHeader(displayName: String, onClear: () -> Unit) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text(
            displayName,
            modifier = Modifier.weight(1f),
            style = MaterialTheme.typography.titleLarge,
        )
        TextButton(onClick = onClear) { Text("Changer") }
    }
}

@Composable
private fun PicksGrid(picks: List<PickDto>, rationale: String?, onClick: (PickDto) -> Unit) {
    if (picks.isEmpty()) {
        Text(
            "Pas de recommandation disponible pour cette cliente.",
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        return
    }
    rationale?.takeIf { it.isNotBlank() }?.let {
        Card(modifier = Modifier.fillMaxWidth()) {
            Text(
                it,
                modifier = Modifier.padding(12.dp),
                style = MaterialTheme.typography.bodyMedium,
            )
        }
    }
    LazyColumn(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        items(picks, key = { it.product_id }) { p -> PickCard(p, onClick = { onClick(p) }) }
    }
}

@Composable
private fun PickCard(p: PickDto, onClick: () -> Unit) {
    Card(onClick = onClick, modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            if (!p.photo_url.isNullOrBlank()) {
                AsyncImage(
                    model = p.photo_url,
                    contentDescription = p.name,
                    modifier = Modifier.size(64.dp).clip(RoundedCornerShape(8.dp)),
                )
                Spacer(Modifier.size(12.dp))
            }
            Column(modifier = Modifier.weight(1f)) {
                Text(p.name, style = MaterialTheme.typography.titleMedium)
                p.reason?.takeIf { it.isNotBlank() }?.let {
                    Text(
                        it,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            Column(horizontalAlignment = Alignment.End) {
                Text(Money(p.price_cents).format(),
                    style = MaterialTheme.typography.titleMedium)
                if (p.score > 0) {
                    Text(
                        "score ${"%.0f".format(p.score * 100)} %",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.primary,
                    )
                }
            }
        }
    }
}

@Composable
private fun FreeSearchBar(
    query: String,
    busy: Boolean,
    onChange: (String) -> Unit,
    onRun: () -> Unit,
) {
    androidx.compose.material3.Card(modifier = Modifier.fillMaxWidth()) {
        androidx.compose.foundation.layout.Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(8.dp),
        ) {
            Text(
                "Recherche libre (Claude Haiku)",
                style = MaterialTheme.typography.titleSmall,
            )
            Text(
                "Ex : « robe taille M en lin », « pantalon noir hiver », " +
                    "« sac marque Sandro ». L'IA extrait les filtres et match " +
                    "l'inventaire vendable.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            androidx.compose.material3.OutlinedTextField(
                value = query,
                onValueChange = onChange,
                placeholder = { Text("Décrire ce que cherche la cliente") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            androidx.compose.material3.Button(
                onClick = onRun,
                enabled = !busy && query.trim().length >= 3,
            ) { Text(if (busy) "Recherche…" else "Rechercher") }
        }
    }
}

private fun fr.vintiz.data.clients.ClientDto.fullName(): String =
    "$first_name ${last_name.uppercase()}".trim()
