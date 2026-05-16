package fr.vintiz.feature.fiscal

import android.content.Intent
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
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.hilt.navigation.compose.hiltViewModel
import fr.vintiz.data.fiscal.FiscalFormat

@Composable
fun FiscalExportScreen(viewModel: FiscalExportViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsState()
    val context = LocalContext.current

    Scaffold { padding ->
        Column(
            modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("Export fiscal NF525", style = MaterialTheme.typography.headlineLarge)
            Text(
                "Hash chain SHA-256 signée serveur — fichier prêt à transmettre à la DGFiP.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    OutlinedTextField(
                        value = state.from.orEmpty(),
                        onValueChange = { viewModel.setFrom(it.ifBlank { null }) },
                        label = { Text("Du (YYYY-MM-DD, vide = depuis le début)") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                    )
                    OutlinedTextField(
                        value = state.to.orEmpty(),
                        onValueChange = { viewModel.setTo(it.ifBlank { null }) },
                        label = { Text("Au (YYYY-MM-DD, vide = aujourd'hui)") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                    )
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        FiscalFormat.entries.forEach { f ->
                            Button(
                                onClick = { viewModel.setFormat(f) },
                                enabled = state.format != f,
                            ) { Text(f.label) }
                        }
                    }
                    state.validation?.let {
                        Text(it, color = MaterialTheme.colorScheme.error)
                    }
                    Button(
                        onClick = viewModel::export,
                        enabled = !state.loading && state.validation == null,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        if (state.loading) {
                            CircularProgressIndicator(
                                modifier = Modifier.height(20.dp),
                                strokeWidth = 2.dp,
                            )
                        } else {
                            Text("Générer l'export")
                        }
                    }
                }
            }

            state.lastExport?.let { file ->
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text("Fichier prêt", style = MaterialTheme.typography.titleLarge,
                            color = MaterialTheme.colorScheme.primary)
                        Text(file.filename, style = MaterialTheme.typography.bodyMedium)
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Button(onClick = {
                                val intent = Intent(Intent.ACTION_SEND).apply {
                                    type = file.mimeType
                                    putExtra(Intent.EXTRA_STREAM, file.uri)
                                    addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                                }
                                ContextCompat.startActivity(
                                    context,
                                    Intent.createChooser(intent, "Partager l'export fiscal"),
                                    null,
                                )
                            }) { Text("Partager") }
                            OutlinedButton(onClick = {
                                val intent = Intent(Intent.ACTION_VIEW).apply {
                                    setDataAndType(file.uri, file.mimeType)
                                    addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                                }
                                runCatching {
                                    ContextCompat.startActivity(context, intent, null)
                                }
                            }) { Text("Ouvrir") }
                        }
                    }
                }
            }

            state.error?.let {
                Text(it, color = MaterialTheme.colorScheme.error)
            }

            Spacer(Modifier.height(8.dp))
            Text(
                "Format XML : NF525. Format JSON : pratique pour audit interne. " +
                "L'hash SHA-256 (`signature`) doit toujours être vérifié par le destinataire.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}
