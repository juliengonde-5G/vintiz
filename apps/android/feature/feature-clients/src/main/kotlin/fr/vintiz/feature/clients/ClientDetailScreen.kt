package fr.vintiz.feature.clients

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import fr.vintiz.core.common.Money
import fr.vintiz.data.clients.ClientAuditDto
import fr.vintiz.data.clients.ClientConsentDto
import fr.vintiz.data.clients.ClientFullDto
import fr.vintiz.data.clients.ClientTransactionDto

@Composable
fun ClientDetailScreen(
    clientId: String,
    onBack: () -> Unit,
    viewModel: ClientDetailViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsState()
    LaunchedEffect(clientId) { viewModel.load(clientId) }

    Scaffold { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding)) {
            TextButton(onClick = onBack, modifier = Modifier.padding(8.dp)) { Text("← Retour") }
            when {
                state.loading -> Box(modifier = Modifier.fillMaxWidth().padding(32.dp),
                    contentAlignment = Alignment.Center) { CircularProgressIndicator() }
                state.error != null -> Text(state.error!!,
                    modifier = Modifier.padding(16.dp),
                    color = MaterialTheme.colorScheme.error)
                state.full != null -> ClientFullBody(
                    full = state.full!!,
                    tab = state.tab,
                    rgpdBusy = state.rgpdBusy,
                    rgpdMessage = state.rgpdMessage,
                    onSelectTab = viewModel::selectTab,
                    onExport = viewModel::exportData,
                    onRequestDeletion = viewModel::requestDeletion,
                )
            }
        }
    }
}

@Composable
private fun ClientFullBody(
    full: ClientFullDto,
    tab: Int,
    rgpdBusy: Boolean,
    rgpdMessage: String?,
    onSelectTab: (Int) -> Unit,
    onExport: () -> Unit,
    onRequestDeletion: () -> Unit,
) {
    val c = full.client
    Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("${c.first_name} ${c.last_name.uppercase()}",
            style = MaterialTheme.typography.headlineMedium)
        Text(
            "${c.email ?: c.phone ?: "—"} • ${c.membership_number ?: "—"} • ${c.loyalty_points} pts",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        full.rfm_segment?.let { AssistChip(onClick = {}, label = { Text("RFM : $it") }) }
    }
    TabRow(selectedTabIndex = tab) {
        listOf("Synthèse", "Achats", "Fidélité", "Goûts", "RGPD", "Audit").forEachIndexed { i, label ->
            Tab(selected = tab == i, onClick = { onSelectTab(i) }, text = { Text(label) })
        }
    }
    when (tab) {
        0 -> SynthesisTab(full)
        1 -> PurchasesTab(full.recent_transactions)
        2 -> LoyaltyTab(full)
        3 -> TastesTab(full.tastes)
        4 -> RgpdTab(full.consents, rgpdBusy, rgpdMessage, onExport, onRequestDeletion)
        else -> AuditTab(full.recent_audit)
    }
}

@Composable
private fun SynthesisTab(full: ClientFullDto) {
    Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text("Total dépensé : ${Money(full.total_spent_cents).format()}",
            style = MaterialTheme.typography.titleMedium)
        Text("Nombre de tickets : ${full.transaction_count}")
        Text("Panier moyen : ${Money(full.avg_basket_cents).format()}")
        full.last_visit_at?.let { Text("Dernière visite : ${it.take(10)}") }
    }
}

@Composable
private fun PurchasesTab(items: List<ClientTransactionDto>) {
    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        if (items.isEmpty()) {
            item { Text("Aucun achat récent",
                color = MaterialTheme.colorScheme.onSurfaceVariant) }
        }
        items(items, key = { it.id }) { tx ->
            Card(modifier = Modifier.fillMaxWidth()) {
                Row(modifier = Modifier.fillMaxWidth().padding(12.dp)) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(Money(tx.total_cents).format(),
                            style = MaterialTheme.typography.titleMedium)
                        Text("${tx.timestamp.take(16).replace("T", " à ")} • ${tx.item_count} articles",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }
    }
}

@Composable
private fun LoyaltyTab(full: ClientFullDto) {
    Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text("Solde : ${full.client.loyalty_points} pts",
            style = MaterialTheme.typography.headlineMedium,
            color = MaterialTheme.colorScheme.primary)
        full.client.loyalty_tier?.takeIf { it.isNotBlank() }?.let {
            Text("Tier : $it", style = MaterialTheme.typography.titleMedium)
        }
        full.rfm_segment?.takeIf { it.isNotBlank() }?.let {
            Text("Segment RFM : $it", style = MaterialTheme.typography.bodyMedium)
        }
        HorizontalDivider()
        Text(
            "Pour modifier le solde ou l'historique points : passer par " +
                "l'admin web /clients/[id] (POS Android ne fait que lecture).",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun TastesTab(tastes: List<String>) {
    Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("Préférences détectées", style = MaterialTheme.typography.titleLarge)
        if (tastes.isEmpty()) {
            Text("Aucun goût détecté pour l'instant (onboarding non rempli ou trop peu d'achats).",
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            tastes.forEach { t -> AssistChip(onClick = {}, label = { Text(t) }) }
        }
    }
}

@Composable
private fun RgpdTab(
    consents: List<ClientConsentDto>,
    busy: Boolean,
    message: String?,
    onExport: () -> Unit,
    onRequestDeletion: () -> Unit,
) {
    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        item {
            Text("Consentements RGPD", style = MaterialTheme.typography.titleLarge)
            Text(
                "Modifications via l'espace client cliente.vintiz.fr/account/rgpd. " +
                    "L'app affiche en lecture + déclenche les droits Articles 17/20.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        items(consents, key = { it.purpose }) { c ->
            Card(modifier = Modifier.fillMaxWidth()) {
                Row(modifier = Modifier.fillMaxWidth().padding(12.dp),
                    verticalAlignment = Alignment.CenterVertically) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(c.purpose, style = MaterialTheme.typography.titleMedium)
                        Text(c.recorded_at.take(10),
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    AssistChip(
                        onClick = {},
                        label = { Text(if (c.granted) "Accordé" else "Refusé") },
                    )
                }
            }
        }
        item {
            Spacer(Modifier.height(12.dp))
            HorizontalDivider()
            Spacer(Modifier.height(8.dp))
            Text("Droits cliente", style = MaterialTheme.typography.titleMedium)
            Text(
                "Article 20 : export portable des données personnelles. " +
                    "Article 17 : demande de suppression (fenêtre 30j annulable).",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(8.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                TextButton(onClick = onExport, enabled = !busy) {
                    Text("Exporter (JSON)")
                }
                TextButton(onClick = onRequestDeletion, enabled = !busy) {
                    Text("Demander suppression")
                }
            }
            message?.let {
                Spacer(Modifier.height(4.dp))
                Text(it, style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.primary)
            }
        }
    }
}

@Composable
private fun AuditTab(items: List<ClientAuditDto>) {
    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        if (items.isEmpty()) {
            item { Text("Aucune entrée d'audit",
                color = MaterialTheme.colorScheme.onSurfaceVariant) }
        }
        items(items.size) { i ->
            val e = items[i]
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(12.dp)) {
                    Text(e.action, style = MaterialTheme.typography.titleSmall)
                    Text("${e.timestamp.take(16).replace("T", " à ")} • ${e.user_id ?: "—"}",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}
