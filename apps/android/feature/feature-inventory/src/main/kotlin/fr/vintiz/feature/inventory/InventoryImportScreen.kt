package fr.vintiz.feature.inventory

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel

@Composable
fun InventoryImportScreen(
    onBack: () -> Unit,
    viewModel: InventoryImportViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsState()
    val launcher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.GetContent(),
    ) { uri -> uri?.let(viewModel::pickFile) }

    Scaffold { padding ->
        Column(
            modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            TextButton(onClick = onBack) { Text("← Retour") }
            Text("Import CSV", style = MaterialTheme.typography.headlineLarge)
            Text(
                "Format attendu : barcode;name;price_cents;tva_rate;category. " +
                    "Header obligatoire. Toujours valider en dry-run avant le commit.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = { launcher.launch("text/*") }) {
                        Text("Choisir un fichier CSV")
                    }
                    state.file?.let {
                        Text("Fichier : ${it.name} (${state.fileSize} octets)",
                            style = MaterialTheme.typography.bodyMedium)
                    }
                }
            }

            if (state.file != null) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(
                        onClick = viewModel::previewImport,
                        enabled = !state.running,
                        modifier = Modifier.weight(1f),
                    ) { Text(if (state.running) "Test…" else "Tester (dry-run)") }
                    Button(
                        onClick = viewModel::confirmImport,
                        enabled = !state.running && state.result?.dry_run == true,
                        modifier = Modifier.weight(1f),
                    ) { Text("Confirmer l'import") }
                }
            }

            state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }

            state.result?.let { r ->
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text(
                            if (r.dry_run) "Aperçu (rien n'a été modifié)"
                            else "Import effectué ✓",
                            style = MaterialTheme.typography.titleLarge,
                            color = if (r.dry_run) MaterialTheme.colorScheme.onSurfaceVariant
                            else MaterialTheme.colorScheme.primary,
                        )
                        Row {
                            Text("Créés : ${r.created}", modifier = Modifier.weight(1f))
                            Text("MAJ : ${r.updated}", modifier = Modifier.weight(1f))
                            Text("Ignorés : ${r.skipped}")
                        }
                        if (r.errors.isNotEmpty()) {
                            Text("Erreurs (${r.errors.size}) :",
                                style = MaterialTheme.typography.titleSmall,
                                color = MaterialTheme.colorScheme.error)
                            LazyColumn(
                                modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
                                verticalArrangement = Arrangement.spacedBy(4.dp),
                            ) {
                                items(r.errors, key = { "${it.row}-${it.reason}" }) { e ->
                                    Text("Ligne ${e.row} : ${e.reason}",
                                        style = MaterialTheme.typography.bodySmall)
                                }
                            }
                        }
                        if (!r.dry_run) {
                            TextButton(onClick = viewModel::reset, modifier = Modifier.padding(top = 8.dp)) {
                                Text("Importer un autre fichier")
                            }
                        }
                    }
                }
            }
        }
    }
}
