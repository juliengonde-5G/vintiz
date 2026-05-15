package fr.vintiz.feature.auth

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Backspace
import androidx.compose.material3.Button
import androidx.compose.material3.ElevatedButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel

@Composable
fun CashierPinScreen(
    onPinSuccess: () -> Unit,
    viewModel: CashierPinViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsState()

    Scaffold { padding ->
        Column(
            modifier = Modifier.fillMaxSize().padding(padding).padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
        ) {
            Text("PIN caisse", style = MaterialTheme.typography.headlineLarge)
            Spacer(Modifier.height(8.dp))
            Text(
                "Code 4 chiffres",
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(24.dp))

            PinDots(filled = state.pin.length, total = 4)

            state.error?.let { err ->
                Spacer(Modifier.height(12.dp))
                Text(err, color = MaterialTheme.colorScheme.error)
            }

            Spacer(Modifier.height(32.dp))

            NumPad(
                onDigit = viewModel::onDigit,
                onBackspace = viewModel::onBackspace,
            )

            Spacer(Modifier.height(24.dp))

            Button(
                onClick = { viewModel.submit(onPinSuccess) },
                enabled = !state.loading && state.pin.length == 4,
                modifier = Modifier.widthIn(min = 200.dp),
            ) { Text(if (state.loading) "…" else "Valider") }
        }
    }
}

@Composable
private fun PinDots(filled: Int, total: Int) {
    Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
        repeat(total) { i ->
            Box(
                modifier = Modifier
                    .size(20.dp)
                    .padding(0.dp),
            ) {
                val color = if (i < filled) MaterialTheme.colorScheme.primary
                else MaterialTheme.colorScheme.outline
                androidx.compose.foundation.Canvas(modifier = Modifier.fillMaxSize()) {
                    drawCircle(color = color)
                }
            }
        }
    }
}

@Composable
private fun NumPad(
    onDigit: (Char) -> Unit,
    onBackspace: () -> Unit,
) {
    val rows = listOf(
        listOf("1", "2", "3"),
        listOf("4", "5", "6"),
        listOf("7", "8", "9"),
        listOf("", "0", "⌫"),
    )
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        for (row in rows) {
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                for (cell in row) {
                    NumKey(
                        label = cell,
                        onClick = {
                            when (cell) {
                                "" -> { /* no-op */ }
                                "⌫" -> onBackspace()
                                else -> onDigit(cell.first())
                            }
                        },
                    )
                }
            }
        }
    }
}

@Composable
private fun NumKey(label: String, onClick: () -> Unit) {
    if (label.isEmpty()) {
        Spacer(Modifier.size(72.dp))
        return
    }
    ElevatedButton(
        onClick = onClick,
        modifier = Modifier.size(72.dp).aspectRatio(1f),
    ) {
        if (label == "⌫") {
            Icon(Icons.Filled.Backspace, contentDescription = "Effacer")
        } else {
            Text(label, style = MaterialTheme.typography.headlineMedium)
        }
    }
}
