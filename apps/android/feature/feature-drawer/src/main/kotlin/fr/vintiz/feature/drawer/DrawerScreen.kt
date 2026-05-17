package fr.vintiz.feature.drawer

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import fr.vintiz.core.common.Money
import fr.vintiz.data.reports.ZReportDto

@Composable
fun DrawerScreen(viewModel: DrawerViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsState()
    LaunchedEffect(Unit) { viewModel.refresh() }

    Scaffold { padding ->
        Column(
            modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("Caisse", style = MaterialTheme.typography.headlineLarge)
            if (state.loading) {
                CircularProgressIndicator()
                return@Column
            }
            state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }

            when (state.phase) {
                DrawerPhase.Loading -> CircularProgressIndicator()
                DrawerPhase.Empty -> OpenDrawerForm(state, viewModel)
                DrawerPhase.Open -> OpenDrawerSummary(state, viewModel)
                DrawerPhase.Close -> CloseDrawerForm(state, viewModel)
                DrawerPhase.Closed -> ClosedDrawerReport(state, viewModel)
            }
        }
    }
}

@Composable
private fun OpenDrawerForm(state: DrawerUiState, vm: DrawerViewModel) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Aucune caisse ouverte.",
                style = MaterialTheme.typography.titleLarge,
                color = MaterialTheme.colorScheme.error)
            Text(
                "Saisis le fond initial (en centimes) puis valide. Cela créera un " +
                    "CashDrawer côté serveur — toutes les ventes lui seront rattachées " +
                    "jusqu'à la fermeture.",
                style = MaterialTheme.typography.bodyMedium,
            )
            OutlinedTextField(
                value = state.openingAmountInput,
                onValueChange = vm::onOpeningAmountChange,
                label = { Text("Fond initial (cents)") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                modifier = Modifier.fillMaxWidth(),
            )
            Button(
                onClick = vm::openDrawer,
                enabled = !state.submitting && state.openingAmountInput.toLongOrNull()?.let { it > 0 } == true,
                modifier = Modifier.fillMaxWidth(),
            ) { Text(if (state.submitting) "Ouverture…" else "Ouvrir la caisse") }
        }
    }
}

@Composable
private fun OpenDrawerSummary(state: DrawerUiState, vm: DrawerViewModel) {
    val opening = state.openingAmount ?: Money.ZERO
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Caisse ouverte ✓",
                style = MaterialTheme.typography.titleLarge,
                color = MaterialTheme.colorScheme.primary)
            Text("Fond initial : ${opening.format()}",
                style = MaterialTheme.typography.titleMedium)
            Text("Toutes les ventes du jour s'enregistrent dans ce drawer.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
            Button(onClick = vm::startClose, modifier = Modifier.fillMaxWidth()) {
                Text("Fermer la caisse")
            }
        }
    }
}

@Composable
private fun CloseDrawerForm(state: DrawerUiState, vm: DrawerViewModel) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Fermeture caisse", style = MaterialTheme.typography.titleLarge)
            Text(
                "Compte les espèces du tiroir, saisis le total en centimes. " +
                    "Le serveur calcule l'écart attendu vs réel et génère le Z-Report.",
                style = MaterialTheme.typography.bodyMedium,
            )
            OutlinedTextField(
                value = state.closingAmountInput,
                onValueChange = vm::onClosingAmountChange,
                label = { Text("Montant compté (cents)") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                modifier = Modifier.fillMaxWidth(),
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = vm::cancelClose, modifier = Modifier.weight(1f)) {
                    Text("Annuler")
                }
                Button(
                    onClick = vm::closeDrawer,
                    enabled = !state.submitting,
                    modifier = Modifier.weight(1f),
                ) { Text(if (state.submitting) "Fermeture…" else "Valider la fermeture") }
            }
        }
    }
}

@Composable
private fun ClosedDrawerReport(state: DrawerUiState, vm: DrawerViewModel) {
    val context = androidx.compose.ui.platform.LocalContext.current
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Z-Report ${state.current?.drawer_id?.take(8) ?: "—"}",
                style = MaterialTheme.typography.titleLarge,
                color = MaterialTheme.colorScheme.primary)
            ZReportContent(state.zReport, state.openingAmount, state.closingAmount)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                androidx.compose.material3.OutlinedButton(
                    onClick = {
                        state.zReport?.let { z ->
                            val uri = ZReportPdfBuilder.build(context, z)
                            val send = android.content.Intent(android.content.Intent.ACTION_SEND).apply {
                                type = "application/pdf"
                                putExtra(android.content.Intent.EXTRA_STREAM, uri)
                                putExtra(android.content.Intent.EXTRA_SUBJECT,
                                    "Z-Report Vintiz — ${z.closed_at.take(10)}")
                                addFlags(android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION)
                            }
                            val chooser = android.content.Intent.createChooser(send,
                                "Envoyer le Z-Report")
                            chooser.addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK)
                            context.startActivity(chooser)
                        }
                    },
                    enabled = state.zReport != null,
                    modifier = Modifier.weight(1f),
                ) { Text("Exporter PDF") }
                Button(onClick = vm::reset, modifier = Modifier.weight(1f)) {
                    Text("Nouvelle caisse")
                }
            }
        }
    }
}

@Composable
private fun ZReportContent(z: ZReportDto?, opening: Money?, closing: Money?) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        opening?.let { Text("Fond initial : ${it.format()}") }
        closing?.let { Text("Compté : ${it.format()}",
            style = MaterialTheme.typography.titleMedium) }

        if (z == null) {
            Text(
                "Z-Report détaillé non disponible (cache report retardé). " +
                    "Consulte l'onglet Admin → Z-Reports pour le détail.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            return@Column
        }

        Text("Espèces : ${Money(z.total_cash_cents).format()}")
        Text("CB : ${Money(z.total_card_cents).format()}")
        Text("Chèque : ${Money(z.total_cheque_cents).format()}")
        Text("Attendu : ${Money(z.expected_cents).format()}",
            style = MaterialTheme.typography.titleMedium)

        val color = when {
            z.diff_cents > 0 -> MaterialTheme.colorScheme.primary
            z.diff_cents < 0 -> MaterialTheme.colorScheme.error
            else -> MaterialTheme.colorScheme.onSurfaceVariant
        }
        Text(
            "Écart : ${Money(z.diff_cents).format()}",
            style = MaterialTheme.typography.titleLarge,
            color = color,
        )
    }
}
