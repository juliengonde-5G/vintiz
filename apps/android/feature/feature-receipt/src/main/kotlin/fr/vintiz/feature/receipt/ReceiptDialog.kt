package fr.vintiz.feature.receipt

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel

@Composable
fun ReceiptDialog(
    transactionId: String,
    paidByCash: Boolean,
    onDismiss: () -> Unit,
    viewModel: ReceiptViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsState()
    LaunchedEffect(transactionId) { viewModel.load(transactionId) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Ticket vente ${transactionId.take(8)}") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Imprimer le ticket sur la MUNBYN ?",
                    style = MaterialTheme.typography.bodyLarge)
                state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                if (state.printed) {
                    Text("Ticket imprimé ✓", color = MaterialTheme.colorScheme.primary)
                }
            }
        },
        confirmButton = {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(
                    onClick = { viewModel.printTicket(kickDrawer = paidByCash) },
                    enabled = !state.printing && !state.printed,
                ) {
                    Text(if (state.printing) "Impression…" else "Imprimer (MUNBYN)")
                }
                OutlinedButton(onClick = onDismiss) {
                    Text(if (state.printed) "Fermer" else "Fermer sans ticket")
                }
            }
        },
        dismissButton = {},
    )
}
